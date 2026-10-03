'use strict';
// Standalone interaction mock. No camera, recognizer, native bridge, storage, or cloud calls.
const bio = {
  name:'생명과학Ⅰ',count:20,maximum:50,
  answers:[5,3,5,4,3,3,5,1,1,2,4,1,3,2,2,5,4,2,3,1],
  points:[2,3,2,2,3,2,3,2,2,2,3,2,3,3,3,2,2,3,3,3],
  seed:[5,3,2,4,3,3,5,1,1,2,4,1,3,2,5,5,4,2,1,1],
  flags:new Map([[7,'흐린 마킹'],[12,'중복 마킹'],[17,'미응답 확인']])
};
const math = {
  name:'확률과 통계',count:30,maximum:100,points:null,
  answers:[4,3,2,2,1,5,2,3,1,3,3,4,5,5,4,6,11,38,15,17,12,97,1,4,5,2,3,5,190,170],
  seed:[4,3,2,2,1,5,2,3,1,3,3,4,5,5,4,6,11,38,15,17,12,97,1,4,5,2,3,5,190,170],
  flags:new Map([[7,'흐린 마킹'],[16,'숫자 마킹 확인'],[17,'미응답 확인']])
};
let exam=bio,answers=[...bio.seed],pending=new Set(bio.flags.keys()),confirmed=new Set(),stage='capture',filter=false,saved=false;
answers[16]=null;
const main=document.querySelector('#main'),actions=document.querySelector('#actions');
const announce=text=>{document.querySelector('#status').textContent=text;};
function mathSVG(){
  let marks='';
  for(let i=0;i<21;i++){
    const n=i<15?i+1:i+8,y=91+i*10.5;
    marks+=`<text x="29" y="${y+3}" font-size="7" fill="#9b5964">${n}</text>`;
    for(let j=0;j<5;j++)marks+=`<ellipse cx="${58+j*25}" cy="${y}" rx="5" ry="4" stroke="#d38392" fill="${exam.seed[n-1]===j+1?(n===7?'#aaa':'#333'):'#fff'}"/>`;
  }
  const questions=[16,17,18,19,20,21,22,29,30];
  questions.forEach((n,i)=>{
    const x=265+(i%3)*65,y=87+Math.floor(i/3)*78,digits=String(exam.seed[n-1]).padStart(3,'0');
    marks+=`<rect x="${x-9}" y="${y-12}" width="53" height="72" fill="none" stroke="#d38392"/><text x="${x+16}" y="${y-3}" font-size="7" text-anchor="middle" fill="#9b5964">${n}번</text>`;
    for(let d=0;d<3;d++)for(let k=0;k<10;k++)marks+=`<ellipse cx="${x+d*16}" cy="${y+6+k*5}" rx="3" ry="2" stroke="#d38392" fill="${+digits[d]===k?'#333':'#fff'}" stroke-width=".5"/>`;
  });
  return `<svg class="paper-photo" viewBox="0 0 490 345" role="img" aria-label="수학 선택형 답란과 백·십·일 숫자 마킹 답란이 있는 연습용 답안지"><rect width="490" height="345" fill="#fffcf7"/><g fill="#292824"><rect x="10" y="10" width="6" height="12"/><rect x="474" y="10" width="6" height="12"/><rect x="10" y="323" width="6" height="12"/><rect x="474" y="323" width="6" height="12"/></g><text x="26" y="32" fill="#9b5964" font-size="11">기출 직행 · 연습용 답안지</text><text x="26" y="53" fill="#292824" font-size="17" font-weight="bold">수학 · 확률과 통계</text><path d="M25 69H465" stroke="#cf9aa3"/><text x="76" y="80" fill="#a86c76" font-size="7">선택형</text><text x="301" y="76" fill="#a86c76" font-size="7">단답형 · 백 십 일</text>${marks}<text x="27" y="332" fill="#aaa" font-size="6">숫자 답은 자릿수별 마킹으로 읽고 확인합니다</text></svg>`;
}
function paperSVG(){
  if(exam===math)return mathSVG();
  let rows='';
  for(let i=0;i<20;i++){
    const col=i<10?0:1,r=i%10,xx=col*240,yy=106+r*21;
    rows+=`<text x="${31+xx}" y="${yy+4}" font-size="9" fill="#9b5964">${i+1}</text>`;
    for(let j=0;j<5;j++){
      const x=63+xx+j*28,fill=(bio.seed[i]===j+1||(i===11&&j===3))?(i===6?'#aaa':'#333'):'#fff';
      rows+=`<ellipse cx="${x}" cy="${yy}" rx="7" ry="9" stroke="#d38392" fill="${fill}"/><text x="${x}" y="${yy+3}" text-anchor="middle" font-size="7" fill="${fill!=='#fff'?'#fff':'#c37b89'}">${j+1}</text>`;
    }
  }
  return `<svg class="paper-photo" viewBox="0 0 490 345" role="img" aria-label="분홍색 OMR 답란과 검은 마킹이 있는 연습용 답안지"><rect width="490" height="345" fill="#fffcf7"/><g fill="#292824"><rect x="10" y="10" width="6" height="12"/><rect x="474" y="10" width="6" height="12"/><rect x="10" y="323" width="6" height="12"/><rect x="474" y="323" width="6" height="12"/></g><text x="26" y="32" fill="#9b5964" font-size="11">기출 직행 · 연습용 답안지</text><text x="26" y="53" fill="#292824" font-size="17" font-weight="bold">생명과학Ⅰ</text><text x="344" y="35" fill="#a86c76" font-size="9">GM-20-01</text><path d="M25 72H465" stroke="#cf9aa3"/><text x="29" y="90" fill="#a86c76" font-size="8">문항</text><text x="92" y="90" fill="#a86c76" font-size="8">답    란</text><text x="269" y="90" fill="#a86c76" font-size="8">문항</text><text x="332" y="90" fill="#a86c76" font-size="8">답    란</text><path d="M244 79V313" stroke="#e4c2c7"/>${rows}<text x="27" y="332" fill="#aaa" font-size="6">실제 수능 답안지의 타원형 답란을 참고한 디자인 예시</text></svg>`;
}
function examCard(select=false){return `<div class="exam"><div><strong>2027학년도 9월 모평</strong><small>2026.09.02 시행 · 고3·N수</small>${select?'':`<small>${exam.name} · ${exam.count}문항</small>`}</div>${select?`<select id="subject" aria-label="시안 과목"><option value="bio" ${exam===bio?'selected':''}>생명과학Ⅰ</option><option value="math" ${exam===math?'selected':''}>확률과 통계</option></select>`:`<span class="count-stamp">${exam.maximum}점 만점</span>`}</div>`;}
function showPhoto(){
  const dialog=document.createElement('dialog');dialog.className='photo-dialog';
  dialog.innerHTML=`<div class="photo-heading"><strong>예시 원본 사진</strong><button class="quiet">닫기</button></div><p class="muted">사진을 옆으로 움직여 마킹을 확인하세요.</p><div class="photo-scroll">${paperSVG()}</div>`;
  document.body.append(dialog);dialog.querySelector('button').onclick=()=>dialog.close();dialog.addEventListener('close',()=>dialog.remove());dialog.showModal();
}
function startReview(){stage='review';render();main.focus({preventScroll:true});window.scrollTo(0,0);}
function go(next){
  if(next==='result'&&pending.size){announce('확인이 필요한 답안 '+pending.size+'개가 남았습니다');return;}
  stage=next;render();window.scrollTo(0,0);main.focus({preventScroll:true});
}
function capture(){
  main.innerHTML=`<div class="intro"><p class="eyebrow">PAPER TO RECORD</p><h1>찍고, 확인하고, 채점하기.</h1><p class="muted">풀어 둔 종이 OMR을 가져오세요.<br>답지와 비교해 점수와 틀린 번호를 정리합니다.</p></div>${examCard(true)}<div class="camera"><div class="camera-label"><span>연습용 OMR · ${exam.count}문항</span><span class="ready">네 모서리를 맞춰 주세요</span></div>${paperSVG()}<div class="guide" aria-hidden="true"><i></i><i></i><i></i><i></i></div><div class="camera-note">종이가 잘리지 않게 · 그림자 없이</div></div><div class="capture-options"><button id="gallery">사진에서 가져오기</button><button id="sheet" ${exam===math?'disabled':''}>${exam===math?'수학 양식 준비 중':'답안지 양식 보기 ↗'}</button></div><p class="guide-note">익숙한 타원형 답란으로 읽습니다.<br>희미하거나 두 번 칠한 답은 채점 전에 확인합니다.</p>`;
  actions.innerHTML=`<button class="primary" id="shoot"><span>◎ &nbsp; 예시 사진 인식하기</span><small>다음 · 답안 확인 →</small></button><p class="action-note">촬영·인식 기능을 구현하기 전의 동작 시안입니다</p>`;
  document.querySelector('#shoot').onclick=startReview;document.querySelector('#gallery').onclick=startReview;
  document.querySelector('#sheet').onclick=()=>window.open('sheet.html','_blank','noopener');
  document.querySelector('#subject').onchange=e=>{
    exam=e.target.value==='math'?math:bio;answers=[...exam.seed];answers[16]=null;pending=new Set(exam.flags.keys());confirmed=new Set();saved=false;render();
  };
}
function row(n){
  const v=answers[n-1],flag=exam.flags.get(n),isPending=pending.has(n),numeric=exam===math&&((n>=16&&n<=22)||n>=29);
  const body=numeric?`<div class="row-main numeric-row"><span class="question-number">${n}</span><input data-number="${n}" aria-label="${n}번 단답형 답" inputmode="numeric" maxlength="3" pattern="[0-9]{1,3}" value="${v??''}"><span>백 · 십 · 일<br>숫자 마킹</span></div>`:`<div class="row-main"><span class="question-number">${n}</span>${[1,2,3,4,5].map(x=>`<button class="bubble" data-number="${n}" data-value="${x}" aria-label="${n}번 답 ${x}번" aria-pressed="${v===x || (isPending&&flag==='중복 마킹'&&[1,4].includes(x))}"><span>${x}</span></button>`).join('')}</div>`;
  let note='';
  if(flag){note=`<div class="row-note ${isPending?'':'resolved'}"><span>${isPending?(flag==='중복 마킹'?'① · ④ 중복 마킹 — 하나를 골라 주세요':flag==='숫자 마킹 확인'?'006으로 읽었습니다. 숫자를 확인하세요':flag==='미응답 확인'?'빈칸으로 읽었습니다. 답을 고르거나 확인하세요':(exam===math?'②':'⑤')+' 흐린 마킹 — 답을 다시 눌러 주세요'):'✓ 답안 확인했습니다'}</span>${isPending&&flag==='미응답 확인'?`<button data-blank="${n}">미응답 확인</button>`:''}${isPending&&numeric?`<button data-confirm="${n}">확인</button>`:''}</div>`;}
  return `<div class="answer-row ${isPending?'flagged':''}" id="q${n}">${body}${note}</div>`;
}
function confirm(n,value){answers[n-1]=value;pending.delete(n);confirmed.add(n);saved=false;review(false);main.querySelector('[data-number="'+n+'"]'+(value===null?'':'[data-value="'+value+'"]'))?.focus({preventScroll:true});announce(n+'번 답을 확인했습니다. 남은 확인 '+pending.size+'개');}
function review(top=true){
  const scroll=window.scrollY;
  main.innerHTML=`<div class="intro"><p class="eyebrow">CHECK YOUR MARKS</p><h1>답안을 한번 확인해 주세요.</h1><p class="muted">읽어 온 답과 종이에 칠한 답이 같은지 확인합니다.</p></div>${examCard()}<div class="flag-summary"><span>⊙</span><div><strong>${pending.size?pending.size+'문항은 확인이 필요합니다':'확인이 끝났습니다'}</strong><p>${pending.size?'애매한 마킹은 정답으로 추측하지 않습니다.<br>번호를 누르면 해당 답란으로 이동합니다.':'점수와 틀린 번호를 정리할 수 있습니다.'}</p><div class="review-links">${[...exam.flags.keys()].map(n=>`<button data-jump="${n}" class="${pending.has(n)?'':'done'}">${n}번 ${pending.has(n)?exam.flags.get(n):'확인 ✓'}</button>`).join('')}</div></div></div><div class="review-photo"><button id="photo" class="quiet">원본 사진 보기 ↗</button><span>마킹과 읽은 답을 비교하세요</span></div><div class="review-tools"><span>${exam.count}문항 · 답은 직접 고칠 수 있습니다</span><button id="onlyflags" aria-pressed="${filter}">${filter?'전체 답안 보기':'확인할 답만 보기'}</button></div><div class="omr-table"><div class="omr-top"><span>문항</span><span>${exam===math?'선택형 + 숫자 마킹':'답 &nbsp; 란'}</span><span>OMR</span></div>${Array.from({length:exam.count},(_,i)=>i+1).filter(n=>!filter||pending.has(n)).map(row).join('')||'<p class="muted">확인할 답이 없습니다.</p>'}</div>`;
  actions.innerHTML=`<button id="grade" class="primary" ${pending.size?'disabled':''}><span>${pending.size?'확인 후 채점하기':'채점 결과 보기'}</span><small>${pending.size?'확인 '+pending.size+'개 남음':'다음 · 결과 →'}</small></button><p class="action-note">정답은 채점 결과에서 확인합니다</p>`;
  main.querySelectorAll('[data-jump]').forEach(b=>b.onclick=()=>document.querySelector('#q'+b.dataset.jump)?.scrollIntoView({behavior:'auto',block:'center'}));
  main.querySelectorAll('.bubble').forEach(b=>b.onclick=()=>confirm(+b.dataset.number,+b.dataset.value));
  main.querySelectorAll('[data-blank]').forEach(b=>b.onclick=()=>confirm(+b.dataset.blank,null));
  main.querySelectorAll('input[data-number]').forEach(input=>input.onchange=()=>{if(/^\d{1,3}$/.test(input.value))confirm(+input.dataset.number,+input.value);else{input.setCustomValidity('0부터 999까지 정수로 입력하세요');input.reportValidity();}});
  main.querySelectorAll('[data-confirm]').forEach(b=>b.onclick=()=>{const input=main.querySelector('input[data-number="'+b.dataset.confirm+'"]');if(/^\d{1,3}$/.test(input.value))confirm(+b.dataset.confirm,+input.value);else announce('숫자를 먼저 확인해 주세요');});
  document.querySelector('#photo').onclick=showPhoto;
  document.querySelector('#onlyflags').onclick=()=>{filter=!filter;review(false);};document.querySelector('#grade').onclick=()=>go('result');
  if(!top)window.scrollTo(0,scroll);
}
function result(){
  const wrong=answers.flatMap((v,i)=>v!==exam.answers[i]?[i+1]:[]),blank=answers.filter(v=>v==null).length;
  const score=exam.points?exam.points.reduce((sum,p,i)=>sum+(answers[i]===exam.answers[i]?p:0),0):null;
  if(saved){main.innerHTML=`<div class="saved"><p class="eyebrow">SAMPLE RECORD</p><div class="seal">기록</div><h1>이렇게 기록됩니다.</h1><p class="muted">${exam.name} · ${score}점<br>틀린 번호 ${wrong.join(', ')||'없음'}</p><p class="source-note">시안에서는 앱 기록을 저장하지 않습니다.</p></div>${examCard()}`;actions.innerHTML='<button class="primary" id="again"><span>처음부터 다시 보기</span><small>촬영 →</small></button>';document.querySelector('#again').onclick=()=>{saved=false;go('capture');};return;}
  main.innerHTML=`<div class="intro"><p class="eyebrow">YOUR RESULT</p><h1>오늘의 풀이를 정리했어요.</h1><p class="muted">확인한 답안을 기준으로 채점했습니다.</p></div>${examCard()}<div class="score-card"><div class="score-label">${score===null?'정답 수':'원점수'}</div><div class="score-value">${score===null?exam.count-wrong.length:score}<span> / ${score===null?exam.count:exam.maximum}${score===null?'문항':'점'}</span></div><div class="score-meta"><div><p>맞힌 문항</p><strong>${exam.count-wrong.length}</strong></div><div><p>틀린 문항</p><strong>${wrong.length-blank}</strong></div><div><p>미응답</p><strong>${blank}</strong></div></div></div><div class="result-status"><span>✓ 답안 확인 ${exam.flags.size}문항 완료</span><span>${score===null?'배점 확인 필요':'문항별 배점 합계 50점'}</span></div>${score===null?'<p class="math-warning">정답은 비교할 수 있습니다. 문항별 배점을 확인한 뒤 점수를 기록합니다.</p>':''}<div class="result-title"><h2>다시 볼 문제</h2><span>${wrong.length}문항</span></div><div class="wrong-cards">${wrong.map(n=>`<div class="wrong-card"><strong>${n}<small>${exam.points?exam.points[n-1]+'점 문항':'정답 비교'}</small></strong><div class="answer-comparison"><span class="mine">${answers[n-1]??'—'}</span><span class="muted">→</span><span class="right">${exam.answers[n-1]}</span></div><p class="lost">${answers[n-1]===null?'미응답':exam.points?'-'+exam.points[n-1]+'점':'오답'}</p></div>`).join('')||'<p class="muted">모든 답이 맞았습니다.</p>'}</div><div class="result-note"><p>점수와 틀린 번호가 기존 풀이 기록에 들어갑니다.<br>푼 날과 이미 기록한 풀이시간은 함께 이어집니다.</p></div><div class="result-bottom"><span>기록 전에 한 번 더 볼 수 있습니다</span><button class="quiet" id="revise">답안 수정</button></div>`;
  actions.innerHTML=`<button class="primary" id="save" ${score===null?'disabled':''}><span>풀이 기록에 반영하기</span><small>${score===null?'배점 확인 필요':score+'점 · 오답 '+wrong.length+'개'}</small></button><p class="action-note">예시 결과입니다 · 실제 기록에 저장하지 않습니다</p>`;
  document.querySelector('#revise').onclick=()=>go('review');document.querySelector('#save').onclick=()=>{saved=true;render();announce('시안의 기록 확인 화면입니다. 실제 저장하지 않습니다');};
}
function render(){
  document.querySelectorAll('[data-stage]').forEach(b=>{b.removeAttribute('aria-current');if(b.dataset.stage===stage)b.setAttribute('aria-current','step');b.disabled=b.dataset.stage==='result'&&pending.size>0;});
  if(stage==='capture')capture();else if(stage==='review')review();else result();
}
document.querySelectorAll('[data-stage]').forEach(b=>b.onclick=()=>go(b.dataset.stage));
document.querySelector('#theme').onclick=()=>{const dark=document.documentElement.dataset.theme!=='dark';document.documentElement.dataset.theme=dark?'dark':'light';document.querySelector('#theme').setAttribute('aria-label',dark?'밝은 화면으로 보기':'어두운 화면으로 보기');};
render();
