'use strict';
const subjects={inquiry:['생명과학Ⅰ','158','과학탐구'],korean:['언어와 매체','140118','국어'],math:['미적분','140120','수학'],english:['영어','80003','영어'],history:['한국사','63004','한국사'],language:['일본어Ⅰ','195','제2외국어·한문']};
document.querySelector('#start').onclick=()=>{
 const family=document.querySelector('#subject').value,[subject,subjectId,group]=subjects[family],exam=document.querySelector('#exam').value;
 const [date,title]=({gov:['20260902','9월 모평(평가원)'],m6:['20250604','6월 모평(평가원)'],csat:['20251113','수능 홀수형'],edu:['20260708','7월 학평(인천)']})[exam];
 const meta={grade:'D300',subject,subjectId,group,date,title,answerURL:family==='inquiry'&&exam==='gov'?'https://wdown.ebsi.co.kr/W61001/01exam/20260902/mobile/h3_m_g_bio1_ans_45HY71KP.png':'',problemURL:''};
 GijulOMR.open(meta,{demo:true});
};
document.querySelector('#dark').onclick=()=>document.body.classList.toggle('dark');
