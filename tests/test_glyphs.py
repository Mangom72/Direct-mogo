"""화면에 실제로 그려지는 글자가 글꼴에 다 들어 있는가.

주석을 글자 목록에서 걷어냈으므로, 잘못 걷지 않았는지는 소스가 아니라
'그려진 것'으로 확인해야 한다. 앱 화면을 여러 상태로 돌려 보고 과목 페이지
50장을 전부 훑는다.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from harness import CHROME, ROOT, SHOT, site, Serve
_srv, SITE = site()
import glob, pathlib, sys
from fontTools.ttLib import TTFont
from playwright.sync_api import sync_playwright

BASE = SITE.rstrip("/")
COVER = None
for f in sorted(glob.glob(str(ROOT / "fonts/*.woff2"))):
    have = {chr(c) for c in TTFont(f).getBestCmap()}
    COVER = have if COVER is None else (COVER & have)
print(f"다섯 벌 모두가 덮는 글자 {len(COVER)}자")

TEXT = """()=>{const w=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);
 let s=''; while(w.nextNode()){const p=w.currentNode.parentElement;
   if(p && getComputedStyle(p).display!=='none' && p.offsetParent!==null) s+=w.currentNode.nodeValue;}
 for(const e of document.querySelectorAll('[aria-label],[placeholder],[title],input[value],option'))
   s += (e.getAttribute('aria-label')||'')+(e.getAttribute('placeholder')||'')+(e.getAttribute('title')||'')+(e.value||'')+(e.textContent||'');
 return s;}"""

seen = set()
def take(pg):
    seen.update(c for c in pg.evaluate(TEXT) if "가" <= c <= "힣")

with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path=CHROME)
    ctx = b.new_context(viewport={"width":412,"height":900}, service_workers="block")
    pg = ctx.new_page()
    pg.goto(BASE + "/", wait_until="load"); pg.wait_for_timeout(2500); take(pg)
    # 학년·과목군을 돌며 이름을 다 훑는다
    for gi in range(3):
        pg.eval_on_selector_all(".row [name=grade]", f"e=>e[{gi}] && e[{gi}].click()")
        pg.wait_for_timeout(120)
        n = pg.eval_on_selector_all("#grp option", "e=>e.length")
        for k in range(n):
            pg.select_option("#grp", index=k); pg.wait_for_timeout(90)
            m = pg.eval_on_selector_all("#sub option", "e=>e.length")
            for j in range(m):
                pg.select_option("#sub", index=j); pg.wait_for_timeout(60); take(pg)
    # 시트·보관함·안내 막대
    pg.eval_on_selector(".item .q", "e=>e.click()"); pg.wait_for_timeout(400); take(pg)
    pg.keyboard.press("Escape"); pg.wait_for_timeout(200)
    pg.goto(BASE + "/#subs=D300.140117-D300.140119", wait_until="load"); pg.wait_for_timeout(2500); take(pg)
    ctx.close()
    # 과목 페이지 전부
    ctx = b.new_context(viewport={"width":412,"height":900}, service_workers="block")
    pg = ctx.new_page()
    for f in ["/s/"] + sorted("/s/" + p.split("/s/")[1] for p in glob.glob(str(ROOT / "s/D*/*.html"))):
        pg.goto(BASE + f, wait_until="load"); take(pg)
    ctx.close()

miss = sorted(seen - COVER)
print(f"화면에서 본 한글 {len(seen)}자 · 글꼴에 없는 글자 {len(miss)}자")
if miss:
    print("★ 네모로 보일 글자:", "".join(miss))
print("\n=== 문제:", "없음" if not miss else "있음")
sys.exit(1 if miss else 0)
