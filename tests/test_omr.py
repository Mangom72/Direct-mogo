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
    assert pg.locator('.omr-sheet img').get_attribute('src').endswith('/manual/inquiry.webp')
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
    pg.select_option('#omrQuestion','16')
    digit=lambda d,v: pg.locator(f'.omr-digit[data-question="16"][data-digit="{d}"][data-value="{v}"]')
    assert pg.locator('.omr-digit[data-question="16"]').count()==29
    digit(2,0).click()
    assert '16번 · 0' in pg.locator('#omrCurrent').inner_text()
    assert pg.locator('.omr-digit[aria-pressed="true"][data-question="16"]').count()==1
    digit(0,1).click()
    assert '미완성' in pg.locator('#omrCurrent').inner_text()
    digit(1,0).click()
    assert '16번 · 100' in pg.locator('#omrCurrent').inner_text()
    digit(2,7).click()
    assert '16번 · 107' in pg.locator('#omrCurrent').inner_text()
    assert pg.locator('.omr-digit[aria-pressed="true"][data-question="16"][data-digit="2"]').count()==1
    digit(2,7).click()
    assert '미완성' in pg.locator('#omrCurrent').inner_text()
    pg.click('#omrBlank');assert '미응답' in pg.locator('#omrCurrent').inner_text()
    assert pg.locator('.omr-digit[aria-pressed="true"][data-question="16"]').count()==0
    pg.locator('.omr-answer-controls button').click()
    pg.locator('.omr-number-pad [data-digit="2"][data-value="0"]').click();pg.click('#omrNumberDone')
    assert '16번 · 0' in pg.locator('#omrCurrent').inner_text()
    pg.locator('.omr-answer-controls button').click();pg.keyboard.press('Escape')
    pg.locator('.omr-number-pad').wait_for(state='detached')
    assert pg.locator('.omr-dialog').is_visible() and pg.locator('.omr-number-pad').count()==0
    pg.click('#omrKey');pg.fill('#omrKeyAnswers','1.5');pg.fill('#omrKeyPoints','3');pg.locator('.omr-actions button').click()
    assert '모두 적어' in pg.locator('.omr-note').inner_text()
    pg.locator('.omr-close').click();pg.select_option('#subject','inquiry');pg.select_option('#exam','edu');pg.click('#start');pg.click('#omrManual')
    assert pg.locator('.omr-exam strong').inner_text().startswith('2026년 ')
    assert '확인해' in pg.locator('.omr-note').inner_text()
    pg.locator('.omr-close').click()

    # Wide entry fits the whole sheet and keeps actual answer clicks distinct.
    pg.set_viewport_size({'width':1024,'height':768})
    pg.select_option('#subject','korean');pg.click('#start');pg.click('#omrManual')
    pg.wait_for_function("()=>document.querySelector('.omr-sheet').classList.contains('omr-full-input')")
    sheet=pg.locator('.omr-sheet');pg.wait_for_function("()=>document.querySelector('.omr-sheet').offsetHeight<=document.querySelector('.omr-sheet-scroll').clientHeight")
    sb=sheet.bounding_box();vb=pg.locator('.omr-sheet-scroll').bounding_box()
    assert sb['width']<=vb['width'] and sb['height']<=vb['height'] and sb['width']>650,(sb,vb)
    assert pg.locator('.omr-dialog').bounding_box()['width']==1024
    pg.locator('.omr-bubble[data-question="1"][data-value="5"]').click()
    assert pg.locator('.omr-bubble[data-question="1"][data-value="5"]').get_attribute('aria-pressed')=='true'
    pg.locator('.omr-answer-controls [data-answer="2"]').click()
    assert pg.locator('.omr-bubble[data-question="1"][data-value="2"]').get_attribute('aria-pressed')=='true'
    pg.select_option('#omrQuestion','45')
    assert sheet.evaluate("e=>e.classList.contains('omr-full-input')")
    pg.locator('.omr-bubble[data-question="45"][data-value="4"]').click()
    pg.click('#omrWhole');assert sheet.evaluate("e=>!e.classList.contains('omr-full-input')")
    pg.click('#omrWhole');assert sheet.evaluate("e=>e.classList.contains('omr-full-input')")
    pg.set_viewport_size({'width':390,'height':844})
    pg.wait_for_function("()=>!document.querySelector('.omr-sheet').classList.contains('omr-full-input')")
    pg.locator('.omr-close').click();pg.select_option('#subject','inquiry')

    # A partially marked integer survives a real draft reload and cannot be graded.
    mathmeta={'grade':'D300','subjectId':'140120','subject':'미적분','group':'수학','date':'20260902','title':'9월 모평(평가원)','answerURL':'draft-answer','problemURL':'draft-problem'}
    pg.evaluate('meta=>GijulOMR.open(meta)',mathmeta);pg.click('#omrManual');pg.select_option('#omrQuestion','16')
    pg.locator('.omr-digit[data-question="16"][data-digit="0"][data-value="1"]').click()
    pg.locator('.omr-close').click();pg.evaluate('meta=>GijulOMR.open(meta)',mathmeta);pg.click('#omrManual');pg.select_option('#omrQuestion','16')
    assert pg.locator('.omr-digit[data-question="16"][data-digit="0"][data-value="1"]').get_attribute('aria-pressed')=='true'
    assert '미완성' in pg.locator('#omrCurrent').inner_text()
    pg.click('#omrKey');assert pg.locator('#omrKeyPoints').input_value().split()==['2','2','3','3','3','3','3','3','4','4','4','4','4','4','4','3','3','3','3','4','4','4','2','3','3','3','3','4','4','4']
    pg.fill('#omrKeyAnswers',' '.join(['1']*30));pg.check('#omrKeyCheck');pg.locator('.omr-actions button').click();pg.check('#omrBlankCheck')
    assert pg.locator('.omr-actions button').is_disabled()
    pg.select_option('#omrQuestion','16');pg.locator('.omr-digit[data-question="16"][data-digit="1"][data-value="0"]').click();pg.locator('.omr-digit[data-question="16"][data-digit="2"][data-value="7"]').click()
    assert '16번 · 107' in pg.locator('#omrCurrent').inner_text()
    assert pg.locator('#omrBlankCheck').is_checked()==False
    pg.locator('.omr-close').click()

    # Source identity, checked year range and genuine pixel resolution are guarded.
    scoring=pg.evaluate("""()=>{const F=GijulOmrForms,m={grade:'D300',subjectId:'140120',date:'20260902',title:'9월 모평(평가원)'};const f=F.forms.math;return {math:F.pointsFor(m,f).points,total:F.pointsFor(m,f).points.reduce((a,b)=>a+b,0),future:F.pointsFor({...m,date:'20270902'},f),old:F.pointsFor({...m,date:'20200902'},f),unknown:F.pointsFor({...m,subjectId:'999'},f)};}""")
    assert scoring['total']==100 and scoring['future'] is None and scoring['old'] is None and scoring['unknown'] is None,scoring
    import json
    entries=json.loads((pathlib.Path(__file__).resolve().parents[1]/'omr/points-reviewed.json').read_text())['entries']
    checks=pg.evaluate("""entries=>entries.filter(e=>!['140119','140120','140121'].includes(e.key[1])).map(e=>{const F=GijulOmrForms,[grade,subjectId,date,title,answerURL]=e.key;const m={grade,subjectId,date,title,answerURL,problemURL:e.problemURL},f=F.forms[({'140117':'korean','80003':'english','63004':'history','158':'inquiry','191':'language','195':'language'})[subjectId]];return {expected:e.points,actual:F.pointsFor(m,f)?.points,badURL:F.pointsFor({...m,problemURL:'different'},f),badType:F.pointsFor({...m,title:title+' 짝수형'},f)}})""",entries)
    assert len(checks)==18 and all(c['actual']==c['expected'] and c['badURL'] is None and c['badType'] is None for c in checks),checks
    pg.select_option('#exam','gov')
    for subject in ['korean','math','english','history','inquiry','language']:
        pg.select_option('#subject',subject);pg.set_viewport_size({'width':1280,'height':960});pg.click('#start');pg.click('#omrManual')
        pg.wait_for_function("()=>document.querySelector('.omr-sheet img').naturalWidth>=3420")
        if subject=='math':
            pg.wait_for_function("()=>document.querySelector('.omr-sheet').dataset.alignment==='clock'")
        # Find coloured ink in the original image, independently of button paint.
        # A shifted cell fails even when synthetic marks share the same bad coordinates.
        alignment=pg.evaluate("""()=>{
            const f=GijulOmrForms.manualForms[document.querySelector('#subject').value];
            const img=document.querySelector('.omr-sheet>img'),c=document.createElement('canvas');
            c.width=img.naturalWidth;c.height=img.naturalHeight;
            const ctx=c.getContext('2d');ctx.drawImage(img,0,0);
            const pixels=ctx.getImageData(0,0,c.width,c.height).data,out=[];
            for(const q of [...f.questions,...(f.secondQuestions||[])])for(const spot of q.spots){
                if(spot.unprinted)continue;
                const button=f.id==='math'?document.querySelector(`.omr-bubble[data-question="${q.n}"][data-value="${spot.value}"]${q.kind==='number'?`[data-digit="${spot.digit}"]`:''}`):null;
                const x=button?parseFloat(button.style.left)*c.width/100:spot.x*c.width/f.width,y=spot.y*c.width/f.width,xx=Math.round(x),yy=Math.round(y);
                let left=Infinity,right=-Infinity,top=Infinity,bottom=-Infinity;
                for(let sy=yy-25;sy<=yy+25;sy++)for(let sx=xx-24;sx<=xx+24;sx++){
                    const i=(sy*c.width+sx)*4,r=pixels[i],g=pixels[i+1],b=pixels[i+2];
                    if(Math.max(r,g,b)-Math.min(r,g,b)>70&&Math.min(r,g,b)<180){
                        left=Math.min(left,sx);right=Math.max(right,sx);top=Math.min(top,sy);bottom=Math.max(bottom,sy);
                    }
                }
                out.push({n:q.n,digit:spot.digit,value:spot.value,
                    error:Math.max(Math.abs(x-(left+right)/2),Math.abs(y-(top+bottom)/2))});
            }
            return out;
        }""")
        assert len(alignment)=={'korean':225,'math':366,'english':225,'history':100,'inquiry':200,'language':150}[subject]
        assert all(a['error'] is not None and a['error']<=6 for a in alignment),(subject,alignment)
        heading=pg.locator('.omr-paper-heading')
        assert heading.get_attribute('data-year')=='2027' and heading.get_attribute('data-original')=='false'
        assert heading.locator('text,strong,span').count()==0
        assert pg.locator('.omr-title-preset').count()==1  # Exact “모의 평가” preset.
        assert pg.locator('.omr-margin-mask').count()==1
        regions=heading.locator('.omr-area-preset').evaluate_all('es=>es.map(e=>{const b=e.getBoundingClientRect();return {x:b.x,y:b.y,width:b.width,height:b.height}})')
        for box in pg.locator('.omr-bubble').evaluate_all('es=>es.map(e=>{const b=e.getBoundingClientRect();return {top:b.top,left:b.left,right:b.right,bottom:b.bottom}})'):
            for region in regions:
                assert box['top']>=region['y']+region['height'] or box['left']>=region['x']+region['width'],(subject,box,region)
        pg.screenshot(path=str(SHOT/('omr-'+subject+'-tablet.png')))
        pg.locator('.omr-close').click()
    # The source timing bars, rather than guessed answer X, control all columns.
    pg.select_option('#subject','math');pg.click('#start');pg.click('#omrManual')
    pg.wait_for_function("()=>document.querySelector('.omr-sheet').dataset.alignment==='clock'")
    clocks=pg.evaluate("""async()=>{
      const F=GijulOmrForms,f=F.manualForms.math,img=document.querySelector('.omr-sheet img');
      const full=GijulOMR.clockColumns(img,f),c=document.createElement('canvas');c.width=1800;c.height=Math.round(f.height);c.getContext('2d').drawImage(img,0,0,c.width,c.height);
      c.naturalWidth=c.width;
      return {full,small:GijulOMR.clockColumns(c,f)};
    }""")
    assert len(clocks['full'])==45 and max(abs(a-b) for a,b in zip(clocks['full'],clocks['small']))<=1,clocks
    pg.locator('.omr-close').click()
    original_x=pg.evaluate("()=>{const f=GijulOmrForms.manualForms.math,out=f.questions.map(q=>q.spots.map(p=>p.x));for(const q of f.questions)for(const p of q.spots)p.x+=15;return out}")
    pg.click('#start');pg.click('#omrManual')
    pg.wait_for_function("()=>document.querySelector('.omr-sheet').dataset.alignment==='clock'")
    for n,index in [(20,41),(21,25),(22,28),(29,38),(30,41)]:
        x=pg.locator(f'.omr-digit[data-question="{n}"][data-digit="0"][data-value="1"]').evaluate("e=>parseFloat(e.style.left)*1800/100")
        assert abs(x-clocks['full'][index])<.001,(n,x,clocks)
        pg.select_option('#omrQuestion',str(n))
        pg.locator(f'.omr-digit[data-question="{n}"][data-digit="2"][data-value="7"]').click()
        assert f'{n}번 · 7' in pg.locator('#omrCurrent').inner_text()
    pg.locator('.omr-close').click()
    pg.evaluate("xs=>GijulOmrForms.manualForms.math.questions.forEach((q,i)=>q.spots.forEach((p,j)=>p.x=xs[i][j]))",original_x)
    # Missing machine marks must leave every answer control and grading blocked.
    import base64
    blank_strip=pg.evaluate("""async()=>{const f=GijulOmrForms.manualForms.math,i=new Image();i.src=f.image;await i.decode();const c=document.createElement('canvas');c.width=i.naturalWidth;c.height=i.naturalHeight;const x=c.getContext('2d');x.drawImage(i,0,0);x.fillStyle='#fff';x.fillRect(0,100,c.width,80);return c.toDataURL().split(',')[1]}""")
    bad_image_url=pg.evaluate("GijulOmrForms.manualForms.math.image")
    ctx.route(bad_image_url,lambda r:r.fulfill(body=base64.b64decode(blank_strip),content_type='image/png'))
    pg.click('#start');pg.click('#omrManual')
    pg.wait_for_function("()=>document.querySelector('.omr-sheet').dataset.alignment==='failed'")
    assert pg.locator('.omr-bubble:enabled').count()==0
    assert pg.locator('.omr-answer-controls button:enabled').count()==0 and pg.locator('#omrBlank').is_disabled()
    assert '기준 표식' in pg.locator('.omr-note').inner_text()
    pg.click('#omrKey');pg.fill('#omrKeyAnswers',' '.join(['1']*30));pg.check('#omrKeyCheck');pg.locator('.omr-actions button').click()
    pg.wait_for_function("()=>document.querySelector('.omr-sheet').dataset.alignment==='failed'")
    pg.check('#omrBlankCheck');assert pg.locator('.omr-actions button').is_disabled()
    pg.locator('.omr-close').click();ctx.unroute(bad_image_url)
    # A late decode cannot change the key editor opened in the meantime.
    pg.evaluate("""()=>{window.omrDecode=HTMLImageElement.prototype.decode;let hold=true;HTMLImageElement.prototype.decode=function(){const loaded=omrDecode.call(this);if(!hold)return loaded;hold=false;return loaded.then(()=>new Promise(r=>window.finishOmrDecode=r));};}""")
    pg.click('#start');pg.click('#omrManual')
    pg.wait_for_function("()=>typeof finishOmrDecode==='function'")
    assert pg.locator('.omr-sheet').get_attribute('data-alignment')=='pending'
    assert pg.locator('.omr-bubble:enabled').count()==0
    pg.click('#omrKey')
    pg.evaluate("async()=>{finishOmrDecode();HTMLImageElement.prototype.decode=omrDecode;await new Promise(requestAnimationFrame);}")
    assert pg.locator('#omrKeyForm').count()==1 and pg.locator('.omr-sheet').count()==0
    assert pg.locator('.omr-note').inner_text()==''
    pg.locator('.omr-close').click()
    # Actual presets load painted outlines, with 시행 연도 / 학년도 and clear regions.
    for title,date,expected,year in [('수능 홀수형','20251113','csat','2026'),('6월 모평(평가원)','20250604','m6','2026'),('10월 학평(서울)','20211012','edu10','2021')]:
        meta={**mathmeta,'date':date,'title':title}
        pg.evaluate('meta=>GijulOMR.open(meta,{demo:true})',meta);pg.click('#omrManual')
        pg.wait_for_function("()=>document.querySelector('.omr-title-preset use').getBBox().width>0")
        heading=pg.locator('.omr-paper-heading')
        assert heading.get_attribute('data-year')==year and heading.get_attribute('data-preset')==expected
        assert heading.locator('text,strong,span').count()==0
        bounds=pg.locator('.omr-title-preset').bounding_box()
        for box in pg.locator('.omr-bubble').evaluate_all('es=>es.map(e=>e.getBoundingClientRect().top)'):
            assert box>=bounds['y']+bounds['height']
        pg.screenshot(path=str(SHOT/('omr-preset-'+expected+'.png')))
        pg.locator('.omr-close').click()
    pg.select_option('#subject','inquiry');pg.set_viewport_size({'width':390,'height':844})

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
    fallback=browser.new_context(service_workers="block")
    fallback.route('**/omr/forms.js',lambda route:route.abort())
    older=fallback.new_page();fallback_errors=[]
    older.on('pageerror',lambda e:fallback_errors.append(str(e)))
    older.goto(SITE);older.wait_for_selector('.item .record')
    older.locator('.item .record').first.click()
    assert older.locator('#recordForm').is_visible() and older.locator('#recordOmr').count()==0
    older.fill('#recordScore','40');older.locator('.record-save').click()
    assert not older.locator('#recordForm').is_visible() and not fallback_errors,fallback_errors
    fallback.close()
    browser.close()
print('답안 입력·채점·사진 확인·기록 보존: 통과')
