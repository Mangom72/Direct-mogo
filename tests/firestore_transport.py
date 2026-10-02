"""Real vendored Firebase SDK against local Auth/Firestore emulators, no production project."""
import os, sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from harness import CHROME, site
from playwright.sync_api import sync_playwright
assert os.environ.get('FIRESTORE_EMULATOR_HOST') in ('127.0.0.1:8080','localhost:8080'), 'Run only in the local Firebase emulator'
_srv, SITE=site()
CONFIG={'firebase':{'apiKey':'local-emulator-key','authDomain':'demo-gijul-sync.firebaseapp.com','projectId':'demo-gijul-sync','appId':'1:123:web:local'},'googleWebClientId':''}
SETUP='''async a=>{
  window.__backend=await GijulFirebase(a.config);
  firebase.auth().useEmulator('http://127.0.0.1:9099',{disableWarnings:true});
  firebase.firestore().useEmulator('127.0.0.1',8080);
  const auth=firebase.auth();
  const credentials=a.first ? await auth.createUserWithEmailAndPassword('sync-local@example.invalid','emulator-fixture-password') : await auth.signInWithEmailAndPassword('sync-local@example.invalid','emulator-fixture-password');
  window.__uid=credentials.user.uid;
  window.__server=[];
  window.__unsubscribe=__backend.listen(__uid,null,ops=>{const all=new Map(__server.map(o=>[o.id,o]));for(const o of ops)all.set(o.id,o);__server=[...all.values()];},e=>{throw e;});
  return __uid;
}'''
with sync_playwright() as pw:
    browser=pw.chromium.launch(executable_path=CHROME)
    ctx=browser.new_context(service_workers='block',bypass_csp=True)
    a=ctx.new_page();a.goto(SITE,wait_until='load');a.wait_for_selector('.item .chk')
    uid=a.evaluate(SETUP,{'config':CONFIG,'first':True})
    assert a.evaluate('async()=>((await __backend.current()).uid)')==uid
    ctx.set_offline(True)
    a.evaluate('''async()=>{
      await firebase.firestore().disableNetwork();
      window.__confirmed=false;
      window.__event={v:1,id:crypto.randomUUID(),clock:1,payload:JSON.stringify([{slot:'score',key:'D300/158/20260902/시험',value:42}])};
      window.__upload=__backend.sendBatch(__uid,[__event]).then(()=>__confirmed=true).catch(()=>window.__offlineFailure=true);
    }''')
    a.wait_for_timeout(500)
    assert not a.evaluate('()=>__confirmed'), 'Offline write falsely confirmed by server'
    ctx.set_offline(False)
    a.evaluate('async()=>{await firebase.firestore().enableNetwork();await __backend.sendBatch(__uid,[__event]);__confirmed=true;}')
    a.wait_for_function('()=>__confirmed && __server.length===1')
    other=browser.new_context(service_workers='block',bypass_csp=True)
    b=other.new_page();b.goto(SITE,wait_until='load');b.wait_for_selector('.item .chk')
    assert b.evaluate(SETUP,{'config':CONFIG,'first':False})==uid
    b.wait_for_function('()=>__server.length===1')
    a.evaluate('async()=>{await __backend.send(__uid,__event);}')
    b.wait_for_timeout(100)
    assert b.evaluate('()=>__server.length')==1, 'Idempotent retry created duplicate records'
    b.evaluate('''async()=>{await __backend.sendBatch(__uid,[{v:1,id:crypto.randomUUID(),clock:2,payload:JSON.stringify([{slot:'wrong',key:'D300/158/20260902/시험',value:[3,7]}])},{v:1,id:crypto.randomUUID(),clock:3,payload:JSON.stringify([{slot:'theme',key:'settings',value:'dark'}])}]);}''')
    a.wait_for_function('()=>__server.length===3')
    assert a.evaluate('()=>__server.map(x=>x.id).sort()')==b.evaluate('()=>__server.map(x=>x.id).sort()')
    # Server timestamp checkpoint returns only the inclusive boundary, not older history.
    b.evaluate("""()=>{__unsubscribe();const last=__server.reduce((a,b)=>a.receivedAt.toMillis()>b.receivedAt.toMillis()?a:b).receivedAt;
      window.__since=[];__unsubscribe=__backend.listen(__uid,{seconds:last.seconds,nanoseconds:last.nanoseconds},ops=>__since.push(...ops),e=>{throw e;});}""")
    b.wait_for_function('()=>__since.length===2')
    assert b.evaluate('()=>__since.every(x=>x.clock>=2)'), 'Checkpoint replayed old history'
    b.evaluate("""async()=>{await __backend.send(__uid,{v:1,id:crypto.randomUUID(),clock:4,payload:JSON.stringify([{slot:'score',key:'D300/158/20260902/시험',value:43}])});}""")
    b.wait_for_function('()=>__since.length===3')
    a.wait_for_function('()=>__server.length===4')
    browser.close()
print('Actual Firebase SDK: offline write waits for server, two browser sessions receive identical events, duplicate retry is idempotent')
