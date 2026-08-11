"""표제의 '한 장으로' — 지금 보는 과목의 정적 페이지로 정확히 가는가."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from harness import CHROME, ROOT, SHOT, site, Serve
_srv, SITE = site()
import asyncio
from playwright.async_api import async_playwright
CH = CHROME
B = SITE.rstrip("/")
async def main():
    err=[]
    async with async_playwright() as p:
        b=await p.chromium.launch(executable_path=CH)
        pg=await (await b.new_context(viewport={"width":412,"height":900})).new_page()
        pg.on("console", lambda m: m.type=="error" and err.append(m.text))
        pg.on("pageerror", lambda e: err.append(str(e)))

        # 1. 여러 과목에서 링크가 그 과목을 가리키는가
        for path,want in [("/#/D300/158/all/all","s/D300/158.html"),
                          ("/#/D200/17022/all/all","s/D200/17022.html"),
                          ("/#/D300/140117/2024/all","s/D300/140117.html")]:
            await pg.goto(B+path, wait_until="load"); await pg.wait_for_timeout(900)
            a=pg.locator(".tally .onepage")
            print(f"{path:28} href={await a.get_attribute('href')}  맞음:",
                  await a.get_attribute("href")==want)
            print("   표제:", await pg.inner_text(".tally .big"),
                  "| aria:", (await a.get_attribute("aria-label"))[:34])

        # 2. 실제로 눌러서 그 과목 페이지가 열리는가
        await pg.goto(B+"/#/D300/158/all/all", wait_until="load"); await pg.wait_for_timeout(900)
        await pg.click(".tally .onepage"); await pg.wait_for_load_state("load")
        print("눌러서 도착:", pg.url.replace(SITE, "/"), "| h1:", await pg.inner_text("h1"))
        # 돌아오는 길
        await pg.click(".pg .go a.app"); await pg.wait_for_timeout(1200)
        print("앱으로 복귀:", pg.url.replace(SITE, "/"), "| 표제:", await pg.inner_text(".tally .big"))

        # 3. 앱(WebView) 안에서는 내주지 않는가
        c=await b.new_context(viewport={"width":412,"height":900})
        await c.add_init_script("window.GijulNative={listSaved:()=>'[]',appInfo:()=>'{}'};")
        pg2=await c.new_page()
        await pg2.goto(B+"/#/D300/158/all/all", wait_until="load"); await pg2.wait_for_timeout(900)
        print("앱에서 한 장으로:", await pg2.locator(".tally .onepage").count(),
              "개 | 받아둔 자료:", await pg2.locator(".tally .vault").count(), "개")

        # 4. 오른쪽 끝에 붙어 있는가 (묶음이 흩어지지 않았는지)
        await pg2.wait_for_timeout(200)
        box=await pg2.evaluate("""()=>{const t=document.querySelector('.tally'),
            a=document.querySelector('.tally-acts');
            if(!a) return null;
            return [Math.round(t.getBoundingClientRect().right - a.getBoundingClientRect().right),
                    a.children.length];}""")
        print("표제 오른쪽 여백(px), 단추 수:", box)
        print("ERRORS:", err or "없음")
        await b.close()
asyncio.run(main())
