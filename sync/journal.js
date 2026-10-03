/* Durable, account-bound change journal. Cloud confirmation alone removes outbox entries. */
(function(root){
  "use strict";
  const same = (a,b)=>JSON.stringify(a)===JSON.stringify(b);
  const newer = (a,b)=>!b || a.clock>b.clock || (a.clock===b.clock && a.id>b.id);
  const subjectId=f=>JSON.stringify([f.g,f.s]);
  const subjects=xs=>Array.isArray(xs) && xs.length<=256 && xs.every(f=>f&&typeof f.g==="string"&&typeof f.s==="string"&&f.g.length<=512&&f.s.length<=512);
  function valid(op){
    if(!op || op.v!==1 || !/^[a-f0-9-]{36}$/.test(op.id) || !Number.isSafeInteger(op.clock) || op.clock<1
       || typeof op.payload!=="string" || new TextEncoder().encode(op.payload).length>65536) throw new Error("Invalid sync event");
    const entries=JSON.parse(op.payload);
    if(!Array.isArray(entries) || !entries.length || entries.length>256) throw new Error("Invalid sync entries");
    for(const e of entries){
      if(!e || !["solved","time","score","wrong","favs","theme"].includes(e.slot)
         || typeof e.key!=="string" || e.key.length>512 || ["__proto__","constructor","prototype"].includes(e.key)) throw new Error("Invalid sync key");
      if(e.slot!=="favs" && e.slot!=="theme" && e.key.split("/").length<4) throw new Error("Invalid exam key");
      if(e.delta!==undefined && (e.slot!=="favs" || e.key!=="settings" || !e.delta || !subjects(e.delta.add) || !subjects(e.delta.remove) || !subjects(e.delta.order) || !subjects(e.value))) throw new Error("Invalid subject changes");
      if(e.value===null) continue;
      if(e.slot==="solved" && !/^\d{8}$/.test(e.value)) throw new Error("Invalid solved date");
      if(e.slot==="score" && (!Number.isInteger(e.value) || e.value<0 || e.value>100)) throw new Error("Invalid score");
      if(e.slot==="wrong" && (!Array.isArray(e.value) || e.value.length>999 || !e.value.every(n=>Number.isInteger(n)&&n>0&&n<=999))) throw new Error("Invalid wrong numbers");
      if(e.slot==="time" && (!e.value || !Number.isFinite(e.value.spent) || e.value.spent<=0 || !Number.isFinite(e.value.limit) || e.value.limit<0)) throw new Error("Invalid time");
      if(e.slot==="theme" && !["auto","light","dark"].includes(e.value)) throw new Error("Invalid theme");
      if(e.slot==="favs" && !subjects(e.value)) throw new Error("Invalid subjects");
    }
    return entries;
  }
  function foldSubjects(state,k,e,op){
    if(!state.subjects){
      const old=state.cells[k];state.subjects={members:{},reset:old || null,order:old?{...old,value:old.value || []}:null};
      for(const f of old?.value || []) state.subjects.members[subjectId(f)]={...old,value:f};
    }
    const s=state.subjects,stamp={clock:op.clock,id:op.id},put=(f,value)=>{
      const key=subjectId(f);
      if(newer(stamp,s.members[key])) s.members[key]={...stamp,value};
    };
    if(e.delta){
      if(newer(stamp,s.reset)){
        for(const f of e.delta.add) put(f,f);
        for(const f of e.delta.remove) put(f,null);
      }
      if(newer(stamp,s.order)) s.order={...stamp,value:e.delta.order};
    }else if(newer(stamp,s.reset)){
      // Old clients send complete lists. Their replacement is a stamped reset,
      // so an older add received later cannot resurrect a removed subject.
      s.reset=stamp;const included=new Map((e.value || []).map(f=>[subjectId(f),f]));
      for(const key of new Set([...Object.keys(s.members),...included.keys()])){
        const [g,subject]=JSON.parse(key);put({g,s:subject},included.get(key) || null);
      }
      if(newer(stamp,s.order)) s.order={...stamp,value:e.value || []};
    }
    const rank=new Map((s.order?.value || []).map((f,i)=>[subjectId(f),i]));
    const value=Object.entries(s.members).filter(([,m])=>m.value!==null).sort(([a],[b])=>(rank.get(a)??Infinity)-(rank.get(b)??Infinity) || (a<b?-1:a>b?1:0)).map(([,m])=>m.value);
    const old=state.cells[k];state.cells[k]={...(newer(op,old)?stamp:old),value};
  }
  function fold(state,op){
    const entries=valid(op); state.clock=Math.max(state.clock,op.clock);
    for(const e of entries){
      const k=JSON.stringify([e.slot,e.key]),old=state.cells[k];
      const history=state.history || (state.history=[]),remember=h=>{
        if(!history.some(v=>v.id===h.id && v.slot===h.slot && v.key===h.key)) history.push(h);
      };
      if(old) remember({clock:old.clock,id:old.id,slot:e.slot,key:e.key,value:old.value});
      if(e.slot==="favs" && e.key==="settings") foldSubjects(state,k,e,op);
      else if(newer(op,old)) state.cells[k]={clock:op.clock,id:op.id,value:e.value};
      remember({clock:op.clock,id:op.id,slot:e.slot,key:e.key,value:e.value});
    }
    state.history.sort((a,b)=>b.clock-a.clock || (a.id<b.id?1:a.id>b.id?-1:0));
    state.history=state.history.slice(0,200);
  }
  function cells(state){
    const out={};
    for(const [k,v] of Object.entries(state.cells)) out[k]=v.value;
    return out;
  }
  class Journal{
    constructor(name="gijul-sync-v1"){ this.name=name; }
    async open(){
      this.db=await new Promise((resolve,reject)=>{
        const r=indexedDB.open(this.name,1);
        r.onupgradeneeded=()=>r.result.createObjectStore("state");
        r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error);
      });return this;
    }
    change(fn){
      return new Promise((resolve,reject)=>{
        const tx=this.db.transaction("state","readwrite"),store=tx.objectStore("state"),r=store.get("journal");let result;
        r.onsuccess=()=>{try{
          const state=r.result || {uid:null,clock:0,cells:{},pending:{}};
          result=fn(state);store.put(state,"journal");
        }catch(e){ reject(e);tx.abort(); }};
        tx.oncomplete=()=>resolve(result);tx.onerror=()=>reject(tx.error);tx.onabort=()=>reject(tx.error || new Error("Journal transaction aborted"));
      });
    }
    bind(uid){return this.change(s=>{if(s.uid && s.uid!==uid) throw new Error("ACCOUNT_MISMATCH");s.uid=uid;return {view:cells(s),pending:Object.keys(s.pending).length};});}
    read(){return this.change(s=>({uid:s.uid,view:cells(s),pending:Object.values(s.pending),cursor:s.cursor || null}));}
    history(){return this.change(s=>s.history || []);}
    capture(before,after,seed=false,intentId=null,isLive=()=>true){return this.change(s=>{
      // Check inside the serialized transaction: another tab may have consumed
      // this intent and released its receipt while this transaction was waiting.
      if(!isLive() || (intentId && s.receipts && s.receipts[intentId])) return {view:cells(s),pending:Object.values(s.pending)};
      if(!s.uid) throw new Error("No sync account");
      const changes=[];
      for(const k of new Set([...Object.keys(before),...Object.keys(after)])){
        if(same(before[k],after[k])) continue;
        if(seed && k in s.cells) continue; // Tombstones also block old-file resurrection.
        const [slot,key]=JSON.parse(k),entry={slot,key,value:after[k]===undefined?null:after[k]};
        if(!seed && slot==="favs" && key==="settings" && Array.isArray(after[k])){
          const prev=new Map((before[k] || []).map(f=>[subjectId(f),f])),next=new Map(after[k].map(f=>[subjectId(f),f]));
          entry.delta={add:[...next].filter(([id])=>!prev.has(id)).map(([,f])=>f),remove:[...prev].filter(([id])=>!next.has(id)).map(([,f])=>f),order:after[k]};
        }
        changes.push(entry);
      }
      while(changes.length){
        const chunk=[];let bytes=2;
        while(changes.length && chunk.length<256){
          const size=new TextEncoder().encode(JSON.stringify(changes[0])).length+1;
          if(bytes+size>65536) break;
          chunk.push(changes.shift());bytes+=size;
        }
        if(!chunk.length) throw new Error("Sync entry is too large");
        const op={v:1,id:crypto.randomUUID(),clock:++s.clock,payload:JSON.stringify(chunk)};
        fold(s,op);s.pending[op.id]=op;
      }
      if(intentId) (s.receipts || (s.receipts={}))[intentId]=true;
      return {view:cells(s),pending:Object.values(s.pending)};
    });}
    releaseReceipt(id){return this.change(s=>{if(s.receipts) delete s.receipts[id];});}
    receive(ops){return this.change(s=>{
      for(const op of ops){
        try{fold(s,op);}catch(e){
          (s.quarantine || (s.quarantine={}))[typeof op?.id==="string"?op.id.slice(0,64):"invalid"]="invalid event";
        }
        const at=op?.receivedAt;
        if(at && Number.isSafeInteger(at.seconds) && at.seconds>0 && Number.isInteger(at.nanoseconds) && at.nanoseconds>=0 && at.nanoseconds<1e9){
          if(!s.cursor || at.seconds>s.cursor.seconds || (at.seconds===s.cursor.seconds && at.nanoseconds>s.cursor.nanoseconds)) s.cursor={seconds:at.seconds,nanoseconds:at.nanoseconds};
        }
      }
      return {view:cells(s),invalid:Object.keys(s.quarantine || {}).length};
    });}
    ack(id){return this.ackMany([id]);}
    ackMany(ids){return this.change(s=>{for(const id of ids) delete s.pending[id];return Object.keys(s.pending).length;});}
  }
  root.GijulJournal={Journal,valid,fold,cells};
})(globalThis);
