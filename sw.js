/* 기출 직행 서비스 워커
   자료 5천여 건이 index.html 안에 들어 있으므로, 이 파일 하나만 쥐고 있으면
   조회·필터는 네트워크 없이 전부 동작한다. 네트워크가 필요한 것은 PDF뿐이다. */
const VERSION = "v4";
const SHELL = `gijul-shell-${VERSION}`;
const FILES = `gijul-files-${VERSION}`;
const KEEP = [SHELL, FILES];

/* 보관함 — 사용자가 손으로 담은 회차. 통 이름이 `gijul-vault:회차` 라 통 목록만
   봐도 무엇이 담겼는지 알 수 있다.

   이것만은 판이 올라도 쓸어내지 않는다. 셸과 최근 파일은 언제든 다시 받으면
   그만이지만 이건 사용자가 '오프라인에서 볼 것'이라고 골라 둔 것이라, 판올림
   한 번에 지하철에서 볼 문제지가 사라지면 안 된다. */
const VAULT = "gijul-vault:";

/* 아래 파일은 하나라도 빠지면 앱의 첫 화면이나 글꼴이 반쪽짜리가 된다. 설치를
   성공으로 표시하지 말고 다음 접속에서 다시 시도한다. 아이콘은 없어도 앱 자체는
   쓸 수 있으므로 따로 받아, 한 변형의 실패가 전체 설치를 막지는 않게 한다. */
const REQUIRED_SHELL_URLS = [
  "./", "./index.html", "./manifest.webmanifest",
  /* 글꼴도 우리 것이 됐으므로 셸과 함께 미리 받아 둔다 — 첫 방문부터 오프라인에서
     제 글꼴로 뜨고, 예전처럼 남의 서버가 대답할 때까지 기다릴 일이 없다. */
  "./fonts/fonts.css",
  "./fonts/SongMyung-400.woff2",
  "./fonts/GijulSans-400.woff2", "./fonts/GijulSans-500.woff2",
  "./fonts/GijulSans-600.woff2", "./fonts/GijulSans-700.woff2",
];
const OPTIONAL_SHELL_URLS = [
  "./icons/icon-192.png", "./icons/icon-512.png",
  "./icons/icon-maskable-192.png", "./icons/icon-maskable-512.png",
  "./icons/apple-touch-icon.png", "./icons/favicon.ico", "./icons/favicon-32.png",
  "./icons/favicon-192.png",
];
const SHELL_URLS = [...REQUIRED_SHELL_URLS, ...OPTIONAL_SHELL_URLS];

/* 주소를 통째로 풀어 두고 정확히 맞는 것만 셸에서 낸다.
   전에는 경로 끝만 비교했는데, 과목 페이지 s/index.html 이 './index.html' 로 끝나는
   바람에 앱 화면이 대신 나갈 뻔했다. 끝자리 비교는 이런 식으로 조용히 어긋난다. */
const SHELL_SET = new Set(SHELL_URLS.map(u => new URL(u, self.location).href));
const ROOT = new URL("./", self.location).href;
const HOME = new URL("./index.html", self.location).href;

const MAX_FILES = 40;   /* 받아둔 PDF·이미지 보관 개수 */

const isPaper = u => u.hostname === "wdown.ebsi.co.kr";

self.addEventListener("install", e=>{
  e.waitUntil(caches.open(SHELL).then(async c => {
    await c.addAll(REQUIRED_SHELL_URLS);
    await Promise.all(OPTIONAL_SHELL_URLS.map(u => c.add(u).catch(()=>{})));
  }).then(()=>self.skipWaiting()));
});

/* 교체된 옛 워커가 남은 요청을 처리하며 방금 지운 통을 되살릴 수 있으므로,
   activate 한 번으로 끝내지 않고 페이지가 뜰 때마다 한 번 더 쓸어낸다. */
async function sweep(){
  const names = await caches.keys();
  await Promise.all(names.filter(n=>n.startsWith("gijul-")
                                 && !n.startsWith(VAULT) && !KEEP.includes(n))
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

/* 글꼴은 자라는 파일이다 — 페이지에 새 글자가 늘면 tools/build_fonts.py 가
   부분집합을 다시 만들어 같은 이름으로 내보낸다. 셸은 캐시 우선이라 한 번 받아
   두면 다시 묻지 않으므로, 그대로 두면 기기에 처음 깔릴 때의 글꼴이 영영 남는다.
   그 뒤에 늘어난 글자는 전부 시스템 글꼴로 떨어져, 한 제목 안에서 글꼴이 갈린다
   ('푼 날'의 '날'이 그랬다).

   그래서 갱신을 물어보는 김에 글꼴도 함께 조건부로 확인한다. 바뀐 것이 없으면
   서버가 304만 돌려주므로 값이 거의 들지 않는다. */
const FONT_URLS = SHELL_URLS.filter(u => u.indexOf("/fonts/") >= 0);

async function freshenFonts(){
  const cache = await caches.open(SHELL);
  await Promise.all(FONT_URLS.map(async u => {
    try{
      const res = await fetch(new URL(u, self.location).href, { cache:"no-cache" });
      if(res && res.ok) await cache.put(new URL(u, self.location).href, res);
    }catch(e){}
  }));
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

/* 문제지: 보관함에 있으면 그것부터. cacheName 없이 부르면 통 전부를 뒤지므로
   보관함이든 최근 것이든 한 번에 잡힌다. 없을 때만 받아서 '최근' 통에 넣는다 —
   보관함은 사용자가 담을 때만 늘어난다. */
async function paper(req){
  const kept = await caches.match(req);
  if(kept) return kept;
  return cacheFirst(req, FILES, trim);
}

self.addEventListener("fetch", e=>{
  const req = e.request;
  if(req.method !== "GET") return;
  let url;
  try{ url = new URL(req.url); }catch(err){ return; }

  /* 셸이 대신 나갈 수 있는 문서는 앱 화면 하나뿐이다. 과목 페이지(s/…)는 검색이나
     링크로 들어오는 별개의 문서라, 여기서 가로채면 주소는 그대로인데 내용만 앱으로
     바뀐다. 우리 것이 아닌 문서는 손대지 않고 브라우저에 맡긴다. */
  if(req.mode === "navigate"){
    const at = url.origin + url.pathname;
    if(at === ROOT || at === HOME) e.respondWith(shell(req));
    return;
  }
  if(isPaper(url)){ e.respondWith(paper(req)); return; }
  if(SHELL_SET.has(url.origin + url.pathname)) e.respondWith(shell(req));
});

self.addEventListener("message", e=>{
  if(e.data !== "check" || !e.source) return;
  /* 달라진 게 없다는 답도 돌려준다. 페이지가 손으로 확인할 때 앱 쪽 답과 모아서
     한 번에 말하느라 양쪽을 다 기다리는데, 여기서 입을 다물면 그 기다림이 끝나지
     않는다. 저절로 도는 확인에서는 페이지가 이 답을 그냥 흘려보낸다. */
  e.waitUntil(Promise.all([
    sweep(),
    check().then(changed=>{
      e.source.postMessage({ type: changed ? "updated" : "current" });
      /* 문서가 바뀌었으면 글자도 늘었을 수 있다. 알림을 먼저 보내고 이어서
         받는다 — 페이지는 기다릴 것이 없고, waitUntil 안이라 다 받기 전에
         워커가 잠들지도 않는다. 이번 화면은 이미 그려졌으므로 새 글꼴은
         다음에 열 때 쓰인다. */
      if(changed) return freshenFonts();
    })
  ]));
});
