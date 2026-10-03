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
/* Unmodified high-resolution fronts extracted from the official 2027 September
   guide HWP, BinData/BIN0002.jpg–BIN0007.jpg. Separate from photo references. */
const manualSource='https://gcja-h.goeay.kr/gcja-h/na/ntt/selectNttInfo.do?bbsId=2506&mi=5763&nttSn=1329024';
const manualForms={};
function manual(id,nativeWidth=3420){const old=forms[id];return manualForms[id]={...old,manual:true,source:manualSource,nativeWidth,nativeHeight:2683,height:2683*1800/nativeWidth,image:base+'templates/manual/'+id+'.webp',questions:[]};}
function choices(f,first,last,x,y,dx=60,dy=100){
 const scale=1800/f.nativeWidth;
 for(let n=first;n<=last;n++)f.questions[n-1]={n,kind:'choice',spots:Array.from({length:5},(_,v)=>({x:(x+v*dx)*scale,y:(y+(n-first)*dy)*scale,value:v+1}))};
}
let m=manual('korean');m.color='#2bb395';choices(m,1,20,1994.5,497.5);choices(m,21,34,2414.5,497.5);choices(m,35,45,2924.5,497.5);
m=manual('english');m.color='#00afe0';choices(m,1,20,1994.5,497.5);choices(m,21,40,2459.5,497.5);choices(m,41,45,2924.5,497.5);
m=manual('history');m.color='#68429a';choices(m,1,20,2234.5,497.5);
m=manual('inquiry',3447);m.color='#215b96';choices(m,1,20,2181,447);
const second={nativeWidth:m.nativeWidth,questions:[]};choices(second,1,20,2961,447);m.secondQuestions=second.questions;
m=manual('language');m.color='#fa8750';choices(m,1,20,2339.5,497.5);choices(m,21,30,2864.5,497.5);
m=manual('math');m.color='#ed258f';choices(m,1,8,1199.5,447);choices(m,9,15,1619.5,447);choices(m,23,28,2504.5,1597);
for(const [n,x,y] of [[16,2174.5,447],[17,2384.5,447],[18,2624.5,447],[19,2849.5,447],[20,3074.5,447],[21,1964.5,1597],[22,2174.5,1597],[29,2849.5,1597],[30,3074.5,1597]])
 m.questions[n-1]={n,kind:'number',spots:Array.from({length:30},(_,i)=>({x:(x+Math.floor(i/10)*60)*1800/m.nativeWidth,y:(y+(i%10)*100)*1800/m.nativeWidth,digit:Math.floor(i/10),value:i%10,unprinted:i===0}))};
/* Number-by-number scoring is stable for the checked 2021–2026 math format.
   Other subjects require exact exam identity; see points-reviewed.json and docs. */
