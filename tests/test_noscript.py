"""스크립트를 끈 화면 — 안내가 나오고 각주 링크가 살아 있는가."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from harness import CHROME, ROOT, SHOT, site, Serve
_srv, SITE = site()
import asyncio
from playwright.async_api import async_playwright
CH = CHROME
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(executable_path=CH)
        # 스크립트가 도는 보통 브라우저
        pg=await (await b.new_context(viewport={"width":412,"height":900})).new_page()
        await pg.goto(SITE, wait_until="load"); await pg.wait_for_timeout(1200)
        print("사람 화면에 noscript 상자 보임:", await pg.locator(".noscript").is_visible())
        print("각주 링크:", await pg.eval_on_selector_all("footer a.doc","e=>e.map(x=>x.textContent)"))
        # 스크립트를 끈 쪽
        c2=await b.new_context(viewport={"width":412,"height":900}, java_script_enabled=False)
        pg2=await c2.new_page()
        await pg2.goto(SITE, wait_until="load"); await pg2.wait_for_timeout(400)
        print("\n스크립트 끈 화면:")
        print("  noscript 보임:", await pg2.locator(".noscript").is_visible())
        print("  글:", (await pg2.locator(".noscript").inner_text()).replace("\n"," ")[:70],"…")
        await pg2.locator(".noscript").screenshot(
          path=str(SHOT / "noscript.png"))
        await b.close()
asyncio.run(main())
