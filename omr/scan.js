/* On-device perspective correction and fixed-template OMR. No remote image service.
   Methods: OpenCV perspective transform + OMRChecker's template/region workflow;
   this is an independent small JS implementation, not their Python runtime. */
(function(){
'use strict';
function convex(points){
 if(!Array.isArray(points)||points.length!==4)return false;
 let sign=0,area=0;
 for(let i=0;i<4;i++){
  const [a,b,c]=[points[i],points[(i+1)%4],points[(i+2)%4]];
  if(![a.x,a.y].every(Number.isFinite))return false;
  const cross=(b.x-a.x)*(c.y-b.y)-(b.y-a.y)*(c.x-b.x);
  if(Math.abs(cross)<1)return false;
  if(sign&&Math.sign(cross)!==sign)return false;
  sign=Math.sign(cross);area+=a.x*b.y-b.x*a.y;
 }
 return Math.abs(area)/2>1000;
}
function transform(points,width,height){
 if(!convex(points))throw new Error('네 모서리가 겹치거나 순서가 뒤집혔습니다. 다시 맞춰 주세요.');
 const target=[[0,0],[width-1,0],[width-1,height-1],[0,height-1]],matrix=[];
 target.forEach(([x,y],i)=>{const p=points[i];matrix.push([x,y,1,0,0,0,-p.x*x,-p.x*y,p.x],[0,0,0,x,y,1,-p.y*x,-p.y*y,p.y]);});
 for(let col=0;col<8;col++){
  let pivot=col;for(let row=col+1;row<8;row++)if(Math.abs(matrix[row][col])>Math.abs(matrix[pivot][col]))pivot=row;
  if(Math.abs(matrix[pivot][col])<1e-9)throw new Error('사진의 모서리를 다시 맞춰 주세요.');
  [matrix[col],matrix[pivot]]=[matrix[pivot],matrix[col]];
  const d=matrix[col][col];for(let k=col;k<=8;k++)matrix[col][k]/=d;
  for(let row=0;row<8;row++)if(row!==col){const v=matrix[row][col];for(let k=col;k<=8;k++)matrix[row][k]-=v*matrix[col][k];}
 }
 return matrix.map(row=>row[8]);
}
function warp(input,points,width=1800,height=1406){
 if(points.some(p=>p.x<0||p.y<0||p.x>=input.width||p.y>=input.height))throw new Error('모서리는 사진 안에 맞춰 주세요.');
 const m=transform(points,width,height),output=new ImageData(width,height),src=input.data,dst=output.data;
 for(let y=0;y<height;y++)for(let x=0;x<width;x++){
  const den=m[6]*x+m[7]*y+1,sx=(m[0]*x+m[1]*y+m[2])/den,sy=(m[3]*x+m[4]*y+m[5])/den;
  const xx=Math.max(0,Math.min(input.width-2,Math.floor(sx))),yy=Math.max(0,Math.min(input.height-2,Math.floor(sy))),dx=sx-xx,dy=sy-yy;
  const at=(yy*input.width+xx)*4,to=(y*width+x)*4;
  for(let c=0;c<3;c++)dst[to+c]=src[at+c]*(1-dx)*(1-dy)+src[at+4+c]*dx*(1-dy)+src[at+input.width*4+c]*(1-dx)*dy+src[at+(input.width+1)*4+c]*dx*dy;
  dst[to+3]=255;
 }
 return output;
}
function corners(image){
 // Propose a bright document component. The user must inspect/correct this proposal.
 const canvas=document.createElement('canvas'),scale=Math.min(400/image.width,400/image.height,1);
 canvas.width=Math.round(image.width*scale);canvas.height=Math.round(image.height*scale);
 const original=document.createElement('canvas');original.width=image.width;original.height=image.height;original.getContext('2d').putImageData(image,0,0);
 const ctx=canvas.getContext('2d');ctx.drawImage(original,0,0,canvas.width,canvas.height);
 const data=ctx.getImageData(0,0,canvas.width,canvas.height).data,w=canvas.width,h=canvas.height,seen=new Uint8Array(w*h),queue=new Int32Array(w*h);
 let best=[];
 function bright(i){return (data[i*4]+data[i*4+1]+data[i*4+2])/3>170;}
 for(let start=0;start<w*h;start++){
  if(seen[start]||!bright(start))continue;
  let count=1,head=0;queue[0]=start;seen[start]=1;
  while(head<count){const i=queue[head++],x=i%w,y=Math.floor(i/w);for(const j of [x?i-1:-1,x<w-1?i+1:-1,y?i-w:-1,y<h-1?i+w:-1])if(j>=0&&!seen[j]&&bright(j)){seen[j]=1;queue[count++]=j;}}
  if(count>best.length)best=Array.from(queue.subarray(0,count));
 }
 if(best.length<w*h*.12)return [{x:0,y:0},{x:image.width-1,y:0},{x:image.width-1,y:image.height-1},{x:0,y:image.height-1}];
 const scores=[Infinity,-Infinity,-Infinity,Infinity],out=[];
 for(const i of best){const x=i%w,y=Math.floor(i/w),s=x+y,d=x-y;
  if(s<scores[0]){scores[0]=s;out[0]={x:x/scale,y:y/scale};}
  if(d>scores[1]){scores[1]=d;out[1]={x:x/scale,y:y/scale};}
  if(s>scores[2]){scores[2]=s;out[2]={x:x/scale,y:y/scale};}
  if(d<scores[3]){scores[3]=d;out[3]={x:x/scale,y:y/scale};}
 }
 return out;
}
function gray(data,at){return (data[at]+data[at+1]+data[at+2])/3;}
function spotScore(photo,reference,spot){
 const px=Math.round(spot.x),py=Math.round(spot.y),w=photo.width,d=photo.data,r=reference.data;
 const bright=[];for(let y=-20;y<=20;y+=2)for(let x=-13;x<=13;x+=2)bright.push(gray(d,((py+y)*w+px+x)*4));
 bright.sort((a,b)=>a-b);const white=bright[Math.floor(bright.length*.9)];
 let eligible=0,ink=0,outline=0,found=0;
 for(let y=-10;y<=10;y++)for(let x=-7;x<=7;x++){
  const at=((py+y)*w+px+x)*4,bg=gray(r,at),lum=gray(d,at)*255/Math.max(white,1);
  if(x*x/25+y*y/49<=1&&bg>45){eligible++;if(lum<Math.min(100,bg-45))ink++;}
  if(Math.max(r[at],r[at+1],r[at+2])-Math.min(r[at],r[at+1],r[at+2])>60){outline++;if(lum<205)found++;}
 }
 return {fill:eligible>=12?ink/eligible:null,alignment:outline?found/outline:0,white};
}
function classify(scores){
 if(scores.some(v=>v.fill===null||v.white<70))return {value:null,flag:'사진 품질 확인'};
 const strong=scores.flatMap((v,i)=>v.fill>=.68?[i]:[]),weak=scores.flatMap((v,i)=>v.fill>=.22&&v.fill<.68?[i]:[]);
 if(strong.length>1)return {value:null,flag:'중복 마킹'};
 if(weak.length)return {value:null,flag:'흐린 마킹'};
 if(strong.length===1)return {value:strong[0],flag:null};
 return {value:null,flag:'미응답 확인'};
}
function layoutScore(photo,reference){
 let total=0,found=0;const a=photo.data,r=reference.data,w=reference.width;
 // Verify the whole printed coloured layout, including unselected answer blocks.
 // This separates English/inquiry forms whose first twenty answer rows nearly coincide.
 for(let y=160;y<reference.height-40;y+=3)for(let x=540;x<w-40;x+=3){
  const at=(y*w+x)*4;if(Math.max(r[at],r[at+1],r[at+2])-Math.min(r[at],r[at+1],r[at+2])<70)continue;
  total++;let match=false;
  for(let yy=-2;yy<=2&&!match;yy++)for(let xx=-2;xx<=2&&!match;xx++){
   const p=((y+yy)*w+x+xx)*4;
   if(gray(a,p)<205)match=true;
  }
  if(match)found++;
 }
 return total?found/total:0;
}
function read(photo,reference,questions){
 if(photo.width!==reference.width||photo.height!==reference.height)throw new Error('답안지 크기가 맞지 않습니다.');
 if(layoutScore(photo,reference)<.8)throw new Error('선택한 양식의 전체 배치와 사진이 맞지 않습니다. 과목 양식을 확인해 주세요.');
 let alignment=0,spots=0;const answers=[],flags=new Map();
 for(const q of questions){
  const scores=q.spots.map(s=>spotScore(photo,reference,s));for(const s of scores){alignment+=s.alignment;spots++;}
  if(q.kind==='choice'){
   const c=classify(scores);answers[q.n-1]=c.value===null?null:c.value+1;if(c.flag)flags.set(q.n,c.flag);
  }else{
   const parts=[0,1,2].map(i=>classify(scores.slice(i*10,i*10+10))),digits=parts.map(c=>c.value);
   const flag=parts.find(c=>c.flag&&c.flag!=='미응답 확인');
   let invalid=!!flag;
   if(digits[2]===null||digits[0]!==null&&digits[1]===null)invalid=true;
   answers[q.n-1]=invalid?null:(digits[0]||0)*100+(digits[1]||0)*10+digits[2];
   if(invalid)flags.set(q.n,flag?.flag||'숫자 마킹 확인');
  }
 }
 if(!spots||alignment/spots<.4)throw new Error('선택한 양식의 답란과 사진이 맞지 않습니다. 회전·모서리·과목 양식을 확인해 주세요.');
 return {answers,flags,alignment:alignment/spots};
}
window.GijulOmrScan=Object.freeze({convex,transform,warp,corners,spotScore,classify,layoutScore,read});
})();
