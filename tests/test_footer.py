"""각주가 어디서 끊기는지 눈에 보이는가.

신고: 사진 아래 정보가 적힌 부분의 줄 간격이 이상하다. 항목을 <br>로만 나눠
두어, 한 항목이 두 줄로 넘어가면 그 줄 사이 간격과 항목 사이 간격이 같았다.
고치면서 매달린 들여쓰기를 넣었는데, 그 값이 inline-block 링크에 물려 내려가
링크가 앞 낱말에 달라붙는 일이 또 있었다. 둘 다 여기서 지킨다.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from harness import CHROME, ROOT, SHOT, site, Serve
_srv, SITE = site()
from playwright.sync_api import sync_playwright

BAD = []
def ck(cond, msg):
    if not cond:
        BAD.append(msg)

MEASURE = """()=>{
  const ns=[...document.querySelectorAll('footer .n')];
  const cs=n=>getComputedStyle(n);
  const rows=ns.map(n=>{const r=n.getBoundingClientRect();
    return {top:Math.round(r.top), bottom:Math.round(r.bottom),
            line:Math.round(parseFloat(cs(n).lineHeight)),
            gap:Math.round(parseFloat(cs(n).marginBottom))};});
  const links=[...document.querySelectorAll('footer .n a')]
      .map(a=>Math.round(parseFloat(getComputedStyle(a).textIndent)));
  return {count:ns.length, rows, links,
          wrapped:ns.filter(n=>n.getBoundingClientRect().height >
                               parseFloat(cs(n).lineHeight)*1.4).length};}"""

with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path=CHROME)
    for w in (412, 900, 1350):
        ctx = b.new_context(viewport={"width": w, "height": 900}, service_workers="block")
        pg = ctx.new_page()
        pg.goto(SITE, wait_until="load")
        pg.wait_for_selector("footer .n", timeout=20000)
        m = pg.evaluate(MEASURE)
        ck(m["count"] >= 4, f"{w}px: 각주 항목이 {m['count']}개뿐입니다 — 나뉘지 않았습니다")

        # 항목 사이 간격이 항목 안 줄 간격보다 넓어야 어디서 끊기는지 보인다
        line = m["rows"][0]["line"]
        gaps = [r["bottom"] for r in m["rows"]]
        between = [m["rows"][i + 1]["top"] - m["rows"][i]["bottom"] for i in range(len(m["rows"]) - 1)]
        ck(all(g >= 6 for g in between),
           f"{w}px: 항목 사이가 {between} — 줄 사이({line}px)와 구별되지 않습니다")
        ck(line <= 20, f"{w}px: 항목 안 줄 간격이 {line}px로 항목 사이만큼 넓습니다")

        # 매달린 들여쓰기가 링크에 물려 내려가면 앞 낱말에 달라붙는다
        ck(all(v == 0 for v in m["links"]),
           f"{w}px: 각주 링크가 들여쓰기를 물려받았습니다 {m['links'][:5]}")

        print(f"{w:>5}px  항목 {m['count']}개 · 두 줄 이상 {m['wrapped']}개 · "
              f"줄 간격 {line}px · 항목 사이 {between} · 링크 들여쓰기 {set(m['links'])}")
        ctx.close()
    b.close()

print("\n=== 문제:", "없음" if not BAD else "")
for x in BAD:
    print("  ★", x)
sys.exit(1 if BAD else 0)
