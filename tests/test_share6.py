"""내 과목 공유 링크 — 여섯 개를 담아 보내고 그대로 받는가."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from harness import CHROME, ROOT, SHOT, site, Serve
_srv, SITE = site()
import asyncio, json
from playwright.async_api import async_playwright
CH = CHROME
FAVS=[{"g":"D300","s":"140117"},{"g":"D300","s":"140119"},{"g":"D300","s":"80003"},
      {"g":"D300","s":"63004"},{"g":"D300","s":"66001"},{"g":"D300","s":"158"}]
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(executable_path=CH)
        c=await b.new_context(viewport={"width":412,"height":900},
             permissions=["clipboard-read","clipboard-write"])
        pg=await c.new_page()
        pg.on("console", lambda m: m.type=="error" and print("  console:",m.text))
        await pg.goto(SITE, wait_until="load")
        await pg.evaluate("f=>localStorage.setItem('gijul.mysubs.v1', JSON.stringify(f))",
                          FAVS)
        await pg.reload(wait_until="load"); await pg.wait_for_timeout(1200)
        pills = await pg.eval_on_selector_all(".favs button", "e=>e.map(x=>x.textContent)")
        print("알약:", pills)
        # navigator.share 없음 -> 클립보드 경로
        await pg.evaluate("()=>{ try{ delete navigator.share; }catch(e){} }")
        await pg.click("#favShare")
        await pg.wait_for_timeout(500)
        txt = await pg.evaluate("()=>navigator.clipboard.readText()")
        print("복사된 주소:", txt)
        print("토큰 수:", len(txt.split("subs=")[1].split(",")) if "subs=" in txt else 0)
        note = await pg.inner_text("#notice") if await pg.locator("#notice").count() else ""
        print("안내:", note.replace("\n"," ")[:90])
        # 받는 쪽
        pg2 = await (await b.new_context(viewport={"width":412,"height":900})).new_page()
        await pg2.goto(txt, wait_until="load"); await pg2.wait_for_timeout(1200)
        print("받는 쪽 안내:", (await pg2.inner_text("#notice")).replace("\n"," ")[:140])
        await b.close()
asyncio.run(main())
