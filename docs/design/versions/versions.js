'use strict';
const list=document.querySelector('#list'),status=document.querySelector('#status');
let rows=[],symbols=false,loadId=0;
const subjects={'140118':['언어와 매체','국어'],'140120':['미적분','수학'],'80003':['영어','영어'],'158':['생명과학Ⅰ','과학탐구'],'63004':['한국사','한국사']};
function metaFor(paper){const id=document.querySelector('#subject').value,[subject,group]=subjects[id];return {grade:'D300',subjectId:id,subject,group,date:paper.date.replaceAll('-',''),title:paper.title,answerURL:paper.answer||'',problemURL:paper.problem||''};}
function panel(title,opener){
 const d=document.createElement('dialog');d.className='preview-dialog';d.setAttribute('aria-label',title);
 d.innerHTML='<header><h2></h2><button type="button" class="panel-close" aria-label="닫기">✕</button></header><div class="panel-content"></div>';
 d.querySelector('h2').textContent=title;d.querySelector('.panel-close').onclick=()=>d.close();
 d.addEventListener('close',()=>{d.remove();(opener.isConnected?opener:document.querySelector('#subject')).focus({preventScroll:true});});document.body.append(d);d.showModal();return d;
}
function record(row,paper,opener){
 const meta=metaFor(paper),f=GijulOmrForms.resolve(meta),d=panel('풀이 기록',opener),content=d.querySelector('.panel-content'),r=row.record||{};
 const sub=document.createElement('p');sub.textContent=GijulOmrForms.heading(meta)+' · '+meta.subject;content.append(sub);
 const form=document.createElement('form');form.innerHTML='<fieldset><legend>풀이시간</legend><div class="time-input"><input id="minutes" type="number" min="0" max="99999" step="1" inputmode="numeric" aria-label="풀이시간 분"><span>분</span><input id="seconds" type="number" min="0" max="59" step="1" inputmode="numeric" aria-label="풀이시간 초"><span>초</span></div></fieldset><label>점수<input id="score" type="number" min="0" max="'+f.maximum+'" step="1" inputmode="numeric" placeholder="0~'+f.maximum+'"></label><label>틀린 문제 번호<input id="wrong" type="text" placeholder="예: 3, 7, 12-14"><small>쉼표나 공백으로 구분 · 모두 맞았으면 없음</small></label><p class="error" role="alert"></p><button type="button" class="enter-omr">답안 입력·채점</button><button class="save" type="submit">시안에 표시</button><p>이 화면의 기록은 앱과 동기화에 저장하지 않습니다.</p>';
 content.append(form);if(r.spent){form.querySelector('#minutes').value=Math.floor(r.spent/60);form.querySelector('#seconds').value=r.spent%60;}
 if(r.score!==undefined)form.querySelector('#score').value=r.score;if(r.wrong)form.querySelector('#wrong').value=r.wrong.length?r.wrong.join(', '):'없음';
 form.querySelector('.enter-omr').onclick=()=>{d.close();d.remove();GijulOMR.open(meta,{demo:true,save:got=>{row.record={...row.record,...got};row.solved=true;render();},onClose:()=>list.querySelector('[data-exam="'+row.id+'"] .record')?.focus({preventScroll:true})});};
 form.onsubmit=e=>{
  e.preventDefault();const error=form.querySelector('.error'),score=form.querySelector('#score'),raw=form.querySelector('#wrong').value.trim(),wrong=[];error.textContent='';
  if(score.value!==''&&!Number.isInteger(score.valueAsNumber)){error.textContent='점수는 정수로 적어 주세요.';return;}
  if(raw&&raw!=='없음'){
   if(!/^\d+(?:\s*-\s*\d+)?(?:[\s,]+\d+(?:\s*-\s*\d+)?)*$/.test(raw)){error.textContent='틀린 번호를 확인해 주세요.';return;}
   for(const match of raw.matchAll(/(\d+)(?:\s*-\s*(\d+))?/g)){const a=+match[1],b=+(match[2]||match[1]);if(a<1||b<a||b>f.count){error.textContent='문제 번호는 1~'+f.count+' 사이로 적어 주세요.';return;}for(let n=a;n<=b;n++)wrong.push(n);}
  }
  const minutes=form.querySelector('#minutes'),seconds=form.querySelector('#seconds'),hasTime=minutes.value!==''||seconds.value!=='';const spent=+minutes.value*60+(+seconds.value);
  if(hasTime&&spent<=0){error.textContent='풀이시간은 0초보다 길게 적어 주세요.';return;}
  row.record={};if(score.value!=='')row.record.score=score.valueAsNumber;if(raw)row.record.wrong=[...new Set(wrong)].sort((a,b)=>a-b);if(hasTime)row.record.spent=spent;
  if(Object.keys(row.record).length)row.solved=true;render();d.close();list.querySelector('[data-exam="'+row.id+'"] .record').focus({preventScroll:true});status.textContent='시안에 풀이 기록을 표시했습니다.';
 };
}
function send(paper,opener){
 const meta=metaFor(paper),d=panel('보내기',opener),content=d.querySelector('.panel-content'),title=document.createElement('p');title.textContent=GijulOmrForms.heading(meta)+' · '+meta.subject;content.append(title);
 const hint=document.createElement('p');hint.textContent='현재 유형의 자료를 선택합니다. 시안에서는 원본 파일을 새 창으로 엽니다.';content.append(hint);
 for(const [key,label] of [['problem','문제'],['answer','정답'],['solution','해설']])if(paper[key]){const a=document.createElement('a');a.textContent=label+' ↗';a.href=paper[key];a.target='_blank';a.rel='noopener';content.append(a);}
}
function render(){
 const heading=document.createElement('div');heading.className='yr-head';
 heading.innerHTML='<span class="y">2025년</span><span class="hak">2026학년도</span><span class="ln"></span><span class="cnt"></span>';
 list.replaceChildren(heading);
 for(const row of rows){
  const paper=row.versions[row.active],item=document.createElement('article');item.className='item';item.dataset.exam=row.id;
  const details=document.createElement('div'),nm=document.createElement('div');nm.className='nm';
  const name=document.createElement('span');name.textContent=row.versions.length>1?paper.title.replace(/\s*(홀수형|짝수형)\s*$/,''):paper.title;nm.append(name);
  if(row.versions.length>1){
   const version=document.createElement('span');version.className='version';const label=document.createElement('span');label.className='variant';label.textContent=paper.form;
   const change=document.createElement('button');change.type='button';change.className='switch';change.dataset.symbol=String(symbols);
   const next=row.versions[(row.active+1)%row.versions.length];change.setAttribute('aria-label',paper.title+' — '+next.form+'으로 전환');change.title=next.form+'으로 전환';
   change.innerHTML='<span class="switch-word">다른 버전</span><span class="arrow" aria-hidden="true">↔</span>';
   change.onclick=()=>{row.active=(row.active+1)%row.versions.length;render();list.querySelector('[data-exam="'+row.id+'"] .switch').focus({preventScroll:true});status.textContent='수능 '+next.form+'으로 바꿨습니다. 현재 유형의 자료와 답안 입력을 사용합니다.';};
   version.append(label,change);nm.append(version);
  }
  const check=document.createElement('button');check.type='button';check.className='chk';check.textContent='✓';check.setAttribute('aria-pressed',String(row.solved));check.setAttribute('aria-label',name.textContent+' 푼 것으로 표시');
  check.onclick=()=>{row.solved=!row.solved;render();list.querySelector('[data-exam="'+row.id+'"] .chk').focus({preventScroll:true});status.textContent=row.solved?'푼 회차로 표시했습니다.':'푼 표시를 지웠습니다.';};nm.append(check);
  const meta=document.createElement('div');meta.className='meta';const badge=document.createElement('span');badge.className='badge';badge.textContent=paper.source;
  const date=document.createElement('span');date.textContent=paper.date.replaceAll('-','.')+(paper.schoolYear?' · '+paper.schoolYear+'학년도':'');meta.append(badge,date);
  if(row.solved){const stamp=document.createElement('span');stamp.className='stamp';stamp.textContent='풂';meta.append(stamp);}
  const recordButton=document.createElement('button');recordButton.className='record';recordButton.type='button';const r=row.record||{};
  const labels=[];if(r.spent)labels.push(Math.floor(r.spent/60)+'분'+(r.spent%60?' '+r.spent%60+'초':''));if(r.score!==undefined)labels.push(r.score+'점');if(r.wrong)labels.push(r.wrong.length?'오답 '+r.wrong.length+'개':'모두 맞음');recordButton.textContent=labels.join(' · ')||'기록';recordButton.setAttribute('aria-label',paper.title+' 풀이시간·점수·틀린 번호 편집');recordButton.onclick=()=>record(row,paper,recordButton);meta.append(recordButton);
  details.append(nm,meta);
  const actions=document.createElement('div');actions.className='acts';
  for(const [key,text,cls] of [['problem','문제','q'],['answer','정답','a'],['solution','해설','']]){
   if(paper[key]){const a=document.createElement('a');a.href=paper[key];a.target='_blank';a.rel='noopener';a.className=cls;a.textContent=text;a.setAttribute('aria-label',paper.title+' '+text+' 열기');actions.append(a);}
   else {const span=document.createElement('span');span.className='off';span.textContent=text;span.setAttribute('aria-label',paper.title+' '+text+' 없음');actions.append(span);}
  }
  const sendButton=document.createElement('button');sendButton.type='button';sendButton.className='send';sendButton.textContent='보내기';sendButton.onclick=()=>send(paper,sendButton);actions.append(sendButton);
  item.append(details,actions);list.append(item);
 }
 heading.querySelector('.cnt').textContent=rows.filter(r=>r.solved).length+'/'+rows.length+' 풂';
}
async function load(){
 const id=++loadId;list.textContent='자료를 불러오고 있습니다.';
 try{
  const response=await fetch('../../../data/D300/'+document.querySelector('#subject').value+'.json');if(!response.ok)throw new Error('자료 응답 오류');
  const data=await response.json();if(id!==loadId)return;
  const groups=new Map();
  for(const p of data.papers.filter(p=>p.year===2025&&p.source==='평가원')){
   const key=p.date+'/'+p.type;if(!groups.has(key))groups.set(key,{id:p.date,versions:[],active:0,solved:false});groups.get(key).versions.push(p);
  }
  rows=[...groups.values()].sort((a,b)=>b.id.localeCompare(a.id));
  for(const row of rows)row.versions.sort((a,b)=>(a.form==='홀수형'?0:1)-(b.form==='홀수형'?0:1));
  render();
 }catch(e){if(id===loadId){list.textContent='자료를 불러오지 못했습니다. 다시 열어 주세요.';status.textContent=list.textContent;}}
}
document.querySelector('#subject').onchange=load;
for(const [id,value] of [['words',false],['symbol',true]])document.querySelector('#'+id).onclick=()=>{symbols=value;document.querySelector('#words').setAttribute('aria-pressed',String(!value));document.querySelector('#symbol').setAttribute('aria-pressed',String(value));render();};
document.querySelector('#theme').onclick=()=>{const dark=document.documentElement.dataset.theme!=='dark';document.documentElement.dataset.theme=dark?'dark':'light';document.querySelector('#theme').setAttribute('aria-label',dark?'밝은 화면으로 보기':'어두운 화면으로 보기');};
load();
