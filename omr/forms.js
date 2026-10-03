/* Coordinates in the unmodified GOE-published 2026 CSAT specimen, rendered at 1800×1406.
   Answer positions are separate from the legacy progress key (which merges odd/even forms). */
(function(){
'use strict';
const base = new URL('.', document.currentScript.src).href;
const forms = {};
function multiple(form, first, last, x, y){
  for(let n=first;n<=last;n++) form.questions[n-1]={n,kind:'choice',spots:Array.from({length:5},(_,v)=>({x:x+v*31.58,y:y+(n-first)*52.63,value:v+1}))};
}
function form(id,area,period,count,maximum,color){return forms[id]={id,area,period,count,maximum,color,width:1800,height:1406,image:base+'templates/'+id+'.webp',questions:[]};}
let f=form('korean','국어 영역',1,45,100,'#36ba84');
multiple(f,1,20,772,260.5);multiple(f,21,34,994.5,260.5);multiple(f,35,45,1388.5,260.5);
f=form('english','영어 영역',3,45,100,'#00aeef');
multiple(f,1,20,758,260.5);multiple(f,21,40,1105.5,260.5);multiple(f,41,45,1453,260.5);
f=form('inquiry','탐구 영역',4,20,50,'#1d4e9d');
multiple(f,1,20,756,260.5);
f.secondQuestions=[];
for(let n=1;n<=20;n++) f.secondQuestions.push({n,kind:'choice',spots:Array.from({length:5},(_,v)=>({x:1466.5+v*31.58,y:260.5+(n-1)*52.63,value:v+1}))});
f=form('history','한국사 영역',4,20,50,'#552d99');multiple(f,1,20,819,260.5);
f=form('language','제2외국어/한문 영역',5,30,50,'#ff6b30');multiple(f,1,20,758,260.5);multiple(f,21,30,1137,260.5);
f=form('math','수학 영역',2,30,100,'#ec008c');
multiple(f,1,10,655,233.5);multiple(f,11,15,876,233.5);multiple(f,23,28,1271,839.5);
const numeric=[[16,1453,233.5],[17,1579,233.5],[18,592,839.5],[19,718,839.5],[20,844.5,839.5],[21,971,839.5],[22,1097,839.5],[29,1453,839.5],[30,1579,839.5]];
for(const [n,x,y] of numeric)f.questions[n-1]={n,kind:'number',spots:Array.from({length:30},(_,i)=>({x:x+Math.floor(i/10)*31.58,y:y+(i%10)*52.63,digit:Math.floor(i/10),value:i%10}))};
function resolve(meta){
  if(meta.grade!=='D300'||!/^20\d{6}$/.test(meta.date)||+meta.date.slice(0,4)<2021)return null;
  const s=meta.subject,g=meta.group||'';
  if(['국어','화법과 작문','언어와 매체'].includes(s))return forms.korean;
  if(['수학','확률과 통계','미적분','기하'].includes(s))return forms.math;
  if(s==='영어')return forms.english;
  if(s==='한국사')return forms.history;
  if(/제2외국어|한문/.test(g))return forms.language;
  if(/탐구/.test(g))return forms.inquiry;
  return null;
}
function exactKey(meta){return JSON.stringify([meta.grade,meta.subjectId,meta.date,meta.title,meta.answerURL||'']);}
function heading(meta){const gov=/수능|평가원/.test(meta.title),year=+meta.date.slice(0,4);return (gov?(year+1)+'학년도':year+'년')+' '+meta.title;}
function displayArea(meta,form){return form.id==='inquiry'&&/^(사회|과학|직업)탐구$/.test(meta.group)?meta.group+' 영역':form.area;}
function questions(form,slot){return form.id==='inquiry'&&slot===2?form.secondQuestions:form.questions;}
const keys={};
keys[JSON.stringify(['D300','158','20260902','9월 모평(평가원)','https://wdown.ebsi.co.kr/W61001/01exam/20260902/mobile/h3_m_g_bio1_ans_45HY71KP.png'])]={
 answers:[5,3,5,4,3,3,5,1,1,2,4,1,3,2,2,5,4,2,3,1],
 points:[2,3,2,2,3,2,3,2,2,2,3,2,3,3,3,2,2,3,3,3],
 source:'문제·정답·해설을 대조한 정답표'
};
window.GijulOmrForms=Object.freeze({base,forms,resolve,exactKey,heading,displayArea,questions,keys,source:'https://www.goe.go.kr/goe/na/ntt/selectNttInfo.do?mi=10961&nttSn=2330309'});
})();
