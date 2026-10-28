"""공식 예시문항: 대상 학년도, 원본·별도 공개분, 기록 격리, 갱신·앱 링크 경로."""
import copy
import json
import pathlib
import re
import sys
from urllib.parse import urlparse, parse_qs
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from harness import ROOT, CHROME, site
sys.path.insert(0, str(ROOT / 'tools'))
import build_api as API
import refresh_data as REFRESH
from playwright.sync_api import sync_playwright

text=(ROOT/'index.html').read_text()
samples=API.read_samples(text)
assert {p['schoolYear'] for p in samples} == {2017,2018,2022,2028}
assert len({p['id'] for p in samples}) == len(samples)
assert all('예시문항' in p['title'] and 'date' not in p and 'year' not in p for p in samples)
assert json.loads((ROOT/'data/samples.json').read_text()) == samples
by_id={p['id']:p for p in samples}
assert by_id['2017-history']['schoolYear']==2017 and by_id['2017-history']['published']=='2014-04-11'
assert by_id['2028-inquiry-2024']['published']=='2024-09-26'
assert by_id['2028-900003']['published']=='2025-04-15'
assert by_id['2028-inquiry-2024']['files'][0]['url'] != by_id['2028-900003']['files'][0]['url']

# 이 추가 작업은 URL 해독기나 네이티브 허용 목록을 넓히지 않는다.
for p in samples:
    for f in p['files']:
        u=urlparse(f['url']);q=parse_qs(u.query)
        assert u.scheme=='https' and not u.username and not u.password and not u.port
        if u.hostname in {'www.suneung.re.kr','www.moe.go.kr'}:
            assert u.path=='/boardCnts/fileDown.do' and re.fullmatch('[0-9a-f]{32}',q['fileSeq'][0])
        else:
            assert u.hostname=='www.ebsi.co.kr' and u.path=='/ebs/ent/com/downLoadFileDefaultNew.ebs'
            assert q['datNo']==['620487'] and q['bbsCd']==['B123'] and q['fileGbn'][0] in '1234'
    for sid in p['subjects']:
        meta=json.loads((ROOT/f'data/D300/{sid}.json').read_text())
        assert p in meta['samples']
assert set(by_id['2028-900001']['subjects']) == {'900001'}
assert set(by_id['2028-900002']['subjects']) == {'900002'}
for sid,name,group in [('900001','국어','국어'),('900002','수학','수학'),('900003','통합사회','사회탐구'),('900004','통합과학','과학탐구')]:
    meta=json.loads((ROOT/f'data/D300/{sid}.json').read_text())
    assert (meta['subject'],meta['group'])==(name,group)
    assert meta['papers']==[]

# 실제 갱신 함수로 새 회차·늦게 온 정답을 채워도 기존 payload와 samples는 보존된다.
current=API.read_payload(text);before=copy.deepcopy(current)
REFRESH.merge(current,{'D300':{'158':{'2099':[['수능','20991119','0new.pdf','','']]}}},REFRESH.known_subjects(text))
for g in before:
    for s in before[g]:
        for y,rows in before[g][s].items(): assert current[g][s][y]==rows
blob=__import__('base64').b64encode(REFRESH.squeeze(json.dumps(current,ensure_ascii=False).encode())).decode()
refreshed=REFRESH.PAYLOAD_RE.sub(lambda m:m[1]+blob+m[3],text,count=1)
assert API.read_samples(refreshed)==samples
assert API.samples_for(API.read_samples(refreshed),'D300','900003')==API.samples_for(samples,'D300','900003')
print('원본·학년도·과목 매핑·별도 공개분·갱신 보존 확인')

_srv,url=site()
with sync_playwright() as pw:
    browser=pw.chromium.launch(executable_path=CHROME)
    ctx=browser.new_context(viewport={'width':360,'height':900},service_workers='block')
    # Android 창구가 있어도 공식 fileDown 링크는 네이티브 다운로드로 넘기지 않는다.
    ctx.add_init_script('window.nativeCalls=[]; window.GijulNative={openPaper:(...a)=>nativeCalls.push(a),openPaperIn:(...a)=>nativeCalls.push(a)};')
    pg=ctx.new_page();errors=[]
    pg.on('pageerror',lambda e:errors.append(str(e)))
    for sid,year in [('900001',2028),('900002',2022),('900003',2028),('900004',2028),('63004',2017),('80003',2018),('140122',2022),('900011',2028),('900019',2028)]:
        pg.goto(url+f'#/D300/{sid}/{year-1}/all');pg.wait_for_selector('.sample')
        assert f'{year}학년도' in pg.locator('#yr').inner_text()
        assert pg.locator('.sample .chk,.sample .record,.sample .send,.sample [data-nm]').count()==0
        assert pg.evaluate('document.documentElement.scrollWidth<=innerWidth')
        assert pg.evaluate('SAMPLES.filter(p=>p.schoolYear===%d).every(p=>sampleLabel(p)==="%d학년도"&&sampleLabel(p,true)==="%s")'%(year,year,str(year)[2:]))
    assert pg.evaluate('url("0legacy.pdf","20251113")')=='https://wdown.ebsi.co.kr/W61001/01exam/20251113/go3/legacy.pdf'
    pg.goto(url+'#/D300/900003/2027/gov');pg.wait_for_selector('.sample')
    assert pg.locator('.sample').count()==2
    first=pg.locator('.sample .acts a').first
    target=first.get_attribute('href')
    ctx.route('https://www.suneung.re.kr/**',lambda route:route.fulfill(status=200,content_type='text/html',body='official source'))
    ctx.route('https://www.moe.go.kr/**',lambda route:route.fulfill(status=200,content_type='text/html',body='official source'))
    with ctx.expect_page() as opened:first.click()
    popup=opened.value;popup.wait_for_load_state();assert popup.url==target
    assert pg.evaluate('nativeCalls')==[]
    pg.screenshot(path='/tmp/direct-mogo-samples-mobile.png',full_page=True)
    pg.goto(url+'s/D300/900003.html');pg.wait_for_selector('.sample')
    assert pg.locator('.sample').count()==2 and pg.locator('.sample [data-nm]').count()==0
    with ctx.expect_page() as opened:pg.locator('.sample-links a').first.click()
    opened.value.wait_for_load_state();assert pg.evaluate('nativeCalls')==[]
    assert not errors,errors
    browser.close()
print('화면·짧은 학년도·필터·기존 링크·Android 창구 격리 확인')
