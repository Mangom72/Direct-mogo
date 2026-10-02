/* Run with the Firebase Firestore emulator, never against a production project. */
const fs = require('node:fs');
const path = require('node:path');
const {initializeTestEnvironment, assertSucceeds, assertFails} = require('@firebase/rules-unit-testing');
const {doc, collection, setDoc, getDoc, getDocs, deleteDoc, updateDoc, serverTimestamp, Timestamp} = require('firebase/firestore');
(async()=>{
  const env=await initializeTestEnvironment({projectId:'demo-gijul-sync',firestore:{rules:fs.readFileSync(path.join(__dirname,'../sync/firestore.rules'),'utf8')}});
  try{
    const owner=env.authenticatedContext('owner').firestore(),other=env.authenticatedContext('other').firestore(),anon=env.unauthenticatedContext().firestore();
    const id='11111111-1111-4111-8111-111111111111',p=`users/owner/events/${id}`;
    const op={v:1,id,clock:1,receivedAt:serverTimestamp(),payload:JSON.stringify([{slot:'score',key:'D300/158/20260902/시험',value:42}])};
    await assertSucceeds(setDoc(doc(owner,p),op));
    const stored=(await getDoc(doc(owner,p))).data();
    await assertSucceeds(setDoc(doc(owner,p),stored));
    await assertSucceeds(getDoc(doc(owner,p)));
    await assertSucceeds(getDocs(collection(owner,'users/owner/events')));
    await assertFails(getDocs(collection(anon,'users/owner/events')));
    await assertFails(getDoc(doc(other,p)));
    await assertFails(setDoc(doc(other,p),op));
    await assertFails(deleteDoc(doc(owner,p)));
    await assertFails(updateDoc(doc(owner,p),{clock:2}));
    await assertFails(updateDoc(doc(owner,p),{payload:'x'.repeat(65537)}));
    await assertFails(updateDoc(doc(owner,p),{isAdmin:true}));
    await assertFails(setDoc(doc(owner,'users/owner'),{isAdmin:true}));
    const freshId='22222222-2222-4222-8222-222222222222',fresh=doc(owner,`users/owner/events/${freshId}`);
    for(const delta of [{receivedAt:Timestamp.fromMillis(1)},{clock:-1},{clock:9007199254740991},{clock:'1'},{payload:123},{payload:'x'.repeat(65537)},{id:'wrong'},{isAdmin:true},{v:2}]){
      await assertFails(setDoc(fresh,{...op,id:freshId,...delta}));
    }
    await assertFails(setDoc(fresh,{v:1,id:freshId,clock:1}));
    await assertFails(setDoc(doc(owner,'users/other/events/'+freshId),{...op,id:freshId}));
    console.log('Firestore rules: owner query/create/read, idempotent retry passed; unauthorized access, mutations, deletes, type/size/schema/role/path attacks denied');
  }finally{await env.cleanup();}
})().catch(e=>{console.error(e);process.exitCode=1;});
