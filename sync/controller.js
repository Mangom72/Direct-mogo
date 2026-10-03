(function(root){
  "use strict";
  let authPending=false,authEpoch=0,connection=0,initialized=false,config=null,journal=null,backend=null,uid=null,stop=null,applying=false,ready=false,baseline=null,work=Promise.resolve(),sending=false,timer=null,peerQueued=false,peerDirty=false;
  const intentPrefix="gijul.sync.intent.v1:",wakeKey="gijul.sync.wake.v1",tab=crypto.randomUUID();let serial=0;
  try{uid=localStorage.getItem("gijul.sync.uid.v1");}catch(e){}
  let state={enabled:false,on:false,busy:false,pending:0,invalid:0,message:""};
  const notify=()=>root.dispatchEvent(new Event("gijul-sync-state"));
  const fail=e=>{state.message=e.message==="ACCOUNT_MISMATCH"?"이 기기에 연결했던 Google 계정으로 로그인해 주세요":(/[가-힣]/.test(e.message || "") ? e.message : "동기화 연결을 확인하지 못했습니다. 기록은 이 기기에 남아 있습니다");state.busy=false;notify();};
  function queue(fn){const next=work.then(fn);work=next.catch(fail);return next;}
  function disconnect(){connection++;if(stop){stop();stop=null;}ready=false;}
  function wake(){try{localStorage.setItem(wakeKey,crypto.randomUUID());}catch(e){}}
  function intents(account){
    const out=[];
    for(let i=0;i<localStorage.length;i++){
      const key=localStorage.key(i);if(!key || !key.startsWith(intentPrefix)) continue;
      try{
        const intent=JSON.parse(localStorage.getItem(key));
        if(intent && intent.uid===account && typeof intent.id==="string" && typeof intent.tab==="string" && Number.isSafeInteger(intent.serial) && intent.before && intent.after) out.push({key,intent});
      }catch(e){/* Keep unreadable intents for recovery; they must not block valid edits. */}
    }
    out.sort((a,b)=>a.intent.tab.localeCompare(b.intent.tab)||a.intent.serial-b.intent.serial);
    return out;
  }
  function apply(view){
    // A user can edit while an IndexedDB receive is awaiting completion. Keep
    // those synchronous intents visible until their own transaction commits.
    const merged={...root.gijulSyncSnapshot(),...view};
    for(const {intent} of intents(uid)) for(const key of new Set([...Object.keys(intent.before),...Object.keys(intent.after)])) merged[key]=intent.after[key]===undefined?null:intent.after[key];
    applying=true;
    try{root.gijulApplySync(merged);}finally{baseline=root.gijulSyncSnapshot();applying=false;}
  }
  async function flush(){
    if(sending || !backend || !uid || !ready || !state.on) return;
    sending=true;let drained=false;const session=connection,account=uid,adapter=backend,current=()=>session===connection && state.on && ready && account===uid;
    try{
      const batch=(await journal.read()).pending;if(!current()) return;
      state.pending=batch.length;notify();
      for(let i=0;i<batch.length;i+=50){
        if(!current()) return;
        const chunk=batch.slice(i,i+50);
        if(adapter.sendBatch) await adapter.sendBatch(account,chunk);
        else for(const op of chunk){if(!current()) return;await adapter.send(account,op);}
        // A confirmed upload remains safe to ACK even if logout occurred during
        // the request. Unsent chunks stay in the original account's journal.
        const pending=await journal.ackMany(chunk.map(op=>op.id));wake();
        if(!current()) return;
        state.pending=pending;notify();
      }
      drained=true;state.message=state.invalid?"일부 변경을 읽지 못했습니다. 이전 이력은 서버에 보존합니다":state.pending?"전송할 기록이 남아 있습니다":"동기화했습니다";
    }catch(e){if(current()) state.message="전송을 기다리는 중입니다. 기록은 이 기기에 남아 있습니다";}
    finally{sending=false;notify();if(ready && state.on && (session!==connection || (drained && state.pending))) void flush();}
  }
  async function commitIntent(key,intent){
    const result=await journal.capture(intent.before,intent.after,false,intent.id,()=>localStorage.getItem(key)!==null);
    localStorage.removeItem(key);
    await journal.releaseReceipt(intent.id);
    state.pending=result.pending.length;
    apply((await journal.read()).view);wake();notify();void flush();
  }
  async function recoverIntents(account){
    for(const {key,intent} of intents(account)) await commitIntent(key,intent);
  }
  function refreshPeer(){
    if(!journal || !uid) return;peerDirty=true;if(peerQueued) return;peerQueued=true;
    queue(async()=>{
      try{do{peerDirty=false;await recoverIntents(uid);const saved=await journal.read();state.pending=saved.pending.length;apply(saved.view);notify();void flush();}while(peerDirty);}
      finally{peerQueued=false;}
    }).catch(()=>{});
  }
  root.gijulCloudChanged=()=>{
    if(applying) return;
    const snapshot=root.gijulSyncSnapshot();
    if(!baseline){baseline=snapshot;return;}
    if(!uid) return;
    const before={},after={};
    for(const key of new Set([...Object.keys(baseline),...Object.keys(snapshot)])){
      if(JSON.stringify(baseline[key])===JSON.stringify(snapshot[key])) continue;
      if(baseline[key]!==undefined) before[key]=baseline[key];
      if(snapshot[key]!==undefined) after[key]=snapshot[key];
    }
    if(!Object.keys(before).length && !Object.keys(after).length) return;
    const intent={uid,id:crypto.randomUUID(),tab,serial:++serial,before,after},key=intentPrefix+intent.id;
    try{localStorage.setItem(key,JSON.stringify(intent));}catch(e){fail(new Error("변경을 전송 대기 목록에 저장하지 못했습니다. 파일로 백업해 주세요"));return;}
    baseline=snapshot;
    if(journal) queue(()=>commitIntent(key,intent)).catch(()=>{});
  };
  async function connect(user){
    disconnect();const session=connection,current=()=>session===connection;
    if(!user){state.on=false;state.busy=false;notify();return;}
    try{
      await queue(async()=>{
        if(!current()) return;
        if(!localStorage.getItem("gijul.sync.before.v1")) localStorage.setItem("gijul.sync.before.v1",JSON.stringify(root.gijulBackupSnapshot()));
        await journal.bind(user.uid);if(!current()) return;
        uid=user.uid;localStorage.setItem("gijul.sync.uid.v1",uid);
        await recoverIntents(uid);if(!current()) return;
        const saved=await journal.read();if(!current()) return;
        apply(saved.view);
        state.on=true;state.busy=false;state.pending=saved.pending.length;state.message="기록을 확인하고 있습니다";
      });
      if(!current()) return;
      if(root.GijulNative && GijulNative.setCloudSyncActive) GijulNative.setCloudSyncActive(true);
      notify();
      const account=uid,checkpoint=(await journal.read()).cursor;if(!current()) return;
      stop=backend.listen(uid,checkpoint,ops=>queue(async()=>{
        if(!current() || !state.on || uid!==account) return;
        const first=!ready,local=root.gijulSyncSnapshot();
        const received=await journal.receive(ops);if(!current()) return;
        let view=received.view;state.invalid=received.invalid;
        if(first){
          // Import existing device records once; cloud values and deletion markers take priority.
          const seeded=await journal.capture({},local,true);if(!current()) return;
          view=seeded.view;state.pending=seeded.pending.length;ready=true;
        }
        apply(view);wake();state.busy=false;state.message=state.invalid?"일부 변경을 읽지 못했습니다. 이전 이력은 서버에 보존합니다":state.pending?"기록을 전송하고 있습니다":"동기화했습니다";notify();void flush();
      }),e=>{if(current()){disconnect();fail(e);}});
    }catch(e){if(current()){
      disconnect();state.on=false;state.busy=true;const cleanup=connection,wasPending=authPending;authPending=true;
      try{await backend.logout();}finally{authPending=wasPending;if(cleanup===connection) fail(e);}
    }}
  }
  root.GijulSync={
    state:()=>({...state}),
    history:async()=>journal?journal.history():[],
    async restore(entry){
      if(!journal || !uid) throw new Error("기록 동기화를 먼저 연결해 주세요");
      return queue(async()=>{
        const found=(await journal.history()).find(h=>h.id===entry.id && h.slot===entry.slot && h.key===entry.key);
        if(!found) throw new Error("이 변경은 최근 이력에 남아 있지 않습니다");
        await recoverIntents(uid);
        const saved=await journal.read(),key=JSON.stringify([found.slot,found.key]);
        await journal.capture({[key]:saved.view[key]},{[key]:found.value});
        const next=await journal.read();apply(next.view);state.pending=next.pending.length;wake();notify();void flush();
      });
    },
    async init(){
      if(initialized) return;initialized=true;const epoch=authEpoch;
      try{
        try{
          const response=await fetch("./sync/config.json",{cache:"no-cache"});
          if(!response.ok) throw new Error("Configuration unavailable");
          config=await response.json();localStorage.setItem("gijul.sync.config.v1",JSON.stringify(config));
        }catch(e){config=JSON.parse(localStorage.getItem("gijul.sync.config.v1") || "null");}
        if(!config || !config.enabled || !config.firebase || !config.firebase.projectId) return;
        state.enabled=true;journal=await new GijulJournal.Journal().open();
        if(!baseline) baseline=root.gijulSyncSnapshot();
        await queue(async()=>{
          const saved=await journal.read();uid=saved.uid;
          if(uid){
            localStorage.setItem("gijul.sync.uid.v1",uid);await recoverIntents(uid);
            const current=await journal.read();state.pending=current.pending.length;apply(current.view);
          }
        });
        notify();backend=await GijulFirebase(config);const user=await backend.current();
        if(epoch===authEpoch) await connect(user);
        if(backend.watch) backend.watch(user=>{
          if(authPending || state.busy) return;
          if(user ? !state.on || user.uid!==uid : state.on){authEpoch++;void connect(user);}
        });
        timer=setInterval(()=>{root.gijulCloudChanged();refreshPeer();},30000);
      }catch(e){fail(e);}
    },
    async login(){
      if(authPending || state.busy || !journal) return;authPending=true;const epoch=++authEpoch;
      state.busy=true;state.message="로그인을 기다리고 있습니다";notify();
      try{
        if(!backend) backend=await GijulFirebase(config);
        const user=await backend.login();if(epoch===authEpoch) await connect(user);
      }catch(e){if(epoch===authEpoch) fail(e);}
      finally{authPending=false;}
    },
    async logout(){
      if(authPending || state.busy) return;authPending=true;authEpoch++;disconnect();state.busy=true;state.on=false;
      state.message="연결을 끊고 있습니다";notify();
      try{await backend.logout();state.message="연결을 끊었습니다. 이 기기의 기록은 보존합니다";}catch(e){fail(e);}
      finally{authPending=false;state.busy=false;notify();}
      // Keep the journal bound to its original account, including signed-out edits.
    },
    async retry(){
      if(authPending || state.busy) return;
      if(state.on && !ready){const epoch=authEpoch,user=await backend.current();if(epoch===authEpoch) await connect(user);}
      else {root.gijulCloudChanged();refreshPeer();}
    },
  };
  root.addEventListener("storage",e=>{if(e.key===wakeKey || e.key?.startsWith(intentPrefix)) refreshPeer();});
  root.addEventListener("online",()=>{root.gijulCloudChanged();refreshPeer();});
  root.addEventListener("pageshow",()=>{refreshPeer();if(timer) clearInterval(timer);timer=setInterval(()=>{root.gijulCloudChanged();refreshPeer();},30000);});
  root.addEventListener("pagehide",()=>{if(timer) clearInterval(timer);});
})(globalThis);
