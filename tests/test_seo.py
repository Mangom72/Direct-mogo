"""구글 문서에 적힌 것만 골라 확인한다."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from harness import CHROME, ROOT, SHOT, site, Serve
_srv, SITE = site()
import asyncio, json, re, pathlib, xml.etree.ElementTree as ET
from playwright.async_api import async_playwright
CH = CHROME
B = SITE.rstrip("/")
R=ROOT

async def main():
    bad=[]
    async with async_playwright() as p:
        b=await p.chromium.launch(executable_path=CH)
        pg=await (await b.new_context(viewport={"width":412,"height":900})).new_page()
        viol=[]
        await pg.add_init_script(
            "addEventListener('securitypolicyviolation',e=>{"
            "(window.__v=window.__v||[]).push(e.violatedDirective)})")

        # 1. 제목·설명이 페이지마다 다른가 (구글: 반복·보일러플레이트 금지)
        titles, descs = {}, {}
        for path in ["/", "/s/", "/s/D300/158.html", "/s/D200/140220.html",
                     "/s/D300/80003.html", "/s/D100/110001.html"]:
            await pg.goto(B+path, wait_until="load"); await pg.wait_for_timeout(250)
            t=await pg.title()
            d=await pg.get_attribute("meta[name=description]","content") or ""
            titles[path]=t; descs[path]=d
            print(f"{path:24} {len(t):3}자  {t}")
        if len(set(titles.values()))!=len(titles): bad.append("제목이 겹칩니다")
        if len(set(descs.values()))!=len(descs): bad.append("설명이 겹칩니다")
        print("\n제목 전부 다름:", len(set(titles.values()))==len(titles),
              "| 설명 전부 다름:", len(set(descs.values()))==len(descs))

        # 2. 빵부스러기 구조화 데이터 — 화면에 보이는 글자와 같아야 한다
        await pg.goto(B+"/s/D300/158.html", wait_until="load"); await pg.wait_for_timeout(300)
        ld=json.loads(await pg.eval_on_selector('script[type="application/ld+json"]',
                                                "e=>e.textContent"))
        seen=await pg.eval_on_selector_all(".crumb a, .crumb b","e=>e.map(x=>x.textContent.trim())")
        names=[i["name"] for i in ld["itemListElement"]]
        print("\n구조화 데이터:", names)
        print("화면 빵부스러기:", seen)
        if names!=seen: bad.append("구조화 데이터와 화면이 다릅니다")
        pos=[i["position"] for i in ld["itemListElement"]]
        if pos!=list(range(1,len(pos)+1)): bad.append("position이 1부터 차례가 아닙니다")
        if "item" in ld["itemListElement"][-1]: bad.append("마지막 칸에 item이 붙어 있습니다")
        if len(names)<2: bad.append("빵부스러기가 두 칸 미만입니다")
        print("CSP 위반:", await pg.evaluate("()=>window.__v||[]") or "없음")
        if await pg.evaluate("()=>window.__v||[]"): bad.append("CSP가 무언가를 막았습니다")

        # 3. 사이트맵 — 무시되는 칸이 없고 날짜가 주소마다 정확한가
        sm=ET.fromstring((R/"sitemap.xml").read_text())
        NS="{http://www.sitemaps.org/schemas/sitemap/0.9}"
        urls=sm.findall(NS+"url")
        if sm.findall(f".//{NS}priority") or sm.findall(f".//{NS}changefreq"):
            bad.append("구글이 무시하는 priority/changefreq가 남아 있습니다")
        dates={u.find(NS+"lastmod").text for u in urls}
        print(f"\n사이트맵 {len(urls)}개 · 서로 다른 날짜 {len(dates)}가지 "
              f"· priority/changefreq 없음: "
              f"{not sm.findall(f'.//{NS}priority')}")
        # 과목 페이지 날짜가 그 과목 최신 시행일과 맞는가
        idx=json.loads((R/"data/index.json").read_text()); wrong=0
        for u in urls:
            loc=u.find(NS+"loc").text
            m=re.search(r"/s/(D\d00)/(\d+)\.html$", loc)
            if not m: continue
            want=json.loads((R/f"data/{m.group(1)}/{m.group(2)}.json").read_text())["papers"][0]["date"]
            if u.find(NS+"lastmod").text != want: wrong+=1
        print("과목 페이지 lastmod 어긋남:", wrong)
        if wrong: bad.append("lastmod가 실제 최신 시행일과 다릅니다")

        # 4. 내부 링크 — 색인에서 49장이 다 닿는가
        await pg.goto(B+"/s/", wait_until="load")
        hrefs=await pg.eval_on_selector_all(".subs a","e=>e.map(x=>x.getAttribute('href'))")
        print("색인에서 나가는 과목 링크:", len(hrefs))
        if len(hrefs)!=49: bad.append("과목 링크가 49개가 아닙니다")
        # 링크 글자가 설명적인가 (구글: 'here' 같은 것 금지)
        texts=await pg.eval_on_selector_all(".subs a","e=>e.map(x=>x.textContent.trim())")
        if any(len(t)<2 for t in texts): bad.append("링크 글자가 너무 짧습니다")

        print("\n=== 문제:", bad or "없음")
        await b.close()
asyncio.run(main())
