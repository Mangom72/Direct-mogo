"""Loss prevention: storage refusal, interrupted writes, concurrent vault readers and identities."""
import json
from pathlib import Path
from harness import CHROME, ROOT, site
from playwright.sync_api import sync_playwright
_srv, SITE = site()
with sync_playwright() as pw:
    browser = pw.chromium.launch(executable_path=CHROME)
    ctx = browser.new_context(service_workers='block', viewport={'width':390,'height':844})
    ctx.route('**/sync/config.json', lambda r:r.fulfill(content_type='application/json',body='{"enabled":false}'))
    page = ctx.new_page(); page.goto(SITE); page.wait_for_selector('.item')
    # Every real row must have an unambiguous native filesystem name, within byte limits.
    rows=[]
    for path in (ROOT/'data').glob('D*/*.json'):
        data=json.loads(path.read_text())
        for p in data['papers']:
            rows.append([p['year'],p['title'],data['subject'],data['grade'],data['subjectId'],p['date']])
    identities=page.evaluate('''rows=>rows.map(([y,t,s,g,id,d])=>({folder:folderName(y,t,s,g,id,d),file:fileName(y,t,s,'문제','same.pdf',g,id,d)}))''',rows)
    for field in ['folder','file']:
        names={}
        for row,item in zip(rows,identities):
            key=tuple(map(str,[row[3],row[4],row[5],row[1]]))
            assert item[field] not in names or names[item[field]]==key, (field,row)
            names[item[field]]=key
            assert len(item[field].encode())<=255
    result=page.evaluate('''()=>{
      const key='D300/158/20260902/시험';
      const bad=readBackup(JSON.stringify({v:1,subs:[],solved:{[key]:'20260230'},times:{[key]:{spent:1e309,limit:-1}},records:{[key]:{score:10000,wrong:[3]}}}));
      if(Object.keys(bad.solved).length||Object.keys(bad.times).length||bad.records[key].score!==undefined||bad.rejected!==3)throw Error('Invalid backup values survived');
      const before=copySnapshot(),next=copySnapshot();next.solved[key]='20261001';next.records[key]={score:33};
      const set=Storage.prototype.setItem;
      Storage.prototype.setItem=function(k,v){if(k===RECORD_KEY)throw new DOMException('fixture','QuotaExceededError');return set.call(this,k,v);};
      const stored=persistSnapshot(next);Storage.prototype.setItem=set;
      delete before.at;const after=copySnapshot();delete after.at;
      if(stored||JSON.stringify(after)!==JSON.stringify(before))throw Error('Refused storage changed live state');
      if(JSON.parse(localStorage.getItem(SOLVED_KEY)||'{}')[key])throw Error('Refused storage left partial solved record');
      if(!persistSnapshot(next))throw Error('Retry failed');
      const imported=readBackup(JSON.stringify({v:1,subs:[],solved:{[key]:'20260101'},records:{[key]:{score:20,wrong:[2]}}}));
      if(!applyBackup(imported,'merge').stored||SOLVED[key]!=='20261001'||RECORDS[key].score!==33||RECORDS[key].wrong[0]!==2)throw Error('Merge overwrote current fields');
      return key;
    }''')
    # The actual form keeps the user's typed score and the modal on storage refusal.
    page.locator('.item .record').first.click();page.fill('#recordScore','33')
    page.evaluate("""()=>{window.__set=Storage.prototype.setItem;Storage.prototype.setItem=function(k,v){if(k===RECORD_KEY)throw new DOMException('fixture','QuotaExceededError');return __set.call(this,k,v);};}""")
    page.click('.record-save')
    assert page.locator('#recordForm').is_visible() and page.locator('#recordScore').input_value()=='33'
    assert '저장하지 못했습니다' in page.locator('.record-error').inner_text()
    page.evaluate('()=>Storage.prototype.setItem=__set');page.click('.record-save')
    assert not page.locator('#recordForm').is_visible()
    # A crash after one legacy-key write rolls back before records are loaded on next boot.
    page.evaluate('''k=>{localStorage.setItem('gijul.state.transaction.v1',JSON.stringify({[SOLVED_KEY]:localStorage.getItem(SOLVED_KEY),[RECORD_KEY]:localStorage.getItem(RECORD_KEY)}));localStorage.setItem(SOLVED_KEY,JSON.stringify({[k]:'20260101'}));}''',result)
    page.reload();page.wait_for_selector('.item')
    assert page.evaluate('k=>SOLVED[k]',result)=='20261001'
    assert page.evaluate('k=>RECORDS[k].score',result)==33
    # A normal reader in another tab must not destroy an in-progress save.
    page.evaluate('''()=>{window.__realFetch=fetch;window.fetch=(url,options)=>String(url).includes('wdown.ebsi.co.kr')?new Promise(resolve=>{window.__release=()=>resolve(new Response('fixture-pdf'));}):__realFetch(url,options);openSheet(ROWS[0],null);window.__save=saveAll();}''')
    page.wait_for_function('()=>!!window.__release')
    peer=ctx.new_page();peer.goto(SITE);peer.wait_for_selector('.item');peer.evaluate('async()=>await Vault.sync()')
    page.evaluate('''async()=>{fetch=async()=>new Response('fixture-pdf');__release();await __save;}''')
    assert page.evaluate('()=>sheetAll.disabled && sheetAll.classList.contains("kept")')
    assert page.evaluate('async()=>{const files=await Vault.list();return ROWS[0].files.every(f=>files.some(x=>x.url===f.url));}')
    # A later-added solution reopens the save action; the existing files are retained.
    page.evaluate('''async()=>{const row=ROWS[0];row.files.push({url:'https://wdown.ebsi.co.kr/W61001/01exam/fixture-later.pdf',name:'later.pdf'});await Vault.sync();openSheet(row,null);}''')
    assert not page.locator('#sheetAll').is_disabled()
    assert '나머지' in page.locator('#sheetAll').inner_text()
    assert not page.evaluate('async()=>(await caches.keys()).some(n=>n.startsWith(VAULT_BOX+"pending:"))')
    print('Verified real-row identities, invalid import, refused writes/retry/restart, local-field merge, two-tab save and incomplete retry')
    ctx.close();browser.close()
