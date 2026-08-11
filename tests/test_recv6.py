"""링크로 받은 과목이 하나도 빠지지 않고 들어오는가 (여섯 개를 보낸다)."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from harness import CHROME, ROOT, SHOT, site, Serve
_srv, SITE = site()
import asyncio, json
from playwright.async_api import async_playwright
CH = CHROME
URL=(SITE + "#subs=D300.140117,D300.140119,D300.80003,"
     "D300.63004,D300.66001,D300.158")
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(executable_path=CH)
        for label, pre in [("빈 목록", []), ("이미 1개 있음", [{"g":"D300","s":"158"}])]:
            c=await b.new_context(viewport={"width":412,"height":900})
            pg=await c.new_page()
            pg.on("console", lambda m: m.type=="error" and print("  console:",m.text))
            await pg.goto(SITE, wait_until="load")
            await pg.evaluate("f=>localStorage.setItem('gijul.mysubs.v1',JSON.stringify(f))",pre)
            await pg.goto(URL, wait_until="load"); await pg.wait_for_timeout(1500)
            print(f"== {label}")
            print("  안내:", (await pg.inner_text("#notice")).replace("\n"," / ")[:130])
            await pg.click("#noticeYes")
            await pg.wait_for_timeout(600)
            pills = await pg.eval_on_selector_all("button.pill","e=>e.map(x=>x.textContent)")
            ls = await pg.evaluate("()=>localStorage.getItem('gijul.mysubs.v1')")
            print("  알약:", pills)
            print("  저장:", len(json.loads(ls)), "개")
            await c.close()
        await b.close()
asyncio.run(main())
