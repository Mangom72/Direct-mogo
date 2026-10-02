(function(root){
  "use strict";
  let authEpoch=0,initialized=false,config=null,journal=null,backend=null,uid=null,stop=null,applying=false,ready=false,baseline=null,work=Promise.resolve(),sending=false,timer=null;
  const intentPrefix="gijul.sync.intent.v1:",tab=crypto.randomUUID();let serial=0;
  try{uid=localStorage.getItem("gijul.sync.uid.v1");}catch(e){}
  let state={enabled:false,on:false,busy:false,pending:0,invalid:0,message:""};
  const notify=()=>root.dispatchEvent(new Event("gijul-sync-state"));
  const fail=e=>{state.message=e.message==="ACCOUNT_MISMATCH"?"이 기기에 연결했던 Google 계정으로 로그인해 주세요":(/[가-힣]/.test(e.message || "") ? e.message : "동기화 연결을 확인하지 못했습니다. 기록은 이 기기에 남아 있습니다");state.busy=false;notify();};
  function queue(fn){const next=work.then(fn);work=next.catch(fail);return next;}
  async function apply(view){
    applying=true;
    try{root.gijulApplySync(view);}finally{baseline=root.gijulSyncSnapshot();applying=false;}
  }
  async function flush(){
    if(sending || !backend || !uid || !ready) return;
    sending=true;
    try{
      const batch=(await journal.read()).pending;state.pending=batch.length;notify();
      for(let i=0;i<batch.length;i+=50){
        const account=uid,chunk=batch.slice(i,i+50);
        if(backend.sendBatch) await backend.sendBatch(account,chunk);
        else for(const op of chunk) await backend.send(account,op);
        state.pending=await journal.ackMany(chunk.map(op=>op.id));
        if(uid!==account) return;
        notify();
      }
      state.message=state.invalid?"일부 변경을 읽지 못했습니다. 이전 이력은 서버에 보존합니다":state.pending?"전송할 기록이 남아 있습니다":"동기화했습니다";
    }catch(e){state.message="전송을 기다리는 중입니다. 기록은 이 기기에 남아 있습니다";}
    finally{sending=false;notify();}
  }
  async function commitIntent(key,intent){
    const result=await journal.capture(intent.before,intent.after,false,intent.id);
    localStorage.removeItem(key);
    await journal.releaseReceipt(intent.id);
    state.pending=result.pending.length;notify();void flush();
  }
  async function recoverIntents(account){
    const intents=[];
    for(let i=0;i<localStorage.length;i++){
      const key=localStorage.key(i);if(!key.startsWith(intentPrefix)) continue;
      const intent=JSON.parse(localStorage.getItem(key));
      if(intent.uid===account) intents.push({key,intent});
    }
    intents.sort((a,b)=>a.intent.tab.localeCompare(b.intent.tab)||a.intent.serial-b.intent.serial);
    for(const {key,intent} of intents) await commitIntent(key,intent);
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
    if(stop) stop();ready=false;
    if(!user){state.on=false;state.busy=false;notify();return;}
    try{
      await queue(async()=>{
        if(!localStorage.getItem("gijul.sync.before.v1")) localStorage.setItem("gijul.sync.before.v1",JSON.stringify(root.gijulBackupSnapshot()));
        await journal.bind(user.uid);uid=user.uid;localStorage.setItem("gijul.sync.uid.v1",uid);
        await recoverIntents(uid);
        const saved=await journal.read(),initial=root.gijulSyncSnapshot();
        await apply({...initial,...saved.view});
        state.on=true;state.busy=false;state.pending=saved.pending.length;state.message="기록을 확인하고 있습니다";
      });
      if(root.GijulNative && GijulNative.setCloudSyncActive) GijulNative.setCloudSyncActive(true);
      notify();
      const account=uid;
      const checkpoint=(await journal.read()).cursor;
      stop=backend.listen(uid,checkpoint,ops=>queue(async()=>{
        if(!state.on || uid!==account) return;
        const first=!ready,local=root.gijulSyncSnapshot();
        const received=await journal.receive(ops);let view=received.view;state.invalid=received.invalid;
        if(first){
          // Import existing device records once; cloud values and deletion markers take priority.
          const seeded=await journal.capture({},local,true);view=seeded.view;
          state.pending=seeded.pending.length;ready=true;
        }
        await apply(view);state.busy=false;state.message=state.invalid?"일부 변경을 읽지 못했습니다. 이전 이력은 서버에 보존합니다":state.pending?"기록을 전송하고 있습니다":"동기화했습니다";notify();void flush();
      }),e=>{ready=false;fail(e);});
    }catch(e){await backend.logout();state.on=false;fail(e);}
  }
  root.GijulSync={
    state:()=>({...state}),
    async init(){
      if(initialized) return;initialized=true;const epoch=authEpoch;
      try{
        try{
          const response=await fetch("./sync/config.json",{cache:"no-cache"});
          if(!response.ok) throw new Error("Configuration unavailable");
          config=await response.json();localStorage.setItem("gijul.sync.config.v1",JSON.stringify(config));
        }catch(e){config=JSON.parse(localStorage.getItem("gijul.sync.config.v1") || "null");}
        if(!config) return;
        if(!config.enabled || !config.firebase || !config.firebase.projectId) return;
        state.enabled=true;journal=await new GijulJournal.Journal().open();
        if(!baseline) baseline=root.gijulSyncSnapshot();
        await queue(async()=>{
          const saved=await journal.read();uid=saved.uid;
          if(uid){
            localStorage.setItem("gijul.sync.uid.v1",uid);await recoverIntents(uid);
            const current=await journal.read();state.pending=current.pending.length;
            await apply({...root.gijulSyncSnapshot(),...current.view});
          }
        });
        notify();backend=await GijulFirebase(config);const user=await backend.current();
        if(epoch===authEpoch) await connect(user);
        timer=setInterval(()=>{root.gijulCloudChanged();void flush();},30000);
      }catch(e){fail(e);}
    },
    async login(){
      if(state.busy) return;authEpoch++;state.busy=true;state.message="로그인을 기다리고 있습니다";notify();
      try{
        if(!backend) backend=await GijulFirebase(config);
        await connect(await backend.login());
      }catch(e){fail(e);}
    },
    async logout(){
      if(state.busy) return;authEpoch++;
      if(stop){stop();stop=null;}ready=false;
      try{await backend.logout();state.on=false;state.message="연결을 끊었습니다. 이 기기의 기록은 보존합니다";notify();}catch(e){fail(e);}
      // Keep the journal bound to its original account, including edits made while signed out.
    },
    async retry(){
      if(state.on && !ready){const epoch=authEpoch,user=await backend.current();if(epoch===authEpoch) await connect(user);}
      else {root.gijulCloudChanged();void flush();}
    },
  };
  root.addEventListener("online",()=>{root.gijulCloudChanged();void flush();});
  root.addEventListener("pageshow",()=>{if(timer) clearInterval(timer);timer=setInterval(()=>{root.gijulCloudChanged();void flush();},30000);});
  root.addEventListener("pagehide",()=>{if(timer) clearInterval(timer);});
})(globalThis);