const mathPoints=Object.freeze([2,2,3,3,3,3,3,3,4,4,4,4,4,4,4,3,3,3,3,4,4,4,2,3,3,3,3,4,4,4]);
const reviewedPoints={"[\"D300\",\"80003\",\"20260902\",\"9월 모평(평가원)\",\"https://wdown.ebsi.co.kr/W61001/01exam/20260902/mobile/h3_m_eng_1_ans_J9Z21QZR.png\"]":{"points":[2,2,2,2,2,2,2,2,2,2,2,3,3,2,3,2,2,2,2,2,3,2,2,2,2,2,2,2,2,3,2,2,3,3,2,2,3,2,3,2,2,3,2,2,2],"problemURL":"https://wdown.ebsi.co.kr/W61001/01exam/20260902/go3/eng_1_mun_9788G389.pdf"},"[\"D300\",\"80003\",\"20251113\",\"수능 홀수형\",\"https://wdown.ebsi.co.kr/W61001/01exam/20251113/mobile/h3_m_eng_1_ans_UP5L2L99.png\"]":{"points":[2,2,2,2,2,2,2,2,2,2,2,3,3,3,2,2,2,2,2,2,2,2,2,3,2,2,2,2,2,3,2,3,2,3,2,2,3,2,3,2,3,2,2,2,2],"problemURL":"https://wdown.ebsi.co.kr/W61001/01exam/20251113/go3/eng_1_mun_9VSFX7CB.pdf"},"[\"D300\",\"80003\",\"20250604\",\"6월 모평(평가원)\",\"https://wdown.ebsi.co.kr/W61001/01exam/20250604/mobile/h3_m_eng_1_ans_9W81DUYU.png\"]":{"points":[2,2,2,2,2,2,2,2,2,2,2,3,2,3,3,2,2,2,2,2,3,2,2,2,2,2,2,2,2,3,2,3,2,3,2,2,3,2,3,2,2,3,2,2,2],"problemURL":"https://wdown.ebsi.co.kr/W61001/01exam/20250604/go3/eng_1_mun_B6TBU193.pdf"},"[\"D300\",\"63004\",\"20260902\",\"9월 모평(평가원)\",\"https://wdown.ebsi.co.kr/W61001/01exam/20260902/mobile/h3_m_s_his_1_ans_Q874M5F1.png\"]":{"points":[2,3,3,2,2,2,3,3,2,2,3,2,3,2,3,3,2,3,3,2],"problemURL":"https://wdown.ebsi.co.kr/W61001/01exam/20260902/go3/s_his_1_mun_67AW5BV8.pdf"},"[\"D300\",\"63004\",\"20251113\",\"수능 홀수형\",\"https://wdown.ebsi.co.kr/W61001/01exam/20251113/mobile/h3_m_s_his_1_ans_RFAX4MR9.png\"]":{"points":[2,2,3,2,3,2,3,2,3,3,3,2,2,2,3,2,3,3,2,3],"problemURL":"https://wdown.ebsi.co.kr/W61001/01exam/20251113/go3/s_his_1_mun_A3F3636G.pdf"},"[\"D300\",\"63004\",\"20250604\",\"6월 모평(평가원)\",\"https://wdown.ebsi.co.kr/W61001/01exam/20250604/mobile/h3_m_s_his_1_ans_36OO3JH6.png\"]":{"points":[2,3,2,3,2,2,3,3,2,3,3,2,3,2,3,2,3,3,2,2],"problemURL":"https://wdown.ebsi.co.kr/W61001/01exam/20250604/go3/s_his_1_mun_62236256.pdf"},"[\"D300\",\"140117\",\"20260902\",\"9월 모평(평가원)\",\"https://wdown.ebsi.co.kr/W61001/01exam/20260902/mobile/h3_m_korA_1_ans_1367Y35Z.png\"]":{"points":[2,2,3,2,2,2,2,3,2,2,2,2,3,2,2,3,2,2,2,2,3,2,2,3,2,2,2,2,2,2,3,2,2,3,2,2,2,2,2,3,2,2,2,2,3],"problemURL":"https://wdown.ebsi.co.kr/W61001/01exam/20260902/go3/korA_1_mun_BHW12OQT.pdf"},"[\"D300\",\"140117\",\"20251113\",\"수능 홀수형\",\"https://wdown.ebsi.co.kr/W61001/01exam/20251113/mobile/h3_m_korA_1_ans_5UAM3UO5.png\"]":{"points":[2,2,3,2,2,2,2,3,2,2,2,3,2,2,2,2,3,2,2,2,3,2,3,2,2,2,2,2,2,3,2,2,2,3,2,2,2,2,2,3,2,2,2,2,3],"problemURL":"https://wdown.ebsi.co.kr/W61001/01exam/20251113/go3/korA_1_mun_3BN8E6DF.pdf"},"[\"D300\",\"140117\",\"20250604\",\"6월 모평(평가원)\",\"https://wdown.ebsi.co.kr/W61001/01exam/20250604/mobile/h3_m_korA_1_ans_FSJUKDES.png\"]":{"points":[2,2,3,2,2,2,2,3,2,2,2,3,2,2,2,2,3,2,2,2,3,2,2,2,2,3,2,2,2,3,2,2,2,3,2,2,2,2,2,3,2,2,2,2,3],"problemURL":"https://wdown.ebsi.co.kr/W61001/01exam/20250604/go3/korA_1_mun_N8NYU3TH_3.pdf"},"[\"D300\",\"158\",\"20260902\",\"9월 모평(평가원)\",\"https://wdown.ebsi.co.kr/W61001/01exam/20260902/mobile/h3_m_g_bio1_ans_45HY71KP.png\"]":{"points":[2,3,2,2,3,2,3,2,2,2,3,2,3,3,3,2,2,3,3,3],"problemURL":"https://wdown.ebsi.co.kr/W61001/01exam/20260902/go3/g_bio1_mun_DE4O4J64.pdf"},"[\"D300\",\"158\",\"20251113\",\"수능\",\"https://wdown.ebsi.co.kr/W61001/01exam/20251113/mobile/h3_m_g_bio1_ans_K9P5481L.png\"]":{"points":[2,2,3,3,2,2,2,2,2,3,3,3,2,3,3,2,3,2,3,3],"problemURL":"https://wdown.ebsi.co.kr/W61001/01exam/20251113/go3/g_bio1_mun_7V3IGX46.pdf"},"[\"D300\",\"158\",\"20250604\",\"6월 모평(평가원)\",\"https://wdown.ebsi.co.kr/W61001/01exam/20250604/mobile/h3_m_g_bio1_ans_A59U942Y.png\"]":{"points":[2,3,2,2,2,3,2,3,3,2,2,3,3,2,2,3,3,2,3,3],"problemURL":"https://wdown.ebsi.co.kr/W61001/01exam/20250604/go3/g_bio1_mun_P1T4GAQ4.pdf"},"[\"D300\",\"191\",\"20260902\",\"9월 모평(평가원)\",\"https://wdown.ebsi.co.kr/W61001/01exam/20260902/mobile/h3_m_2nd_gr_ans_8X9R2ET7.png\"]":{"points":[2,1,1,2,2,2,1,1,1,2,2,1,2,1,1,2,2,2,2,2,2,2,2,2,2,1,2,1,2,2],"problemURL":"https://wdown.ebsi.co.kr/W61001/01exam/20260902/go3/2nd_gr_mun_7T3W64P4.pdf"},"[\"D300\",\"191\",\"20251113\",\"수능\",\"https://wdown.ebsi.co.kr/W61001/01exam/20251113/mobile/h3_m_2nd_gr_ans_677PC97A.png\"]":{"points":[1,2,1,2,2,1,1,2,2,2,1,2,2,1,2,2,2,2,2,2,1,2,2,1,1,2,1,2,2,2],"problemURL":"https://wdown.ebsi.co.kr/W61001/01exam/20251113/go3/2nd_gr_mun_H2RY447N.pdf"},"[\"D300\",\"191\",\"20250604\",\"6월 모평(평가원)\",\"https://wdown.ebsi.co.kr/W61001/01exam/20250604/mobile/h3_m_2nd_gr_ans_44UKK587.png\"]":{"points":[1,2,1,2,2,1,2,1,1,2,2,2,2,2,1,2,1,1,2,2,2,2,2,2,1,2,2,1,2,2],"problemURL":"https://wdown.ebsi.co.kr/W61001/01exam/20250604/go3/2nd_gr_mun_4543A8FQ.pdf"},"[\"D300\",\"195\",\"20260902\",\"9월 모평(평가원)\",\"https://wdown.ebsi.co.kr/W61001/01exam/20260902/mobile/h3_m_2nd_ja_ans_691FHE1E.png\"]":{"points":[1,2,2,2,2,1,2,1,2,2,1,1,1,1,2,2,2,2,1,2,2,1,2,2,2,2,1,2,2,2],"problemURL":"https://wdown.ebsi.co.kr/W61001/01exam/20260902/go3/2nd_ja_mun_68468492.pdf"},"[\"D300\",\"195\",\"20251113\",\"수능\",\"https://wdown.ebsi.co.kr/W61001/01exam/20251113/mobile/h3_m_2nd_ja_ans_Q2DCL4KO.png\"]":{"points":[1,2,2,2,2,1,2,1,2,2,1,1,2,1,2,2,2,2,1,2,2,1,2,2,2,1,1,2,2,2],"problemURL":"https://wdown.ebsi.co.kr/W61001/01exam/20251113/go3/2nd_ja_mun_BI892H76.pdf"},"[\"D300\",\"195\",\"20250604\",\"6월 모평(평가원)\",\"https://wdown.ebsi.co.kr/W61001/01exam/20250604/mobile/h3_m_2nd_ja_ans_5QH8Y665.png\"]":{"points":[1,2,2,2,2,1,2,1,2,2,2,2,2,1,2,1,1,1,2,1,2,2,2,2,2,1,2,2,1,2],"problemURL":"https://wdown.ebsi.co.kr/W61001/01exam/20250604/go3/2nd_ja_mun_B345FJ64.pdf"}};
function pointsFor(meta,form){
 const exact=reviewedPoints[exactKey(meta)];
 if(exact&&meta.problemURL===exact.problemURL&&exact.points.length===form.count&&exact.points.reduce((a,b)=>a+b,0)===form.maximum)return {points:[...exact.points],source:'이 회차의 원본 문제지에서 대조한 배점'};
 if(form.id==='math'&&meta.grade==='D300'&&['140119','140120','140121'].includes(meta.subjectId)&&+meta.date.slice(0,4)>=2021&&+meta.date.slice(0,4)<=2026&&/수능|평가원|학평/.test(meta.title))return {points:[...mathPoints],source:'2021~2026년 시행 수학 공통·선택 배점 · 문제지와 확인해 주세요'};
 return null;
}
const keys={};
keys[JSON.stringify(['D300','158','20260902','9월 모평(평가원)','https://wdown.ebsi.co.kr/W61001/01exam/20260902/mobile/h3_m_g_bio1_ans_45HY71KP.png'])]={
 answers:[5,3,5,4,3,3,5,1,1,2,4,1,3,2,2,5,4,2,3,1],
 points:[2,3,2,2,3,2,3,2,2,2,3,2,3,3,3,2,2,3,3,3],
 source:'문제·정답·해설을 대조한 정답표'
};
window.GijulOmrForms=Object.freeze({base,forms,resolve,exactKey,heading,displayArea,questions,keys,pointsFor,manualForms,manualSource,source:'https://www.goe.go.kr/goe/na/ntt/selectNttInfo.do?mi=10961&nttSn=2330309'});
})();
