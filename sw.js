/* 기출 직행 서비스 워커
   자료 3,800여 건이 index.html 안에 들어 있으므로, 이 파일 하나만 쥐고 있으면
   조회·필터는 네트워크 없이 전부 동작한다. 네트워크가 필요한 것은 PDF뿐이다. */
const VERSION = "v1";
const SHELL = `gijul-shell-${VERSION}`;
const FILES = `gijul-files-${VERSION}`;
const KEEP = [SHELL, FILES];

const SHELL_URLS = [
  "./", "./index.html", "./manifest.webmanifest",
  "./icons/icon-192.png", "./icons/icon-512.png",
  "./icons/icon-maskable-192.png", "./icons/icon-maskable-512.png",
  "./icons/apple-touch-icon.png", "./icons/favicon.ico", "./icons/favicon-32.png",
  /* 글꼴도 우리 것이 됐으므로 셸과 함께 미리 받아 둔다 — 첫 방문부터 오프라인에서
     제 글꼴로 뜨고, 예전처럼 남의 서버가 대답할 때까지 기다릴 일이 없다. */
  "./fonts/fonts.css",
  "./fonts/SongMyung-400.woff2",
  "./fonts/GijulSans-400.woff2", "./fonts/GijulSans-500.woff2",
  "./fonts/GijulSans-600.woff2", "./fonts/GijulSans-700.woff2",
];

/* "./"는 빼둔다 — slice로 만든 빈 문자열은 endsWith가 항상 참이라 전부 셸로 빨려든다 */
const SHELL_PATHS = SHELL_URLS.filter(u => u !== "./").map(u => u.slice(1));

const MAX_FILES = 40;   /* 받아둔 PDF·이미지 보관 개수 */

const isPaper = u => u.hostname === "wdown.ebsi.co.kr";

self.addEventListener("install", e=>{
  /* 아이콘 하나가 없다고 설치 전체가 실패하면 안 된다 */
  e.waitUntil(caches.open(SHELL)
    .then(c => Promise.all(SHELL_URLS.map(u => c.add(u).catch(()=>{}))))
    .then(()=>self.skipWaiting()));
});

/* 교체된 옛 워커가 남은 요청을 처리하며 방금 지운 통을 되살릴 수 있으므로,
   activate 한 번으로 끝내지 않고 페이지가 뜰 때마다 한 번 더 쓸어낸다. */
async function sweep(){
  const names = await caches.keys();
  await Promise.all(names.filter(n=>n.startsWith("gijul-") && !KEEP.includes(n))
                         .map(n=>caches.delete(n)));
}

self.addEventListener("activate", e=>{
  e.waitUntil(sweep().then(()=>self.clients.claim()));
});

/* 오래된 자료부터 버린다. Cache Storage는 넣은 순서를 유지하므로 앞에서부터 지우면 된다. */
async function trim(cache){
  const keys = await cache.keys();
  for(let i = 0; i < keys.length - MAX_FILES; i++) await cache.delete(keys[i]);
}

/* 셸: 캐시에서 즉시. 갱신 확인은 아래 check()가 따로 맡는다 —
   여기서 같이 하면 페이지가 메시지 리스너를 붙이기도 전에 알림이 날아가 버린다. */
async function shell(req){
  const hit = await caches.match(req, { cacheName:SHELL, ignoreSearch:true });
  if(hit) return hit;
  const res = await fetch(req).catch(()=>null);
  if(res && res.ok) (await caches.open(SHELL)).put(req, res.clone());
  return res || Response.error();
}

/* 페이지가 뜬 뒤 명시적으로 물어볼 때만 돈다. 내용이 달라졌으면 캐시를 갈아끼우고 참을 준다.

   reload가 아니라 no-cache다. 둘 다 서버에 물어보지만 reload는 HTTP 캐시를 통째로
   무시하고 무조건 받아 온다 — 바뀐 것이 없어도 실행할 때마다 index.html 190KB를
   다시 내려받고 있었다. no-cache는 조건부로 물어서, 그대로면 서버가 304만 돌려주고
   본문은 이미 있는 것을 쓴다. 바뀌었으면 그때만 200으로 새 본문이 온다.
   아래 비교는 그대로 성립한다 — 어느 쪽이든 res는 지금 서버에 있는 내용이다. */
async function check(){
  const cache = await caches.open(SHELL);
  const url = new URL("./index.html", self.location).href;
  const res = await fetch(url, { cache:"no-cache" }).catch(()=>null);
  if(!res || !res.ok) return false;
  const old = await cache.match(url, { ignoreSearch:true })
           || await cache.match(new URL("./", self.location).href, { ignoreSearch:true });
  const before = old ? await old.text() : null;
  const after = await res.clone().text();
  await cache.put(url, res.clone());
  await cache.put(new URL("./", self.location).href, res.clone());
  return before !== null && before !== after;
}

/* 폰트·자료: 한 번 받아두면 계속 캐시에서.
   caches.open을 미리 부르지 않는 게 중요하다 — 실패한 요청까지 빈 캐시 통을 만들어 두면,
   교체된 옛 워커의 지연된 요청이 방금 지운 통을 되살린다. */
async function cacheFirst(req, name, after){
  const hit = await caches.match(req, { cacheName:name });
  if(hit) return hit;
  const res = await fetch(req);
  if(res && (res.ok || res.type === "opaque")){
    const cache = await caches.open(name);
    await cache.put(req, res.clone());
    if(after) await after(cache);
  }
  return res;
}

self.addEventListener("fetch", e=>{
  const req = e.request;
  if(req.method !== "GET") return;
  let url;
  try{ url = new URL(req.url); }catch(err){ return; }

  if(req.mode === "navigate"){ e.respondWith(shell(req)); return; }
  if(isPaper(url)){ e.respondWith(cacheFirst(req, FILES, trim)); return; }
  if(url.origin === self.location.origin && SHELL_PATHS.some(p=>url.pathname.endsWith(p))){
    e.respondWith(shell(req));
  }
});

self.addEventListener("message", e=>{
  if(e.data !== "check" || !e.source) return;
  /* 달라진 게 없다는 답도 돌려준다. 페이지가 손으로 확인할 때 앱 쪽 답과 모아서
     한 번에 말하느라 양쪽을 다 기다리는데, 여기서 입을 다물면 그 기다림이 끝나지
     않는다. 저절로 도는 확인에서는 페이지가 이 답을 그냥 흘려보낸다. */
  e.waitUntil(Promise.all([
    sweep(),
    check().then(changed=> e.source.postMessage({ type: changed ? "updated" : "current" }))
  ]));
});
