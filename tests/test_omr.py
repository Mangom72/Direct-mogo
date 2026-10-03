"""Actual specimen input, guarded grading and fixed-template image recognition.
Synthetic marks validate coordinates and algorithms, not camera success rates.
"""
import pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from harness import CHROME, SHOT, site
from playwright.sync_api import sync_playwright
_srv, SITE = site()
ANS = [5,3,5,4,3,3,5,1,1,2,4,1,3,2,2,5,4,2,3,1]
POINTS = [2,3,2,2,3,2,3,2,2,2,3,2,3,3,3,2,2,3,3,3]
with sync_playwright() as pw:
    browser = pw.chromium.launch(executable_path=CHROME)
    ctx = browser.new_context(viewport={"width":390,"height":844},service_workers="block")
    pg = ctx.new_page(); errors=[]
    pg.on('pageerror',lambda e: errors.append(str(e)))
    pg.goto(SITE); pg.wait_for_selector('.item .record')
    pg.select_option('#grp',label='과학탐구');pg.select_option('#sub',label='생명과학Ⅰ')
    row=pg.locator('.item').filter(has=pg.locator('.meta',has_text='2026.09.02')).first
    key=row.locator('.record').get_attribute('data-k')
    pg.evaluate('''k=>{SOLVED[k]='20260915';TIMES[k]={spent:1200,limit:1800};saveSolved();saveTimes();render()}''',key)
    row.locator('.record').click();pg.click('#recordOmr');pg.click('#omrManual')
    assert '0/20' in pg.locator('.omr-progress').inner_text()
    assert pg.locator('.omr-exam').inner_text().startswith('2027학년도')
    assert pg.locator('.omr-sheet img').get_attribute('src').endswith('/inquiry.webp')
    assert pg.locator('header.head').count()==0 or pg.locator('header.head').evaluate('e=>e.inert')
    for n,v in enumerate(ANS,1):
        if n in [3,15,19]: v = v%5+1
        pg.select_option('#omrQuestion',str(n))
        pg.locator(f'.omr-bubble[data-question="{n}"][data-value="{v}"]').click()
    pg.locator('.omr-actions button').click()
    assert '42' in pg.locator('.omr-score strong').inner_text()
    assert pg.locator('[data-wrong]').count()==3
    pg.screenshot(path=str(SHOT/'omr-result.png'))
    pg.locator('.omr-actions button').click()
    assert '반영했습니다' in pg.locator('.omr-saved').inner_text()
    assert pg.evaluate('k=>RECORDS[k]',key)=={'score':42,'wrong':[3,15,19]}
    assert pg.evaluate('k=>SOLVED[k]',key)=='20260915'
    assert pg.evaluate('k=>TIMES[k]',key)=={'spent':1200,'limit':1800}
    pg.locator('.omr-actions button').click()
    assert pg.evaluate('document.body.style.overflow')==''

    # Use the same module in the public demo; no prefilled answers or record writes.
    pg.goto(SITE+'docs/design/omr/');pg.click('#start');pg.click('#omrManual')
    assert '0/20' in pg.locator('.omr-progress').inner_text()
    pg.set_viewport_size({'width':320,'height':740})
    assert pg.locator('.omr-dialog').evaluate('e=>e.scrollWidth<=e.clientWidth')
    pg.screenshot(path=str(SHOT/'omr-manual-320.png'))
    pg.locator('.omr-close').click();pg.select_option('#subject','math');pg.click('#start');pg.click('#omrManual')
    pg.select_option('#omrQuestion','16');pg.locator('.omr-number[data-question="16"]').click()
    assert pg.locator('#omrNumberDone').is_disabled()
    pg.locator('.omr-number-pad [data-digit="2"][data-value="0"]').click();pg.click('#omrNumberDone')
    assert pg.locator('.omr-number[data-question="16"]').get_attribute('aria-label')=='16번 숫자 답 0 수정'
    pg.locator('.omr-number[data-question="16"]').click();pg.keyboard.press('Escape')
    # Native dialog close dispatch/removal is asynchronous; wait for the observable outcome.
    pg.locator('.omr-number-pad').wait_for(state='detached')
    assert pg.locator('.omr-dialog').is_visible() and pg.locator('.omr-number-pad').count()==0
    pg.click('#omrKey');pg.fill('#omrKeyAnswers','1.5');pg.fill('#omrKeyPoints','3');pg.locator('.omr-actions button').click()
    assert '모두 적어' in pg.locator('.omr-note').inner_text()
    pg.locator('.omr-close').click();pg.select_option('#subject','inquiry');pg.select_option('#exam','edu');pg.click('#start');pg.click('#omrManual')
    assert pg.locator('.omr-exam strong').inner_text().startswith('2026년 ')
    assert '확인해' in pg.locator('.omr-note').inner_text()
    pg.locator('.omr-close').click()

    # Reference-colour masking preserves printed digits and the original watermark.
    probe=pg.evaluate('''async ans=>{
      const F=GijulOmrForms,S=GijulOmrScan,f=F.forms.inquiry,ref=await GijulOMR.loadReference(f);
      const c=document.createElement('canvas');c.width=f.width;c.height=f.height;const ctx=c.getContext('2d');
      const mark=(spot,rx=7)=>{ctx.fillStyle='#000';ctx.beginPath();ctx.ellipse(spot.x,spot.y,rx,10,0,0,Math.PI*2);ctx.fill();};
      ctx.putImageData(ref,0,0);const blank=S.read(ref,ref,f.questions);
      f.questions.forEach((q,i)=>mark(q.spots[ans[i]-1]));
      const full=ctx.getImageData(0,0,c.width,c.height),read=S.read(full,ref,f.questions);
      mark(f.questions[0].spots[0]);const double=S.read(ctx.getImageData(0,0,c.width,c.height),ref,f.questions);
      ctx.putImageData(ref,0,0);mark(f.questions[0].spots[0],2);const faint=S.read(ctx.getImageData(0,0,c.width,c.height),ref,f.questions);
      const shadow=new ImageData(new Uint8ClampedArray(full.data),c.width,c.height);
      for(let i=0;i<shadow.data.length;i+=4){const shade=.55+.35*(i/4%c.width)/c.width;for(let j=0;j<3;j++)shadow.data[i+j]*=shade;}
      const shaded=S.read(shadow,ref,f.questions);
      const points=[{x:0,y:0},{x:c.width-1,y:0},{x:c.width-1,y:c.height-1},{x:0,y:c.height-1}];
      const warped=S.read(S.warp(full,points),ref,f.questions);
      let reject=false;ctx.fillStyle='#fff';ctx.fillRect(0,0,c.width,c.height);try{S.read(ctx.getImageData(0,0,c.width,c.height),ref,f.questions)}catch(e){reject=true;}
      let keySeparate=true;const meta={grade:'D300',subjectId:'158',subject:'생명과학Ⅰ',group:'과학탐구',date:'20260902',title:'9월 모평(평가원)',answerURL:'https://wdown.ebsi.co.kr/W61001/01exam/20260902/mobile/h3_m_g_bio1_ans_45HY71KP.png'};
      keySeparate=!!F.keys[F.exactKey(meta)]&&!F.keys[F.exactKey({...meta,title:meta.title+' 홀수형'})]&&!F.keys[F.exactKey({...meta,subjectId:'159'})];
      return {answers:read.answers,flags:[...read.flags],blank:blank.answers, double:double.flags.get(1),faint:faint.flags.get(1),shadow:shaded.answers,warp:warped.answers,reject,keySeparate,convex:S.convex([points[0],points[2],points[1],points[3]]),counts:Object.values(F.forms).map(f=>f.questions.length)};
    }''',ANS)
    assert probe['answers']==ANS and probe['flags']==[],probe
    assert probe['blank']==[None]*20,probe
    assert probe['double']=='중복 마킹' and probe['faint']=='흐린 마킹',probe
    assert probe['shadow']==ANS and probe['warp']==ANS,probe
    assert probe['reject'] and probe['keySeparate'] and not probe['convex'],probe
    assert sorted(probe['counts'])==[20,20,30,30,45,45]

    all_forms=pg.evaluate("""async()=>{const out=[];for(const f of Object.values(GijulOmrForms.forms)){const ref=await GijulOMR.loadReference(f),c=document.createElement('canvas');c.width=f.width;c.height=f.height;const x=c.getContext('2d');x.putImageData(ref,0,0);x.fillStyle='#000';const expected=f.questions.map((q,i)=>q.kind==='choice'?i%5+1:190);for(const q of f.questions){const val=expected[q.n-1];for(const s of q.spots){if(q.kind==='choice'?s.value===val:s.value===+[...String(val)][s.digit]){x.beginPath();x.ellipse(s.x,s.y,7,10,0,0,Math.PI*2);x.fill();}}}const r=GijulOmrScan.read(x.getImageData(0,0,c.width,c.height),ref,f.questions);out.push({id:f.id,expected,answers:r.answers,flags:[...r.flags]});}return out}""")
    assert all(f['answers']==f['expected'] and not f['flags'] for f in all_forms),all_forms
    assert pg.evaluate('''async()=>{for(const [id,f] of Object.entries(GijulOmrForms.forms)){const r=await GijulOMR.loadReference(f);for(const [other,of] of Object.entries(GijulOmrForms.forms)){if(id===other)continue;const p=await GijulOMR.loadReference(of);let rejected=false;try{GijulOmrScan.read(p,r,f.questions)}catch(e){rejected=true;}if(!rejected)return false;}}return true}''')


    numbers=pg.evaluate("""async()=>{const F=GijulOmrForms,S=GijulOmrScan,f=F.forms.math,r=await GijulOMR.loadReference(f),c=document.createElement('canvas');c.width=f.width;c.height=f.height;const x=c.getContext('2d');x.putImageData(r,0,0);x.fillStyle='#000';for(const [n,digits] of [[16,[null,null,0]],[18,[null,1,9]],[19,[1,null,9]],[21,[null,null,6]]])for(const s of f.questions[n-1].spots)if(digits[s.digit]===s.value){x.beginPath();x.ellipse(s.x,s.y,7,10,0,0,Math.PI*2);x.fill();}const got=S.read(x.getImageData(0,0,c.width,c.height),r,f.questions);return {zero:got.answers[15],blank:got.answers[16],two:got.answers[17],gap:got.answers[18],one:got.answers[20],gapFlag:got.flags.get(19)};}""")
    assert numbers=={'zero':0,'blank':None,'two':19,'gap':None,'one':6,'gapFlag':'숫자 마킹 확인'},numbers
    second=pg.evaluate("""async ans=>{const f=GijulOmrForms.forms.inquiry,r=await GijulOMR.loadReference(f),c=document.createElement('canvas');c.width=f.width;c.height=f.height;const x=c.getContext('2d');x.putImageData(r,0,0);x.fillStyle='#000';for(const q of f.secondQuestions){const s=q.spots[ans[q.n-1]-1];x.beginPath();x.ellipse(s.x,s.y,7,10,0,0,Math.PI*2);x.fill();}const got=GijulOmrScan.read(x.getImageData(0,0,c.width,c.height),r,f.secondQuestions);return {answers:got.answers,flags:[...got.flags]};}""",ANS)
    assert second=={'answers':ANS,'flags':[]},second

    # Real image upload passes through crop and mandatory review; not a canned result.
    pg.select_option('#exam','gov');pg.click('#start');pg.click('#omrPhoto')
    image=pg.evaluate('''async ans=>{const f=GijulOmrForms.forms.inquiry,ref=await GijulOMR.loadReference(f),c=document.createElement('canvas');c.width=f.width;c.height=f.height;const x=c.getContext('2d');x.putImageData(ref,0,0);x.fillStyle='#000';f.questions.forEach((q,i)=>{const s=q.spots[ans[i]-1];x.beginPath();x.ellipse(s.x,s.y,7,10,0,0,Math.PI*2);x.fill();});return c.toDataURL('image/png').split(',')[1];}''',ANS)
    import base64
    pg.set_input_files('#omrFile',{'name':'marked.png','mimeType':'image/png','buffer':base64.b64decode(image)})
    pg.wait_for_selector('#omrFormCheck')
    assert pg.locator('.omr-actions button').is_disabled()
    # Exact synthetic canvas edges; automatic corner proposal is deliberately editable.
    for corner,axes in enumerate([(0,0),(1000,0),(1000,1000),(0,1000)]):
        for axis,value in zip(['x','y'],axes):
            pg.locator(f'[data-corner="{corner}"][data-axis="{axis}"]').evaluate('(e,v)=>{e.value=v;e.dispatchEvent(new Event("input"))}',value)
    pg.check('#omrFormCheck');pg.locator('.omr-actions button').click();pg.wait_for_selector('#omrPhotoCheck')
    assert '20/20' in pg.locator('.omr-progress').inner_text()
    assert pg.locator('.omr-actions button').is_disabled()
    pg.check('#omrPhotoCheck');pg.locator('.omr-actions button').click()
    assert '50' in pg.locator('.omr-score strong').inner_text()
    pg.locator('.omr-close').click()
    pg.evaluate('window.gijulOmrScanResult("old_request",true,"garbage")')
    assert pg.locator('.omr-dialog').count()==0
    assert not errors,errors
    browser.close()
print('답안 입력·채점·사진 확인·기록 보존: 통과')
