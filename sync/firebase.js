/* Pinned SDK files load only after Firebase is configured and synchronization is opened. */
(function(root){
  "use strict";
  let loaded;
  function script(src){return new Promise((resolve,reject)=>{
    const el=document.createElement("script");el.src=src;el.onload=resolve;el.onerror=()=>{el.remove();reject(new Error("동기화 연결을 불러오지 못했습니다"));};document.head.append(el);
  });}
  root.GijulFirebase=async function(config){
    if(!loaded) loaded=(async()=>{
      for(const name of ["app","auth","firestore"]) await script("./sync/vendor/firebase-"+name+"-compat.js");
    })().catch(e=>{loaded=null;throw e;});
    await loaded;
    const app=firebase.apps.length?firebase.app():firebase.initializeApp(config.firebase);
    const auth=app.auth(),db=app.firestore();
    await auth.setPersistence(firebase.auth.Auth.Persistence.LOCAL);
    // Outbox lives in our atomic IndexedDB journal; SDK cache is not an acknowledgement.
    const authenticate=async()=>{
      if(root.GijulNative){
        if(!GijulNative.googleSignIn) throw new Error("앱을 업데이트한 뒤 다시 로그인해 주세요");
        const token=await new Promise((resolve,reject)=>{
          const requestId=crypto.randomUUID();
          let timeout=setTimeout(()=>{if(GijulNative.cancelGoogleSignIn) GijulNative.cancelGoogleSignIn(requestId);root.gijulGoogleSignIn=null;reject(new Error("로그인 시간이 지났습니다. 다시 시도해 주세요"));},120000);
          root.gijulGoogleSignIn=(id,ok,value)=>{if(id!==requestId) return;clearTimeout(timeout);root.gijulGoogleSignIn=null;ok?resolve(value):reject(new Error(value));};
          try{GijulNative.googleSignIn(config.googleWebClientId,requestId);}catch(e){clearTimeout(timeout);root.gijulGoogleSignIn=null;reject(e);}
        });
        return (await auth.signInWithCredential(firebase.auth.GoogleAuthProvider.credential(token))).user;
      }
      return (await auth.signInWithPopup(new firebase.auth.GoogleAuthProvider())).user;
    };
    return {
      current:()=>new Promise(resolve=>{const stop=auth.onAuthStateChanged(user=>{stop();resolve(user);});}),
      watch:callback=>auth.onAuthStateChanged(callback),
      login:authenticate,
      logout:async()=>{await auth.signOut();if(root.GijulNative&&GijulNative.clearGoogleSignIn) GijulNative.clearGoogleSignIn();},
      listen(uid,cursor,onData,onError){
        let query=db.collection("users").doc(uid).collection("events").orderBy("receivedAt");
        if(cursor) query=query.where("receivedAt",">=",new firebase.firestore.Timestamp(cursor.seconds,cursor.nanoseconds));
        const seen=new Set();let delivery=Promise.resolve();
        return query.onSnapshot({includeMetadataChanges:true},snap=>{
          if(snap.metadata.fromCache || snap.metadata.hasPendingWrites) return;
          const docs=snap.docs;
          delivery=delivery.then(async()=>{
            const fresh=docs.filter(d=>!seen.has(d.id));
            await onData(fresh.map(d=>d.data()));
            for(const d of fresh) seen.add(d.id);
          }).catch(onError);
        },onError);
      },
      async send(uid,op){return this.sendBatch(uid,[op]);},
      async sendBatch(uid,ops){
        const events=db.collection("users").doc(uid).collection("events");
        await db.runTransaction(async tx=>{
          const rows=[];
          for(const op of ops) rows.push({op,ref:events.doc(op.id),existing:await tx.get(events.doc(op.id))});
          for(const {op,ref,existing} of rows){
            if(existing.exists){
              const old=existing.data();
              if(old.v!==op.v || old.id!==op.id || old.clock!==op.clock || old.payload!==op.payload) throw new Error("저장된 변경 이력이 일치하지 않습니다");
            }else tx.set(ref,{...op,receivedAt:firebase.firestore.FieldValue.serverTimestamp()});
          }
        });
      },
    };
  };
})(globalThis);
