(function(){
'use strict';
const F=window.GijulOmrForms,S=window.GijulOmrScan;
if(!F||!S)return;
const DRAFT='gijul.omr.drafts.v1';
const escape=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let current=null;
const places=['백','십','일'];
function digitsOf(value){
 if(value===null)return [null,null,null];
 return [value>=100?Math.floor(value/100):null,value>=10?Math.floor(value/10)%10:null,value%10];
}
function numberAnswer(digits){
 if(digits.every(v=>v===null))return {value:null,partial:false};
 if(digits[2]===null||digits[0]!==null&&digits[1]===null)return {value:null,partial:true};
 return {value:(digits[0]||0)*100+(digits[1]||0)*10+digits[2],partial:false};
}
function restoreNumbers(s,draft){
 s.numberMarks={};
 for(const q of s.form.questions){if(q.kind!=='number')continue;
  const d=draft?.numberMarks?.[q.n];
  const valid=Array.isArray(d)&&d.length===3&&d.every(v=>v===null||Number.isInteger(v)&&v>=0&&v<=9);
  s.numberMarks[q.n]=valid?[...d]:digitsOf(s.answers[q.n-1]);
  const got=numberAnswer(s.numberMarks[q.n]);s.answers[q.n-1]=got.value;
  if(got.partial)s.flags.set(q.n,'숫자 마킹 미완성');
 }
}
function loadDraft(key,count){
 try{const text=localStorage.getItem(DRAFT)||'{}';if(text.length>300000)return null;const o=JSON.parse(text),d=o[key];
  if(!d||!Array.isArray(d.answers)||d.answers.length!==count||!d.answers.every(a=>a===null||Number.isInteger(a)&&a>=0&&a<=999))return null;
  return d;
 }catch(e){return null;}
}
function validateKey(answers,points,form,questions){
 if(!Array.isArray(answers)||answers.length!==form.count||!answers.every((v,i)=>Number.isInteger(v)&&v>=0&&v<=(questions[i].kind==='choice'?5:999)&&(questions[i].kind!=='choice'||v>=1)))return '정답을 문항 순서대로 모두 적어 주세요. 선택형은 1~5, 단답형은 0~999의 정수입니다.';
 if(!Array.isArray(points)||points.length!==form.count||!points.every(v=>Number.isInteger(v)&&v>=1&&v<=10))return '문항별 배점을 모두 정수로 적어 주세요.';
 if(points.reduce((a,b)=>a+b,0)!==form.maximum)return '배점 합계가 '+form.maximum+'점이어야 합니다.';
 return '';
}
function grade(answers,key){return {score:key.points.reduce((sum,p,i)=>sum+(answers[i]===key.answers[i]?p:0),0),wrong:answers.flatMap((v,i)=>v!==key.answers[i]?[i+1]:[])};}
function open(meta,options={}){
 const style=document.querySelector('#omrStyle');if(style)style.media='all';
 close();const form=F.resolve(meta);if(!form)throw new Error('현재 답안지 양식은 2021년 시행 이후 고3·N수 회차를 지원합니다.');
 const exact=F.exactKey(meta),draft=options.demo?null:loadDraft(exact,form.count),verified=F.keys[exact];
 const state={meta,options,form,exact,answers:draft?.answers||Array(form.count).fill(null),slot:draft?.slot===2?2:1,key:verified?{answers:[...verified.answers],points:[...verified.points],source:verified.source}:null,
  flags:new Map(Array.isArray(draft?.flags)?draft.flags.filter(v=>Array.isArray(v)&&Number.isInteger(v[0])&&v[0]>=1&&v[0]<=form.count&&typeof v[1]==='string').slice(0,form.count):[]),mode:null,photoDerived:!!draft?.photoDerived,stage:'choose',zoom:1.55,whole:window.innerWidth>=768,wide:window.innerWidth>=768,active:1,photo:null,photoChecked:false,blankChecked:false,request:null,job:0,draftError:'',closed:false,focus:document.activeElement};
 restoreNumbers(state,draft);
 if(!state.key&&draft?.key&&!validateKey(draft.key.answers,draft.key.points,form,F.questions(form,state.slot)))state.key=draft.key;
 const dialog=document.createElement('dialog');dialog.className='omr-dialog';dialog.setAttribute('aria-label','답안 입력·채점');
 dialog.innerHTML='<header class="omr-header"><div><span>기출 직행</span><strong>답안 입력·채점</strong></div><button type="button" class="omr-close" aria-label="답안 입력 닫기">✕</button></header><main class="omr-body" tabindex="-1"></main><footer class="omr-actions"></footer><div class="omr-live" role="status" aria-live="polite"></div>';
 state.dialog=dialog;state.body=dialog.querySelector('main');state.footer=dialog.querySelector('footer');current=state;
 dialog.querySelector('.omr-close').onclick=close;
 dialog.addEventListener('keydown',event=>{if(event.key==='Escape')event.stopPropagation();});
 dialog.addEventListener('cancel',event=>{event.preventDefault();close();});
 safelyWatchSize(state);document.body.append(dialog);dialog.showModal();render();
 return state;
}
function safelyWatchSize(s){
 s.resize=()=>{if(current!==s||s.stage!=='input')return;const wide=window.innerWidth>=768;if(wide!==s.wide){s.wide=wide;s.whole=wide;}updateSheet();if(!s.whole)focusQuestion(s.active);};
 window.addEventListener('resize',s.resize);
}
function back(){const s=current;if(!s)return false;const top=s.dialog.querySelector('dialog[open]');if(top){top.close();return true;}return close();}
function close(){
 const s=current;if(!s)return false;s.closed=true;current=null;
 if(s.request){clearTimeout(s.request.timeout);try{window.GijulNative?.cancelOmrScan?.(s.request.id);}catch(e){}}
 s.sheetObserver?.disconnect();window.removeEventListener('resize',s.resize);s.photo=null;s.dialog.close();s.dialog.remove();s.focus?.focus?.({preventScroll:true});s.options.onClose?.();return true;
}
function live(text){const s=current;if(s)s.dialog.querySelector('.omr-live').textContent=text;}
function note(text){const s=current;if(s){const node=s.body.querySelector('.omr-note');if(node)node.textContent=text;live(text);}}
function saveDraft(){
 const s=current;if(!s||s.options.demo)return;
 try{let all=JSON.parse(localStorage.getItem(DRAFT)||'{}');if(!all||Array.isArray(all)||typeof all!=='object')all={};
  delete all[s.exact];all[s.exact]={answers:s.answers,numberMarks:s.numberMarks,slot:s.slot,key:s.key,photoDerived:s.photoDerived,flags:[...s.flags],at:Date.now()};const entries=Object.entries(all).slice(-20);
  localStorage.setItem(DRAFT,JSON.stringify(Object.fromEntries(entries)));s.draftError='';
 }catch(e){s.draftError='답안 임시 저장을 하지 못했습니다. 화면을 닫기 전에 점수 기록을 저장해 주세요.';note(s.draftError);}
}
function info(){const {meta,form}=current;return `<div class="omr-exam"><strong>${escape(F.heading(meta))}</strong><span>${escape(meta.date.slice(0,4)+'.'+meta.date.slice(4,6)+'.'+meta.date.slice(6))} 시행 · ${escape(meta.subject)}</span><small>${form.period}교시 · ${escape(F.displayArea(meta,form))} · ${form.count}문항 · ${form.maximum}점 만점</small></div>`;}
function primary(label,handler,disabled=false){const s=current;s.footer.innerHTML=`<button type="button" class="omr-primary" ${disabled?'disabled':''}>${escape(label)}</button><p>${s.options.demo?'체험 화면 · 앱 기록에 저장하지 않습니다':'답안 초안은 이 기기에만 보관 · 점수·오답은 풀이 기록으로'}</p>`;s.footer.querySelector('button').onclick=handler;}
function render(){
 const s=current;if(!s)return;s.sheetObserver?.disconnect();s.dialog.dataset.stage=s.stage;
 if(s.stage==='choose')choose();else if(s.stage==='photo')photo();else if(s.stage==='crop')crop();else if(s.stage==='key')keyEditor();else if(s.stage==='result')result();else input();
 if(s.draftError)note(s.draftError);
}
function move(stage){current.job++;current.stage=stage;render();current.body.focus({preventScroll:true});current.body.scrollTop=0;}
function choose(){
 const s=current;
 s.body.innerHTML=`<p class="omr-kicker">ANSWER SHEET</p><h1>어떻게 답안을 입력할까요?</h1>${info()}<div class="omr-modes"><button type="button" id="omrManual"><span class="omr-mode-icon">①</span><strong>직접 누르기</strong><small>답안지의 마킹 칸을 눌러 입력합니다.</small></button><button type="button" id="omrPhoto"><span class="omr-mode-icon">▣</span><strong>사진으로 읽기</strong><small>문서를 스캔하고 읽은 답을 확인합니다.</small></button></div><p class="omr-note" role="status">${s.answers.some(v=>v!==null)?'이 기기에 임시 저장한 답안을 이어서 입력할 수 있습니다.':'직접 입력은 빈 답안지에서 시작합니다.'}</p><div class="omr-source"><img src="${(F.manualForms[s.form.id]||s.form).image}" alt="${escape(s.form.area)} 공식 공개 답안지"><p>직접 입력은 공식 공개 모평 답안지의 고해상도 원본을 사용합니다.<br>사진 읽기는 경기도교육청 수능 견본과 같은 배치가 필요합니다.</p><a href="${F.manualSource}" target="_blank" rel="noopener">원본 공개 자료 ↗</a></div>`;
 s.footer.innerHTML='<p>입력 방식은 진행 중에도 바꿀 수 있습니다.</p>';
 s.body.querySelector('#omrManual').onclick=()=>{s.mode='manual';move('input');};
 s.body.querySelector('#omrPhoto').onclick=()=>{s.mode='photo';move('photo');};
}
function photo(){
 const s=current;
 s.body.innerHTML=`<p class="omr-kicker">SCAN DOCUMENT</p><h1>답안지를 먼저 스캔합니다.</h1>${info()}<div class="omr-scan-preview"><img src="${s.form.image}" alt="선택한 답안지 양식"><span>네 모서리 · 회전 · 기울기 확인</span></div><p>선택한 양식과 같은 종이 답안지를 사용해 주세요.<br>스캔 후 네 모서리를 확인하고 답란을 읽습니다.</p>${s.form.id==='inquiry'?'<label class="omr-field">읽을 답란<select id="omrSlot"><option value="1">제1선택 답란</option><option value="2">제2선택 답란</option></select></label>':''}<div class="omr-photo-buttons"><button type="button" id="omrScan">문서 스캔 / 촬영</button><button type="button" id="omrPick">사진에서 가져오기</button></div><button class="omr-link" id="omrBack">입력 방식 다시 선택</button><p class="omr-note" role="status">사진은 이 기기에서 처리하며 서버로 보내지 않습니다.</p><input type="file" id="omrFile" accept="image/jpeg,image/png" hidden>`;
 if(s.form.id==='inquiry'){const select=s.body.querySelector('#omrSlot');select.value=String(s.slot);select.onchange=()=>{s.slot=+select.value;saveDraft();};}
 s.body.querySelector('#omrBack').onclick=()=>move('choose');
 const file=s.body.querySelector('#omrFile');file.onchange=()=>{if(file.files[0])readFile(file.files[0],s);};
 s.body.querySelector('#omrScan').onclick=()=>launchPhoto(false);
 s.body.querySelector('#omrPick').onclick=()=>launchPhoto(true);
 s.footer.innerHTML='<p>사진 인식은 시험 적용 단계입니다. 읽은 답은 반드시 확인합니다.</p>';
}
function launchPhoto(pick){
 const s=current,native=window.GijulNative;
 if(native){
  const method=pick?'pickOmrPhoto':'scanOmr';
  if(typeof native[method]!=='function'){note('이 앱에는 문서 스캔 기능이 없습니다. 앱을 업데이트하거나 직접 입력을 사용해 주세요.');return;}
  if(s.request){note('사진 작업을 준비하고 있습니다. 잠시 기다려 주세요.');return;}
  const id='omr_'+Date.now()+'_'+Math.random().toString(36).slice(2,9),timeout=setTimeout(()=>{if(current===s&&s.request?.id===id){native.cancelOmrScan?.(id);s.request=null;note('스캐너 준비가 오래 걸립니다. 인터넷 연결을 확인하거나 사진에서 가져오기를 사용해 주세요.');}},120000);
  s.request={id,timeout};note('문서 스캐너를 준비하고 있습니다. 처음에는 추가 다운로드가 필요할 수 있습니다.');
  try{native[method](id);}catch(e){clearTimeout(timeout);s.request=null;note('사진 작업을 열지 못했습니다. 직접 입력을 사용할 수 있습니다.');}
 }else{
  const file=s.body.querySelector('#omrFile');if(pick)file.removeAttribute('capture');else file.setAttribute('capture','environment');file.click();
 }
}
window.gijulOmrScanResult=(id,ok,value)=>{
 const s=current;if(!s||s.request?.id!==id)return;clearTimeout(s.request.timeout);s.request=null;
 if(!ok){note(value);return;}
 if(typeof value!=='string'||value.length>3*1024*1024||!value.startsWith('data:image/jpeg;base64,')){note('사진 응답을 읽지 못했습니다.');return;}
 try{const raw=atob(value.slice(23)),bytes=Uint8Array.from(raw,c=>c.charCodeAt(0));readFile(new Blob([bytes],{type:'image/jpeg'}),s);}catch(e){note('사진을 읽지 못했습니다.');}
};
async function imageSize(file){
 const bytes=new Uint8Array(await file.slice(0,1024*1024).arrayBuffer()),v=new DataView(bytes.buffer);
 if(file.type==='image/png'){
  if(bytes.length<24||v.getUint32(0)!==0x89504e47||v.getUint32(4)!==0x0d0a1a0a)throw new Error('PNG 형식 오류');
  return [v.getUint32(16),v.getUint32(20)];
 }
 if(bytes[0]!==255||bytes[1]!==216)throw new Error('JPEG 형식 오류');
 let at=2,orientation=1,size=null;
 while(at+4<bytes.length){
  if(bytes[at++]!==255)break;while(bytes[at]===255)at++;
  const marker=bytes[at++];if(marker===218||marker===217)break;
  const length=v.getUint16(at);if(length<2||at+length>bytes.length)break;
  if(marker===225&&length>16&&v.getUint32(at+2)===0x45786966){
   try{const base=at+8,little=v.getUint16(base)===0x4949,dir=base+v.getUint32(base+4,little),count=v.getUint16(dir,little);
    for(let i=0;i<Math.min(count,100);i++){const tag=dir+2+i*12;if(v.getUint16(tag,little)===274){orientation=v.getUint16(tag+8,little);break;}}
   }catch(e){}
  }
  if([192,193,194,195,197,198,199,201,202,203,205,206,207].includes(marker)&&length>=7)size=[v.getUint16(at+5),v.getUint16(at+3)];
  at+=length;
 }
 if(!size)throw new Error('JPEG 크기 확인 실패');
 return orientation>=5&&orientation<=8?size.reverse():size;
}
async function readFile(file,s){
 const job=++s.job;
 if(file.size>20*1024*1024){note('20MB 이하의 JPEG 또는 PNG 사진을 골라 주세요.');return;}
 if(!['image/jpeg','image/png'].includes(file.type)){note('JPEG 또는 PNG 사진을 골라 주세요.');return;}
 note('사진을 읽고 있습니다.');
 try{
  const [width,height]=await imageSize(file);if(!width||!height||width*height>40000000)throw new Error('사진 크기 초과');
  const ratio=Math.min(1800/Math.max(width,height),1);
  const bitmap=await createImageBitmap(file,{resizeWidth:Math.max(1,Math.round(width*ratio)),resizeHeight:Math.max(1,Math.round(height*ratio))});if(current!==s||s.closed||s.job!==job){bitmap.close();return;}
  const scale=Math.min(1800/Math.max(bitmap.width,bitmap.height),1),canvas=document.createElement('canvas');canvas.width=Math.round(bitmap.width*scale);canvas.height=Math.round(bitmap.height*scale);
  const ctx=canvas.getContext('2d',{willReadFrequently:true});ctx.drawImage(bitmap,0,0,canvas.width,canvas.height);bitmap.close();
  s.photo=ctx.getImageData(0,0,canvas.width,canvas.height);s.corners=S.corners(s.photo);s.photoChecked=false;move('crop');
 }catch(e){if(current===s&&s.job===job)note('사진을 읽지 못했습니다. 다른 JPEG 또는 PNG 사진을 골라 주세요.');}
}
function crop(){
 const s=current;
 s.body.innerHTML=`<p class="omr-kicker">ALIGN THE SHEET</p><h1>네 모서리를 맞춰 주세요.</h1>${info()}<p>파란 점을 답안지의 네 모서리에 맞춥니다.<br>양식 밖의 인쇄 여백은 포함하지 마세요.</p><div class="omr-crop"><canvas id="omrCrop"></canvas></div><div class="omr-corner-fields">${['왼쪽 위','오른쪽 위','오른쪽 아래','왼쪽 아래'].map((name,i)=>`<label>${name}<input type="range" min="0" max="1000" step="1" data-corner="${i}" data-axis="x" aria-label="${name} 가로 위치"><input type="range" min="0" max="1000" step="1" data-corner="${i}" data-axis="y" aria-label="${name} 세로 위치"></label>`).join('')}</div><div class="omr-photo-buttons"><button id="omrRotate">90° 회전</button><button id="omrRetry">사진 다시 선택</button></div><label class="omr-check"><input type="checkbox" id="omrFormCheck">${escape(s.form.area)} 양식과 문항 배치가 같은 것을 확인했습니다.</label><p class="omr-note" role="status">맞춘 영역을 평평하게 보정한 뒤 답란을 읽습니다.</p>`;
 const canvas=s.body.querySelector('#omrCrop');canvas.width=s.photo.width;canvas.height=s.photo.height;
 function draw(){const ctx=canvas.getContext('2d');ctx.putImageData(s.photo,0,0);ctx.strokeStyle='#1d78bb';ctx.fillStyle='#1d78bb';ctx.lineWidth=4;ctx.beginPath();s.corners.forEach((p,i)=>i?ctx.lineTo(p.x,p.y):ctx.moveTo(p.x,p.y));ctx.closePath();ctx.stroke();s.corners.forEach(p=>{ctx.beginPath();ctx.arc(p.x,p.y,Math.max(s.photo.width/40,14),0,Math.PI*2);ctx.fill();});}
 function sync(){s.body.querySelectorAll('[data-corner]').forEach(input=>{const axis=input.dataset.axis,max=axis==='x'?s.photo.width-1:s.photo.height-1;input.value=Math.round(s.corners[+input.dataset.corner][axis]/max*1000);});draw();}
 let dragging=null;
 const position=e=>{const box=canvas.getBoundingClientRect();return {x:Math.max(0,Math.min(canvas.width-1,(e.clientX-box.left)*canvas.width/box.width)),y:Math.max(0,Math.min(canvas.height-1,(e.clientY-box.top)*canvas.height/box.height))};};
 canvas.onpointerdown=e=>{const p=position(e);dragging=s.corners.map((c,i)=>({i,d:Math.hypot(c.x-p.x,c.y-p.y)})).sort((a,b)=>a.d-b.d)[0].i;canvas.setPointerCapture(e.pointerId);s.corners[dragging]=p;sync();};
 canvas.onpointermove=e=>{if(dragging!==null){s.corners[dragging]=position(e);sync();}};canvas.onpointerup=canvas.onpointercancel=()=>{dragging=null;};
 s.body.querySelectorAll('[data-corner]').forEach(input=>input.oninput=()=>{const axis=input.dataset.axis,max=axis==='x'?s.photo.width-1:s.photo.height-1;s.corners[+input.dataset.corner][axis]=+input.value/1000*max;draw();});
 s.body.querySelector('#omrRotate').onclick=()=>{const before=document.createElement('canvas');before.width=s.photo.width;before.height=s.photo.height;before.getContext('2d').putImageData(s.photo,0,0);const rotated=document.createElement('canvas');rotated.width=before.height;rotated.height=before.width;const ctx=rotated.getContext('2d');ctx.translate(rotated.width,0);ctx.rotate(Math.PI/2);ctx.drawImage(before,0,0);s.photo=ctx.getImageData(0,0,rotated.width,rotated.height);s.corners=S.corners(s.photo);crop();};
 s.body.querySelector('#omrRetry').onclick=()=>move('photo');
 primary('보정하고 답안 읽기',()=>recognize(s),true);
 s.body.querySelector('#omrFormCheck').onchange=e=>{s.footer.querySelector('button').disabled=!e.target.checked;};sync();
}
async function recognize(s){
 const job=s.job;
 s.footer.querySelector('button').disabled=true;note('기울기를 보정하고 마킹을 읽고 있습니다.');
 await new Promise(resolve=>requestAnimationFrame(()=>setTimeout(resolve,0)));
 try{
  if(current!==s||s.job!==job)return;
  const reference=await loadReference(s.form);if(current!==s||s.job!==job)return;
  const fixed=S.warp(s.photo,s.corners,s.form.width,s.form.height),read=S.read(fixed,reference,F.questions(s.form,s.slot));
  s.photo=fixed;s.photoDerived=true;s.answers=read.answers;s.flags=read.flags;restoreNumbers(s,null);s.photoChecked=false;s.blankChecked=false;saveDraft();move('input');
 }catch(e){if(current===s&&s.job===job){note(e.message||'사진의 답란을 읽지 못했습니다. 모서리를 다시 맞춰 주세요.');s.footer.querySelector('button').disabled=false;}}
}
const references=new Map();
async function loadReference(form){
 if(references.has(form.image))return references.get(form.image);
 const response=await fetch(form.image);if(!response.ok)throw new Error('답안지 원본을 불러오지 못했습니다. 인터넷 연결을 확인해 주세요.');
 const bitmap=await createImageBitmap(await response.blob()),canvas=document.createElement('canvas');canvas.width=form.width;canvas.height=form.height;const ctx=canvas.getContext('2d',{willReadFrequently:true});ctx.drawImage(bitmap,0,0,form.width,form.height);bitmap.close();const data=ctx.getImageData(0,0,form.width,form.height);references.set(form.image,data);return data;
}
function input(){
 const s=current;s.sheetForm=s.photoDerived?s.form:(F.manualForms[s.form.id]||s.form);const questions=F.questions(s.sheetForm,s.slot),done=s.answers.filter(v=>v!==null).length;
 s.body.innerHTML=`<p class="omr-kicker">${s.photoDerived?'CHECK YOUR MARKS':'MARK YOUR ANSWERS'}</p><h1>${s.photoDerived?'읽은 답을 확인해 주세요.':'답안지의 답란을 눌러 주세요.'}</h1>${info()}<div class="omr-input-tools"><label>문항 <select id="omrQuestion">${questions.map(q=>`<option value="${q.n}">${q.n}번${s.flags.has(q.n)?' · 확인 필요':''}</option>`).join('')}</select></label><button id="omrWhole">전체 양식</button><button id="omrKey">정답·배점</button></div><div class="omr-progress"><span>${done}/${s.form.count}문항 입력</span><span id="omrPending">${s.flags.size?'확인 '+s.flags.size+'개 남음':'답란을 다시 누르면 지웁니다'}</span></div><div class="omr-sheet-scroll"><div class="omr-sheet"><img src="${s.sheetForm.image}" alt="${escape(s.form.area)} 공개 답안지의 마킹 입력 영역">${s.sheetForm.manual?`<div class="omr-paper-heading omr-paper-${s.form.id}"><strong>${escape(F.heading(s.meta))} 답안지</strong><div><b>${['','①','②','③','④','⑤'][s.form.period]}</b><small>교시</small><span ${s.form.id==='language'||s.form.id==='inquiry'?'data-long="true"':''}>${escape(F.displayArea(s.meta,s.form))}</span></div></div>`:`<div class="omr-caption"><small>기출 직행 · 학습용</small><strong>${escape(F.heading(s.meta))}</strong><b>${s.form.period}교시 ${escape(F.displayArea(s.meta,s.form))}</b><span>${escape(s.meta.subject)}</span></div>`}<div class="omr-marks"></div></div></div><div class="omr-current"><strong id="omrCurrent"></strong><div class="omr-answer-controls" aria-label="현재 문항 답안"></div><button id="omrBlank">미응답으로 확인</button><button id="omrNext">다음 문항 →</button></div><div class="omr-flags">${[...s.flags].map(([n,flag])=>`<button data-jump="${n}">${n}번 ${escape(flag)}</button>`).join('')}</div>${s.photoDerived?'<label class="omr-check"><input type="checkbox" id="omrPhotoCheck">원본 사진과 전체 답안을 비교해 확인했습니다.</label><button id="omrOriginal" class="omr-link">보정한 원본 사진 보기</button>':''}<label class="omr-check" id="omrBlankLabel"><input type="checkbox" id="omrBlankCheck">빈 답란은 미응답으로 채점합니다.</label><div class="omr-input-bottom"><button class="omr-link" id="omrMode">입력 방식 바꾸기</button><a href="${s.sheetForm.source||F.source}" target="_blank" rel="noopener">공개 양식 출처 ↗</a></div><p class="omr-note" role="status">${s.key?'정답표와 문항별 배점이 준비되어 있습니다.':'채점하려면 정답·문항별 배점을 먼저 확인해 주세요.'}</p>`;
 const sheet=s.body.querySelector('.omr-sheet'),marks=s.body.querySelector('.omr-marks');
 sheet.style.setProperty('--omr-color',s.sheetForm.color);
 for(const q of questions){
  if(q.kind==='choice')for(const spot of q.spots){const b=document.createElement('button');b.type='button';b.className='omr-bubble';b.dataset.question=q.n;b.dataset.value=spot.value;b.setAttribute('aria-label',q.n+'번 답 '+spot.value+'번');b.style.left=(spot.x/s.sheetForm.width*100)+'%';b.style.top=(spot.y/s.sheetForm.height*100)+'%';b.onclick=()=>change(q.n,s.answers[q.n-1]===spot.value?null:spot.value);marks.append(b);}
  else{
   for(const spot of q.spots){
    if(spot.unprinted)continue;
    const b=document.createElement('button');b.type='button';b.className='omr-bubble omr-digit';
    b.dataset.question=q.n;b.dataset.digit=spot.digit;b.dataset.value=spot.value;
    b.setAttribute('aria-label',q.n+'번 '+places[spot.digit]+'의 자리 '+spot.value);
    b.style.left=spot.x/s.sheetForm.width*100+'%';b.style.top=spot.y/s.sheetForm.height*100+'%';
    b.onclick=()=>markDigit(q.n,spot.digit,spot.value,b);marks.append(b);
   }
  }
 }
 const choose=s.body.querySelector('#omrQuestion');choose.value=s.active;choose.onchange=e=>focusQuestion(+e.target.value);
 s.body.querySelector('#omrWhole').onclick=()=>{s.whole=!s.whole;updateSheet();if(!s.whole)focusQuestion(s.active);};
 s.body.querySelector('#omrKey').onclick=()=>move('key');
 s.body.querySelector('#omrBlank').onclick=()=>change(s.active,null);
 s.body.querySelector('#omrNext').onclick=()=>focusQuestion(Math.min(s.active+1,s.form.count));
 s.body.querySelector('#omrMode').onclick=()=>move('choose');
 s.body.querySelectorAll('[data-jump]').forEach(b=>b.onclick=()=>focusQuestion(+b.dataset.jump));
 const photoCheck=s.body.querySelector('#omrPhotoCheck');if(photoCheck){photoCheck.checked=s.photoChecked;photoCheck.onchange=e=>{s.photoChecked=e.target.checked;updateFooter();};}
 const blankCheck=s.body.querySelector('#omrBlankCheck');blankCheck.checked=s.blankChecked;blankCheck.onchange=e=>{s.blankChecked=e.target.checked;updateFooter();};
 s.body.querySelector('#omrOriginal')?.addEventListener('click',()=>{if(!s.photo){note('원본 사진은 화면을 닫으면 보관하지 않습니다.');return;}const view=document.createElement('dialog');view.className='omr-photo-view';view.innerHTML='<button type="button" aria-label="원본 사진 닫기">닫기</button><div><canvas></canvas></div>';const canvas=view.querySelector('canvas');canvas.width=s.photo.width;canvas.height=s.photo.height;canvas.getContext('2d').putImageData(s.photo,0,0);view.querySelector('button').onclick=()=>view.close();view.addEventListener('close',()=>view.remove());s.dialog.append(view);view.showModal();});
 if(window.ResizeObserver){s.sheetObserver=new ResizeObserver(s.resize);s.sheetObserver.observe(s.body.querySelector('.omr-sheet-scroll'));}updateSheet();updateInput();requestAnimationFrame(()=>{if(current===s&&s.stage==='input')focusQuestion(s.active);});
}
function updateSheet(){
 const s=current,sheet=s?.body.querySelector('.omr-sheet');if(!sheet)return;const scroll=s.body.querySelector('.omr-sheet-scroll'),f=s.sheetForm;
 s.zoom=s.whole?Math.max(.05,Math.min(scroll.clientWidth/f.width,s.wide?scroll.clientHeight/f.height:1)):1.55;
 sheet.style.width=f.width*s.zoom+'px';sheet.style.height=f.height*s.zoom+'px';sheet.style.setProperty('--omr-zoom',s.zoom);
 sheet.classList.toggle('omr-overview',s.whole&&!s.wide);sheet.classList.toggle('omr-full-input',s.whole&&s.wide);
 scroll.classList.toggle('omr-fitted',s.whole&&s.wide);
 s.body.querySelector('#omrWhole').textContent=s.whole?'답란 확대':'전체 양식';
}
function focusQuestion(n){
 const s=current;s.active=n;s.body.querySelector('#omrQuestion').value=n;
 if(s.whole&&!s.wide){s.whole=false;updateSheet();}
 if(!s.whole){
  const q=F.questions(s.sheetForm,s.slot)[n-1],spot=q.spots[0],scroll=s.body.querySelector('.omr-sheet-scroll');
  const centerX=q.kind==='choice'?(q.spots[0].x+q.spots[4].x)/2:spot.x+32,centerY=q.kind==='choice'?spot.y:spot.y+160;
  scroll.scrollLeft=centerX*s.zoom-scroll.clientWidth/2;scroll.scrollTop=centerY*s.zoom-(q.kind==='choice'?70:scroll.clientHeight/2);
 }
 updateCurrent();
}
function updateCurrent(){
 const s=current,node=s.body.querySelector('#omrCurrent');if(!node)return;const q=F.questions(s.sheetForm,s.slot)[s.active-1],answer=s.answers[s.active-1];
 node.textContent=s.active+'번 · '+(s.flags.get(s.active)||(answer===null?'미응답':answer+(q.kind==='number'?' → 숫자 답':'번 선택')));
 s.body.querySelector('#omrQuestion').value=s.active;
 const controls=s.body.querySelector('.omr-answer-controls');controls.classList.toggle('omr-numeric-controls',q.kind==='number');controls.replaceChildren();
 for(const value of q.kind==='choice'?[1,2,3,4,5]:['숫자 답란 확대']){
  const b=document.createElement('button');b.type='button';b.textContent=value;b.dataset.answer=value;
  b.setAttribute('aria-label',s.active+'번 '+(q.kind==='choice'?'답 '+value+'번':'숫자 답란 확대'));
  if(q.kind==='choice')b.setAttribute('aria-pressed',String(value===answer));
  b.onclick=()=>{const n=s.active;if(q.kind==='number')numberPad(n);else{change(n,answer===value?null:value);s.body.querySelector('.omr-answer-controls [data-answer="'+value+'"]').focus({preventScroll:true});}};
  controls.append(b);
 }
}
function change(n,value){
 const s=current;s.answers[n-1]=value;if(F.questions(s.form,s.slot)[n-1].kind==='number')s.numberMarks[n]=digitsOf(value);s.flags.delete(n);s.active=n;s.photoChecked=false;s.blankChecked=false;saveDraft();updateInput();
 const b=s.body.querySelector('.omr-bubble:not(.omr-digit)[data-question="'+n+'"][data-value="'+value+'"]');b?.focus({preventScroll:true});live(n+'번 '+(value===null?'미응답으로 확인했습니다':value+' 답을 입력했습니다'));
}
function markDigit(n,digit,value,button){
 const s=current,digits=s.numberMarks[n];digits[digit]=digits[digit]===value?null:value;
 const got=numberAnswer(digits);s.answers[n-1]=got.value;s.flags.delete(n);
 if(got.partial)s.flags.set(n,'숫자 마킹 미완성');
 s.active=n;s.photoChecked=false;s.blankChecked=false;saveDraft();updateInput();button.focus({preventScroll:true});
 live(n+'번 '+places[digit]+'의 자리 '+(digits[digit]===null?'비움':digits[digit])+(got.partial?' · 나머지 자릿수를 확인해 주세요':''));
}
function updateInput(){
 const s=current;
 s.body.querySelectorAll('.omr-bubble').forEach(b=>{
  const n=+b.dataset.question,value=+b.dataset.value;
  const chosen=b.classList.contains('omr-digit')?s.numberMarks[n]?.[+b.dataset.digit]===value:s.answers[n-1]===value;
  b.setAttribute('aria-pressed',String(chosen));
 });
 s.body.querySelector('.omr-progress span').textContent=s.answers.filter(v=>v!==null).length+'/'+s.form.count+'문항 입력';
 s.body.querySelector('#omrPending').textContent=s.flags.size?'확인 '+s.flags.size+'개 남음':'답란을 다시 누르면 지웁니다';
 const flags=s.body.querySelector('.omr-flags');flags.replaceChildren();
 for(const [n,flag] of s.flags){const b=document.createElement('button');b.type='button';b.textContent=n+'번 '+flag;b.onclick=()=>focusQuestion(n);flags.append(b);}
 const photo=s.body.querySelector('#omrPhotoCheck');if(photo)photo.checked=s.photoChecked;
 const blank=s.body.querySelector('#omrBlankCheck');blank.checked=s.blankChecked;s.body.querySelector('#omrBlankLabel').hidden=!s.answers.includes(null);
 updateCurrent();updateFooter();
}
function updateFooter(){
 const s=current;
 if(!s.key){primary('정답·배점 입력하기',()=>move('key'));return;}
 const invalid=validateKey(s.key.answers,s.key.points,s.form,F.questions(s.form,s.slot));
 const blocked=!!invalid||s.flags.size>0||(s.photoDerived&&!s.photoChecked)||(s.answers.includes(null)&&!s.blankChecked);
 primary(blocked?'답안 확인 후 채점하기':'채점 결과 보기',()=>move('result'),blocked);
}
function numberPad(n){
 const s=current,digits=[...s.numberMarks[n]],dialog=document.createElement('dialog');dialog.className='omr-number-pad';
 dialog.innerHTML=`<header><h2>${n}번 숫자 답</h2><button type="button" aria-label="숫자 입력 닫기">✕</button></header><p>자릿수별로 눌러 입력합니다. 빈칸과 0은 다릅니다.</p><div class="omr-digit-grid">${places.map((name,d)=>`<div><strong>${name}</strong>${Array.from({length:10},(_,v)=>`<button type="button" data-digit="${d}" data-value="${v}" ${d===0&&v===0&&s.sheetForm.manual?'disabled':''} aria-label="${name}의 자리 ${v}">${v}</button>`).join('')}<button type="button" data-digit="${d}" data-empty="true" aria-label="${name}의 자리 비우기">비움</button></div>`).join('')}</div><p class="omr-number-result" role="status"></p><button type="button" class="omr-primary" id="omrNumberDone">답안에 반영</button>`;
 function refresh(){dialog.querySelectorAll('[data-digit]').forEach(b=>b.setAttribute('aria-pressed',digits[+b.dataset.digit]===(b.dataset.empty?null:+b.dataset.value)));dialog.querySelector('.omr-number-result').textContent=digits.map(v=>v===null?'—':v).join(' · ');dialog.querySelector('#omrNumberDone').disabled=numberAnswer(digits).partial;}
 dialog.querySelector('header button').onclick=()=>dialog.close();dialog.querySelectorAll('[data-digit]').forEach(b=>b.onclick=()=>{const d=+b.dataset.digit,v=b.dataset.empty?null:+b.dataset.value;digits[d]=digits[d]===v?null:v;refresh();});dialog.querySelector('#omrNumberDone').onclick=()=>{const v=numberAnswer(digits).value;dialog.close();change(n,v);s.numberMarks[n]=[...digits];saveDraft();updateInput();};dialog.addEventListener('close',()=>{dialog.remove();s.body.querySelector('.omr-digit[data-question="'+n+'"][data-digit="2"]')?.focus({preventScroll:true});});s.dialog.append(dialog);dialog.showModal();refresh();
}
function keyEditor(){
 const s=current,knownPoints=F.pointsFor(s.meta,s.form);
 s.body.innerHTML=`<p class="omr-kicker">ANSWER KEY</p><h1>정답과 배점을 확인합니다.</h1>${info()}<p>${s.key?escape(s.key.source||'직접 확인한 정답표'):'이 회차에는 확인된 정답표가 없습니다. 정답지와 문제지의 배점을 보고 입력해 주세요.'}</p><div class="omr-input-bottom">${s.meta.answerURL?`<a href="${escape(s.meta.answerURL)}" target="_blank" rel="noopener">정답지 열기 ↗</a>`:''}${s.meta.problemURL?`<a href="${escape(s.meta.problemURL)}" target="_blank" rel="noopener">문제지 배점 확인 ↗</a>`:''}</div>${knownPoints?`<p class="omr-points-source">${escape(knownPoints.source)}</p>`:''}<form id="omrKeyForm"><label class="omr-field">정답 · 문항 순서대로<textarea id="omrKeyAnswers" rows="5" inputmode="numeric" aria-label="문항별 정답" placeholder="문항 순서대로 공백 또는 쉼표로 구분"></textarea></label><label class="omr-field">문항별 배점 · 합계 ${s.form.maximum}점<textarea id="omrKeyPoints" rows="5" inputmode="numeric" aria-label="문항별 배점" placeholder="문제지에 표시된 정수 배점"></textarea></label><label class="omr-check"><input type="checkbox" id="omrKeyCheck">${escape(s.meta.subject)}의 시험명·홀짝형·선택과목과 정답·배점이 일치합니다.</label><p class="omr-note" role="alert"></p></form><button id="omrKeyBack" class="omr-link">답안 입력으로 돌아가기</button>`;
 if(s.key)s.body.querySelector('#omrKeyAnswers').value=s.key.answers.join(' ');
 if(s.key||knownPoints)s.body.querySelector('#omrKeyPoints').value=(s.key?.points||knownPoints.points).join(' ');
 s.body.querySelector('#omrKeyBack').onclick=()=>move('input');
 function parse(id){const raw=s.body.querySelector(id).value.trim();if(raw.length>10000||!/^\d+(?:[\s,]+\d+)*$/.test(raw))return [];return raw.split(/[\s,]+/).map(Number);}
 primary('확인한 정답표 적용',()=>{
  const answers=parse('#omrKeyAnswers'),points=parse('#omrKeyPoints'),error=validateKey(answers,points,s.form,F.questions(s.form,s.slot));
  if(error){note(error);return;}if(!s.body.querySelector('#omrKeyCheck').checked){note('시험지 유형과 정답·배점을 확인해 주세요.');return;}
  s.key={answers,points,source:'직접 확인한 정답표'};saveDraft();move('input');
 });
}
function result(){
 const s=current;
 if(!s.key||validateKey(s.key.answers,s.key.points,s.form,F.questions(s.form,s.slot))||s.flags.size||(s.photoDerived&&!s.photoChecked)||(s.answers.includes(null)&&!s.blankChecked)){move('input');return;}
 const got=grade(s.answers,s.key),blank=s.answers.filter(v=>v===null).length;
 s.body.innerHTML=`<p class="omr-kicker">YOUR RESULT</p><h1>점수와 오답을 확인해 주세요.</h1>${info()}<div class="omr-score"><small>원점수</small><strong>${got.score}<span> / ${s.form.maximum}점</span></strong><div><span>정답 <b>${s.form.count-got.wrong.length}</b></span><span>오답 <b>${got.wrong.length-blank}</b></span><span>미응답 <b>${blank}</b></span></div></div><h2>다시 볼 문제</h2><div class="omr-wrong">${got.wrong.map(n=>`<button type="button" data-wrong="${n}"><strong>${n}번</strong><span>${s.answers[n-1]??'미응답'} → ${s.key.answers[n-1]}</span><small>${s.key.points[n-1]}점 문항</small></button>`).join('')||'<p>모든 답이 맞았습니다.</p>'}</div><p>점수와 틀린 번호를 풀이 기록에 반영합니다.<br>기존 푼 날과 풀이시간은 이어갑니다.</p><button class="omr-link" id="omrRevise">답안 다시 확인</button><p class="omr-note" role="status"></p>`;
 s.body.querySelectorAll('[data-wrong]').forEach(b=>b.onclick=()=>{s.active=+b.dataset.wrong;move('input');});s.body.querySelector('#omrRevise').onclick=()=>move('input');
 primary(s.options.demo?'예시 기록 화면 보기':'점수·틀린 번호 기록',async()=>{
  const button=s.footer.querySelector('button');button.disabled=true;
  try{if(!s.options.demo&&typeof s.options.save!=='function')throw new Error('저장 경로 없음');const saved=await s.options.save?.(got);if(current!==s)return;if(saved===false){button.disabled=false;note('기록 저장을 완료하지 못했습니다. 다시 시도해 주세요.');return;}
   s.body.innerHTML=`<div class="omr-saved"><span>기록</span><h1>${s.options.demo?'이렇게 기록됩니다.':'풀이 기록에 반영했습니다.'}</h1><p>${escape(s.meta.subject)} · ${got.score}점<br>틀린 번호 ${got.wrong.join(', ')||'없음'}</p>${s.options.demo?'<p>체험 화면에서는 앱 기록을 저장하지 않습니다.</p>':''}</div>`;primary('닫기',close);
  }catch(e){if(current===s){button.disabled=false;note('기록을 저장하지 못했습니다. 다시 시도해 주세요.');}}
 });
}
window.GijulOMR=Object.freeze({open,close,closeIfOpen:back,validateKey,grade,loadReference});
})();
