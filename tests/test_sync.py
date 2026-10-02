"""Durable sync journal and page integration; no real account credentials are used."""
import sys, pathlib, json, hashlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from harness import CHROME, ROOT, site
from playwright.sync_api import sync_playwright
_srv, SITE = site()
with sync_playwright() as pw:
    browser = pw.chromium.launch(executable_path=CHROME)
    page = browser.new_page(service_workers='block')
    page.goto(SITE, wait_until='load')
    page.wait_for_selector('.item .chk')
    report = page.evaluate('''async()=>{
      const {Journal}=GijulJournal, k='D300/158/20260902/시험';
      const score=JSON.stringify(['score',k]),wrong=JSON.stringify(['wrong',k]);
      const a=await new Journal('sync-test-a').open(),b=await new Journal('sync-test-b').open();
      await a.bind('owner');await b.bind('owner');
      const first=await a.capture({}, {[score]:42});
      if(first.pending.length!==1) throw Error('local write not pending');
      a.db.close();const reopened=await new Journal('sync-test-a').open();
      let state=await reopened.read();if(state.pending.length!==1 || state.view[score]!==42) throw Error('restart lost pending write');
      const other=await b.capture({}, {[wrong]:[3,7]});
      await reopened.receive(other.pending);await b.receive(first.pending);
      if(JSON.stringify((await reopened.read()).view)!==JSON.stringify((await b.read()).view)) {
        const x=(await reopened.read()).view,y=(await b.read()).view;
        if(x[score]!==y[score] || JSON.stringify(x[wrong])!==JSON.stringify(y[wrong])) throw Error('independent fields did not merge');
      }
      await reopened.receive(first.pending);if((await reopened.read()).pending.length!==1) throw Error('receive falsely acknowledged pending event');
      await reopened.ack(first.pending[0].id);if((await reopened.read()).pending.length) throw Error('ack did not remove event');
      const deleted=await reopened.capture({[score]:42},{});
      await b.receive(deleted.pending);
      await b.capture({}, {[score]:42},true);
      if((await b.read()).view[score]!==null) throw Error('old backup resurrected deletion');
      const x=await reopened.capture({}, {[score]:50}),y=await b.capture({}, {[score]:40});
      await reopened.receive(y.pending);await b.receive(x.pending);
      if((await reopened.read()).view[score]!==(await b.read()).view[score]) throw Error('concurrent edits did not converge');
      let blocked=false;try{await reopened.bind('other-user');}catch(e){blocked=e.message==='ACCOUNT_MISMATCH';}
      if(!blocked) throw Error('account isolation failed');
      const count=(await reopened.read()).pending.length;
      try{await reopened.capture({}, {[score]:42.5});}catch(e){}
      if((await reopened.read()).pending.length!==count) throw Error('invalid write partially committed');
      const at={seconds:1234567890,nanoseconds:123};
      const malformed={v:1,id:crypto.randomUUID(),clock:100,payload:'[invalid',receivedAt:at};
      const result=await reopened.receive([malformed,{...x.pending[0],receivedAt:at}]);
      if(result.invalid!==1 || (await reopened.read()).cursor.nanoseconds!==123) throw Error('invalid event blocked checkpoint');
      const c=await new Journal('sync-test-large').open();await c.bind('owner');
      const lots={};for(let n=0;n<300;n++)lots[JSON.stringify(['wrong',k+n])]=Array.from({length:999},(_,i)=>i+1);
      const large=await c.capture({},lots);
      if(!large.pending.every(op=>op.payload.length<=65536) || Object.keys(large.view).length!==300) throw Error('large import lost entries');
      return ['restart/outbox','server ACK','independent fields','delete markers','concurrent convergence','account isolation','atomic invalid rollback','bounded import','invalid quarantine/checkpoint'];
    }''')
    print('Journal:', ', '.join(report))
    page.evaluate('''async()=>{
      const backend=await GijulFirebase({firebase:{apiKey:'local-fixture-key',projectId:'demo-login-fixture',authDomain:'demo-login-fixture.firebaseapp.com',appId:'1:123:web:fixture'},googleWebClientId:'fixture.apps.googleusercontent.com'});
      firebase.auth().signInWithCredential=async()=>({user:{uid:'native-fixture'}});
      window.GijulNative={googleSignIn:(client,id)=>window.__requestId=id,cancelGoogleSignIn:id=>window.__cancelled=id};
      let done=false;const first=backend.login().then(u=>{done=true;return u;});
      await new Promise(r=>setTimeout(r,0));
      gijulGoogleSignIn(crypto.randomUUID(),true,'stale-token');
      await new Promise(r=>setTimeout(r,10));if(done) throw Error('stale native login response accepted');
      gijulGoogleSignIn(__requestId,true,'fixture-token');
      if((await first).uid!=='native-fixture') throw Error('matching native login failed');
      const timer=window.setTimeout;window.setTimeout=(f,t)=>timer(f,t===120000?20:t);
      try{await backend.login();throw Error('native login never timed out');}catch(e){if(!__cancelled || __cancelled!==__requestId) throw Error('timed out native login not cancelled');}
      finally{window.setTimeout=timer;delete window.GijulNative;}
    }''')
    print('Native login adapter: stale request ignored, timeout cancels the matching native request')

    for name,entry in json.loads((ROOT/'sync/vendor/source.json').read_text()).items():
        assert hashlib.sha256((ROOT/'sync/vendor'/name).read_bytes()).hexdigest()==entry['sha256']
    ctx=browser.new_context(service_workers='block')
    ctx.route('**/sync/config.json',lambda r:r.fulfill(content_type='application/json',body=json.dumps({'enabled':True,'firebase':{'projectId':'test'},'googleWebClientId':'test'})))
    ctx.route('**/sync/firebase.js',lambda r:r.fulfill(content_type='application/javascript',body='''
      window.__uploads=[];window.__remote=[];window.__accept=false;
      window.GijulFirebase=async()=>({
        current:()=>new Promise(resolve=>window.__initialAuth=resolve),login:async()=>({uid:'test-owner'}),logout:async()=>{},
        listen:(uid,cursor,data,error)=>{window.__deliver=data;setTimeout(()=>data(__remote),0);return()=>{};},
        send:(uid,op)=>{window.__uploads.push(op);return new Promise((resolve,reject)=>{
          window.__finish=()=>{__remote.push(op);resolve();};window.__reject=()=>reject(Error('offline'));
          if(__accept) __finish();
        });}
      });'''))
    pg=ctx.new_page();pg.goto(SITE,wait_until='load');pg.wait_for_selector('.item .chk')
    pg.wait_for_function('()=>GijulSync.state().enabled')
    pg.wait_for_function('()=>typeof __initialAuth==="function"')
    pg.evaluate('()=>GijulSync.login()')
    pg.wait_for_function('()=>window.__finish && GijulSync.state().on')
    pg.evaluate('()=>__initialAuth(null)')
    pg.wait_for_timeout(50)
    assert pg.evaluate('()=>GijulSync.state().on'), 'Late initial auth query disconnected the new login'
    pg.evaluate('()=>__reject()')
    pg.wait_for_timeout(100)
    assert pg.evaluate('()=>GijulSync.state().pending')>0
    original=pg.evaluate('()=>__uploads[0].id')
    pg.evaluate('()=>{__accept=true;GijulSync.retry();}')
    pg.wait_for_function('()=>GijulSync.state().pending===0')
    assert pg.evaluate('()=>__uploads[1].id')==original
    key=pg.locator('.item .chk').first.get_attribute('data-k')
    pg.evaluate('k=>{SOLVED[k]="20261003";RECORDS[k]={score:85,wrong:[1,3]};saveSolved();saveRecords();tellSolved();}',key)
    pg.wait_for_function('()=>__uploads.some(op=>op.payload.includes("85"))')
    pg.wait_for_function('()=>GijulSync.state().pending===0')
    remote={'v':1,'id':'11111111-1111-4111-8111-111111111111','clock':1000,'payload':json.dumps([{'slot':'score','key':key,'value':90}])}
    pg.evaluate('op=>__deliver([...__remote,op])',remote)
    pg.wait_for_function('k=>RECORDS[k]?.score===90',arg=key)
    assert pg.evaluate('k=>RECORDS[k].wrong',key)==[1,3]
    # Logging out preserves outbox and never reconnects the old Drive file.
    pg.evaluate('()=>GijulSync.logout()');assert not pg.evaluate('()=>GijulSync.state().on')
    pg.evaluate('k=>{RECORDS[k].score=95;saveRecords();tellSolved();}',key)
    pg.wait_for_function('()=>GijulSync.state().pending>0')
    pg.reload(wait_until='load');pg.wait_for_selector('.item .chk')
    pg.wait_for_function('()=>GijulSync.state().pending>0')
    assert pg.evaluate('k=>RECORDS[k].score',key)==95
    # Process death before the IndexedDB transaction preserves the synchronous intent.
    intent=pg.evaluate("""k=>{
      const encoded=JSON.stringify(['score',k]);
      const intent={uid:'test-owner',id:crypto.randomUUID(),tab:'crash-test',serial:1,before:{[encoded]:95},after:{[encoded]:96}};
      localStorage.setItem('gijul.sync.intent.v1:'+intent.id,JSON.stringify(intent));
      RECORDS[k].score=96;saveRecords();return intent;
    }""",key)
    pg.reload(wait_until='load');pg.wait_for_selector('.item .chk')
    pg.wait_for_function('k=>RECORDS[k]?.score===96',arg=key)
    pg.wait_for_function('id=>!localStorage.getItem("gijul.sync.intent.v1:"+id)',arg=intent['id'])
    # Process death after commit but before removing the intent does not create a new event.
    before_clock=pg.evaluate("""async k=>{
      const encoded=JSON.stringify(['score',k]),journal=await new GijulJournal.Journal().open();
      const intent={uid:'test-owner',id:crypto.randomUUID(),tab:'crash-test',serial:2,before:{[encoded]:96},after:{[encoded]:97}};
      localStorage.setItem('gijul.sync.intent.v1:'+intent.id,JSON.stringify(intent));
      await journal.capture(intent.before,intent.after,false,intent.id);
      RECORDS[k].score=97;saveRecords();
      return journal.change(s=>s.clock);
    }""",key)
    pg.reload(wait_until='load');pg.wait_for_selector('.item .chk')
    pg.wait_for_function('k=>RECORDS[k]?.score===97',arg=key)
    pg.wait_for_function('()=>!Object.keys(localStorage).some(k=>k.startsWith("gijul.sync.intent.v1:"))')
    after_clock=pg.evaluate('async()=>{const j=await new GijulJournal.Journal().open();return j.change(s=>s.clock);}')
    assert before_clock==after_clock, 'Committed intent was replayed as a new change after restart'
    print('Controller: late initial auth ignored, retry same UUID, failure retains outbox, remote field merge, signed-out restart, crash intent receipt')
    browser.close()
print('전체: 통과')
