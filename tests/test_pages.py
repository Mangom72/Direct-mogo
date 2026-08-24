"""과목 정적 페이지 — 스크립트 없이 읽히는가, 링크가 살아 있는가."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from harness import CHROME, ROOT, SHOT, site, Serve
_srv, SITE = site()
import asyncio, re, pathlib
from playwright.async_api import async_playwright
CH = CHROME
# 통 이름에 붙는 판. sw.js 에서 읽는다 — 여기에 적어 두면 판을 올릴 때마다 깨진다.
V = re.search(r'VERSION = "(v\d+)"', (ROOT / "sw.js").read_text(encoding="utf-8")).group(1)
B = SITE.rstrip("/")
D=str(SHOT)
async def main():
    err=[]
    async with async_playwright() as p:
        b=await p.chromium.launch(executable_path=CH)
        c=await b.new_context(viewport={"width":412,"height":1000},device_scale_factor=2)
        pg=await c.new_page()
        pg.on("console", lambda m: m.type=="error" and err.append(m.text))
        pg.on("pageerror", lambda e: err.append(str(e)))

        for path in ["/s/", "/s/D300/158.html"]:
            r=await pg.goto(B+path, wait_until="load")
            print(f"== {path}  HTTP {r.status}")
            print("   제목:", await pg.title())
            print("   설명:", (await pg.get_attribute('meta[name=description]','content'))[:70])
            print("   canonical:", await pg.get_attribute('link[rel=canonical]','href'))
            print("   h1:", await pg.inner_text("h1"))
            fonts=await pg.evaluate("()=>[document.fonts.check('700 19px \"Song Myung\"'),"
                                    "document.fonts.check('14px \"Gijul Sans\"')]")
            print("   글꼴 실림(명조/고딕):", fonts)
            await pg.screenshot(path=f"{D}/pg_{path.strip('/').replace('/','_') or 'idx'}.png",
                                full_page=(path=='/s/'))

        # 과목 페이지 내용 점검
        await pg.goto(B+"/s/D300/158.html", wait_until="load")
        rows=await pg.eval_on_selector_all("tbody tr","e=>e.length")
        links=await pg.eval_on_selector_all(".dl a","e=>e.map(x=>x.href)")
        bad=[u for u in links if not u.startswith("https://wdown.ebsi.co.kr/")]
        print(f"   회차 행 {rows}개 · 자료 링크 {len(links)}개 · 엉뚱한 링크 {len(bad)}")
        # 서로 오가는 길
        for sel,label in [('.pg .go a.app','앱 화면'),('.crumb a','빵부스러기'),
                          ('.also .chips a','옆 과목'),('footer .ln a','바닥')]:
            hrefs=await pg.eval_on_selector_all(sel,"e=>e.map(x=>x.getAttribute('href'))")
            print(f"   {label}: {hrefs[:3]}{' …' if len(hrefs)>3 else ''}")

        # 내부 링크가 실제로 열리는가 (표본)
        import json as J
        idx=J.loads((ROOT / "data/index.json").read_text(encoding="utf-8"))
        n_ok=0; n=0
        for gr in idx["grades"]:
            for g in gr["groups"]:
                for s in g["subjects"]:
                    n+=1
                    r=await pg.request.head(f"{B}/s/{gr['code']}/{s['id']}.html")
                    if r.status==200: n_ok+=1
        print(f"   색인이 가리키는 과목 페이지 {n_ok}/{n} 열림")
        r=await pg.request.get(B+"/sitemap.xml")
        print("   sitemap.xml:", r.status, r.headers.get("content-type"),
              len(re.findall(r"<url>", await r.text())), "개 주소")
        r=await pg.request.get(B+"/robots.txt")
        print("   robots.txt:", r.status)
        print("ERRORS:", err or "없음")
        await b.close()
asyncio.run(main())

# ── 서비스 워커가 과목 페이지를 앱 화면으로 바꿔치지 않는가 ─────────────
async def sw_check():
    async with async_playwright() as p:
        b=await p.chromium.launch(executable_path=CH)
        c=await b.new_context(viewport={"width":412,"height":900})
        pg=await c.new_page()
        await pg.goto(B+"/", wait_until="load")
        await pg.wait_for_function("() => navigator.serviceWorker.controller !== null",
                                   timeout=15000)
        print("== 서비스 워커 등록됨")
        for path,want in [("/s/","과목별 기출문제"),("/s/D300/158.html","생명과학Ⅰ 기출문제"),
                          ("/","기출 직행")]:
            await pg.goto(B+path, wait_until="load")
            h1=await pg.inner_text("h1")
            ok = want in h1
            print(f"   {path:22} h1='{h1}'  기대대로: {ok}")
        # 셸이 s/ 를 캐시에 끌어들이지 않았는가
        keys=await pg.evaluate("""async()=>{const c=await caches.open('gijul-shell-%s');
            return (await c.keys()).map(r=>new URL(r.url).pathname).filter(u=>u.includes('/s/'));}""" % V)
        print("   셸 캐시에 섞여 든 과목 페이지:", keys or "없음")
        await b.close()
asyncio.run(sw_check())
