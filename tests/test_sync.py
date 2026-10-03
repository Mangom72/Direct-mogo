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
      // A tab that loaded an intent before another tab consumed it cannot replay it.
      const shared=await new Journal('sync-test-shared').open(),peer=await new Journal('sync-test-shared').open();await shared.bind('owner');
      const intentId=crypto.randomUUID(),intentKey='test-intent:'+intentId;localStorage.setItem(intentKey,'live');
      await shared.capture({}, {[score]:40},false,intentId,()=>localStorage.getItem(intentKey)!==null);
      localStorage.removeItem(intentKey);await shared.releaseReceipt(intentId);
      await shared.receive([{v:1,id:crypto.randomUUID(),clock:10,payload:JSON.stringify([{slot:'score',key:k,value:90}])}]);
      await peer.capture({}, {[score]:40},false,intentId,()=>localStorage.getItem(intentKey)!==null);
      if((await peer.read()).view[score]!==90 || (await peer.read()).pending.length!==1) throw Error('consumed intent replayed from another tab');
      const fav=JSON.stringify(['favs','settings']),base=[{g:'D300',s:'국어'}];
      const fa=await new Journal('sync-test-favs-a').open(),fb=await new Journal('sync-test-favs-b').open();await fa.bind('owner');await fb.bind('owner');
      const initial=await fa.capture({}, {[fav]:base},true);await fb.receive(initial.pending);await fa.ackMany(initial.pending.map(o=>o.id));
      const ax=await fa.capture({[fav]:base},{[fav]:[...base,{g:'D300',s:'수학'}]}),bx=await fb.capture({[fav]:base},{[fav]:[...base,{g:'D300',s:'영어'}]});
      await fa.receive(bx.pending);await fb.receive(ax.pending);
      const union=(await fa.read()).view[fav];if(union.length!==3 || JSON.stringify(union)!==JSON.stringify((await fb.read()).view[fav])) throw Error('independent subject additions lost');
      const removed=await fa.capture({[fav]:union},{[fav]:union.filter(f=>f.s!=='국어')});
      await fb.receive(removed.pending);await fb.receive(initial.pending);
      if((await fb.read()).view[fav].some(f=>f.s==='국어')) throw Error('subject removal resurrected by legacy event');
      // Reordering preserves a concurrently added member, and replay order is immaterial.
      const ordered=await fa.capture({[fav]:(await fa.read()).view[fav]},{[fav]:[...(await fa.read()).view[fav]].reverse()});
      const fc=await new Journal('sync-test-favs-shuffled').open();await fc.bind('owner');
      for(const op of [...initial.pending,...ax.pending,...bx.pending,...removed.pending,...ordered.pending].reverse()) await fc.receive([op]);
      if(JSON.stringify((await fc.read()).view[fav])!==JSON.stringify((await fa.read()).view[fav])) throw Error('out-of-order subjects did not converge');
      const events=[...new Map([...initial.pending,...ax.pending,...bx.pending,...removed.pending,...ordered.pending].map(o=>[o.id,o])).values()];
      const expected=JSON.stringify((await fa.read()).view[fav]);let permutations=0;
      function replay(prefix,remaining){
        if(!remaining.length){const state={clock:0,cells:{}};for(const op of prefix)GijulJournal.fold(state,op);if(JSON.stringify(GijulJournal.cells(state)[fav])!==expected)throw Error('subject replay permutation diverged');permutations++;return;}
        remaining.forEach((op,i)=>replay([...prefix,op],remaining.filter((_,n)=>n!==i)));
      }
      replay([],events);if(permutations!==120)throw Error('subject replay coverage changed');
      const legacy={v:1,id:crypto.randomUUID(),clock:20,payload:JSON.stringify([{slot:'favs',key:'settings',value:base}])};
      await fc.receive([legacy]);await fc.receive(events);
      if(JSON.stringify((await fc.read()).view[fav])!==JSON.stringify(base))throw Error('old client replacement resurrected prior deltas');
      if(!(await reopened.history()).some(h=>h.slot==='score' && h.value===42)) throw Error('overwritten value missing from recovery history');
      return ['restart/outbox','server ACK','independent fields','delete markers','concurrent convergence','account isolation','atomic invalid rollback','bounded import','invalid quarantine/checkpoint','cross-tab intent deduplication','subject merge/removal/order','value recovery history'];
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
      window.__uploads=[];window.__remote=[];window.__accept=false;window.__listeners=[];window.__loginCount=0;
      window.GijulFirebase=async()=>window.__adapter=({
        current:()=>new Promise(resolve=>window.__initialAuth=resolve),watch:callback=>{window.__authWatch=callback;return()=>{};},login:async()=>{__loginCount++;return {uid:'test-owner'};},logout:async()=>{if(window.__holdLogout)await new Promise(r=>window.__finishLogout=r);},
        listen:(uid,cursor,data,error)=>{window.__deliver=data;__listeners.push(data);setTimeout(()=>data(__remote),0);return()=>{};},
        send:(uid,op)=>{window.__uploads.push(op);return new Promise((resolve,reject)=>{
          window.__finish=()=>{__remote.push(op);resolve();};window.__reject=()=>reject(Error('offline'));
          if(__accept) __finish();
        });}
      });'''))
    pg=ctx.new_page();pg.goto(SITE,wait_until='load');pg.wait_for_selector('.item .chk')
    pg.wait_for_function('()=>GijulSync.state().enabled')
    pg.click('#bakBtn');assert not pg.locator('#cloudSyncDisconnect').is_visible(), 'Signed-out account controls are visible'
    pg.wait_for_function('()=>typeof __initialAuth==="function"')
    pg.evaluate('()=>GijulSync.login()')
    pg.wait_for_function('()=>window.__finish && GijulSync.state().on')
    pg.evaluate('()=>__initialAuth(null)')
    pg.wait_for_timeout(50)
    assert pg.evaluate('()=>GijulSync.state().on'), 'Late initial auth query disconnected the new login'
    assert pg.locator('#cloudSyncDisconnect').is_visible(), 'Signed-in account controls are hidden'
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
    assert not pg.locator('#cloudSyncDisconnect').is_visible(), 'Logged-out account controls remain visible'
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
    # A local edit made during a suspended receive stays visible before any server echo.
    pg.evaluate('()=>__initialAuth(null)')
    pg.evaluate('()=>{__accept=true;return GijulSync.login();}')
    pg.wait_for_function('()=>GijulSync.state().on && GijulSync.state().pending===0')
    pg.evaluate("""()=>{
      const receive=GijulJournal.Journal.prototype.receive;
      GijulJournal.Journal.prototype.receive=async function(ops){
        GijulJournal.Journal.prototype.receive=receive;
        await new Promise(r=>window.__releaseReceive=r);return receive.call(this,ops);
      };
      const apply=gijulApplySync;window.__appliedScores=[];
      window.gijulApplySync=view=>{__appliedScores.push(view[JSON.stringify(['score',window.__testKey])]);apply(view);};
    }""")
    pg.evaluate('k=>window.__testKey=k',key)
    pending_remote={**remote,'id':'22222222-2222-4222-8222-222222222222','clock':2000,'payload':json.dumps([{'slot':'score','key':key,'value':50}])}
    pg.evaluate('op=>{void __deliver([op]);}',pending_remote)
    pg.wait_for_function('()=>typeof __releaseReceive==="function"')
    pg.evaluate('k=>{RECORDS[k].score=98;saveRecords();tellSolved();__releaseReceive();}',key)
    pg.wait_for_function('()=>GijulSync.state().pending===0 && __uploads.some(o=>o.payload.includes("98"))')
    assert pg.evaluate('k=>RECORDS[k].score',key)==98, 'Receive overwrote an in-flight local edit'
    assert 50 not in pg.evaluate('()=>__appliedScores'), 'Remote value flashed over the local edit before commit'
    # Disconnect blocks login and further sends immediately, even before signOut finishes.
    old_listener=pg.evaluate('()=>__listeners.length-1')
    pg.evaluate('()=>{__holdLogout=true;void GijulSync.logout();}')
    pg.wait_for_function('()=>typeof __finishLogout==="function"')
    count=pg.evaluate('()=>__loginCount')
    pg.evaluate('()=>GijulSync.login()')
    assert pg.evaluate('()=>__loginCount')==count and not pg.evaluate('()=>GijulSync.state().on'), 'Login raced with pending logout'
    pg.evaluate('()=>{__holdLogout=false;__finishLogout();}')
    pg.wait_for_function('()=>!GijulSync.state().busy')
    pg.evaluate('()=>GijulSync.login()')
    pg.wait_for_function('()=>GijulSync.state().on && GijulSync.state().pending===0')
    stale={**pending_remote,'id':'33333333-3333-4333-8333-333333333333','clock':9999,'payload':json.dumps([{'slot':'score','key':key,'value':1}])}
    pg.evaluate('a=>{void __listeners[a.index]([a.op]);}',{'index':old_listener,'op':stale})
    pg.wait_for_timeout(100)
    assert pg.evaluate('k=>RECORDS[k].score',key)==98, 'Stale same-account listener applied after reconnect'
    pg.evaluate('()=>__authWatch(null)')
    assert not pg.evaluate('()=>GijulSync.state().on'), 'External Auth logout left the controller connected'
    # A second tab observes the durable journal while signed out/offline.
    peer=ctx.new_page();peer.goto(SITE,wait_until='load');peer.wait_for_selector('.item .chk')
    peer.wait_for_function('()=>typeof __initialAuth==="function"')
    peer.evaluate('()=>__initialAuth(null)')
    pg.evaluate('()=>GijulSync.logout()')
    pg.evaluate('k=>{RECORDS[k].score=99;saveRecords();tellSolved();}',key)
    peer.wait_for_function('k=>RECORDS[k]?.score===99',arg=key)
    peer.evaluate('k=>{RECORDS[k].wrong=[5,8];saveRecords();tellSolved();}',key)
    pg.wait_for_function('k=>JSON.stringify(RECORDS[k]?.wrong)==="[5,8]"',arg=key)
    assert pg.evaluate('k=>RECORDS[k].score',key)==99
    # Choosing a losing value makes a new durable normal event; legacy backups stay intact.
    pg.evaluate("""async k=>{
      const entry=(await GijulSync.history()).find(h=>h.key===k && h.slot==='score' && h.value===97);
      if(!entry) throw Error('missing older score');await GijulSync.restore(entry);
    }""",key)
    peer.wait_for_function('k=>RECORDS[k]?.score===97',arg=key)
    pg.evaluate('()=>closeSheet()')
    pg.click('#bakBtn');pg.get_by_role('button',name='이력 보기',exact=True).click()
    pg.wait_for_function('()=>sheetNm.textContent==="동기화 변경 이력" && sheetList.querySelector(".sfile")')
    assert pg.get_by_role('button',name='복원',exact=True).count()>0
    pg.get_by_role('button',name='복원',exact=True).first.click()
    assert pg.get_by_role('button',name='복원 확인',exact=True).count()==1
    pg.set_viewport_size({'width':300,'height':600})
    assert pg.evaluate('()=>document.querySelector(".sheet-card").scrollWidth<=document.querySelector(".sheet-card").clientWidth')
    # Only the in-flight confirmed chunk is ACKed when logout interrupts a large outbox.
    peer.close()
    pg.evaluate("""async()=>{
      const j=await new GijulJournal.Journal().open(),pending=(await j.read()).pending;
      await j.ackMany(pending.map(o=>o.id));
      for(let n=0;n<51;n++)await j.capture({}, {[JSON.stringify(['score','D300/158/20260902/chunk-'+n])]:n});
    }""")
    pg.evaluate('''()=>{window.__batches=[];__adapter.sendBatch=(uid,ops)=>{__batches.push(ops);return new Promise(resolve=>window.__finishBatch=()=>{__remote.push(...ops);resolve();});};}''')
    pg.evaluate('()=>{__accept=false;void GijulSync.login();}')
    pg.wait_for_function('()=>__batches.length===1')
    pg.evaluate('()=>GijulSync.logout()')
    pg.evaluate('()=>__finishBatch()')
    pg.wait_for_timeout(100)
    assert pg.evaluate('()=>__batches.length')==1, 'Logout allowed further outbox chunks to send'
    remaining=pg.evaluate('async()=>{const j=await new GijulJournal.Journal().open();return (await j.read()).pending.length;}')
    assert remaining==1, 'Unsent chunk was acknowledged or confirmed chunk was retained'
    print('Controller races: edit during receive, logout/login exclusion, stale listener, offline peer refresh, older value restore and confirmation UI')
    browser.close()
print('전체: 통과')
