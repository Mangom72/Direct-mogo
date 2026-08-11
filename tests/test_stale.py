"""'새로고침'을 닫은 뒤 다시 확인하면 무엇이라 말하는가.

신고: 업데이트 확인 → '새 자료가 있습니다' → 닫기 → 다시 확인 → '최신입니다'.
워커의 check()가 견준 뒤 캐시를 갱신해 버려, 두 번째 확인은 갱신된 캐시와
서버를 견주기 때문이다. 정작 낡은 것은 지금 떠 있는 이 문서다.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from harness import CHROME, ROOT, SHOT, site, Serve
_srv, SITE = site()
import re, shutil, subprocess, time, pathlib, sys
from playwright.sync_api import sync_playwright


# 셸이 바뀐 상황을 만들어야 하므로 사본을 내준다.
_own = Serve(copy=True).__enter__()
TMP, URL = _own.dir, _own.url

# 앱인 척한다 — '업데이트 확인' 단추는 앱에서만 나온다
STUB=("window.GijulNative={systemDark:()=>false,listSaved:()=>'[]',savePaper:()=>{},"
      "shareFile:()=>{},openSaved:()=>{},deleteSaved:()=>{},where:()=>'/d',"
      "appVersion:()=>'{\"code\":28,\"name\":\"3.7\"}',"
      "checkUpdate:()=>{setTimeout(()=>window.gijulUpdate('latest'),50);},installUpdate:()=>{}};")
BAD=[]
try:
    with sync_playwright() as pw:
        b=pw.chromium.launch(executable_path=CHROME)
        ctx=b.new_context(viewport={"width":412,"height":900})
        ctx.add_init_script(STUB)
        pg=ctx.new_page(); errs=[]
        pg.on("pageerror", lambda e: errs.append(str(e)[:120]))
        pg.goto(URL, wait_until="load")
        pg.wait_for_selector(".item", timeout=25000)
        pg.wait_for_function("()=>navigator.serviceWorker.controller!==null", timeout=25000)
        pg.wait_for_function("()=>caches.keys().then(k=>k.some(n=>n.startsWith('gijul-shell')))", timeout=20000)
        print("0. 워커 등록·셸 캐시 완료")

        # 서버 쪽 껍데기를 바꾼다
        idx=TMP/"index.html"
        idx.write_text(idx.read_text(encoding="utf-8").replace("</body>","<!-- 새 판 --></body>"), encoding="utf-8")

        def check_and_read(label):
            pg.evaluate("()=>{document.getElementById('notice').hidden=true;}")
            pg.click("#appInfo button")
            pg.wait_for_function(
                "()=>{const n=document.getElementById('notice');"
                "return !n.hidden && !/확인하는 중/.test(document.getElementById('noticeText').textContent);}",
                timeout=20000)
            t=pg.text_content("#noticeText").strip()
            y=pg.text_content("#noticeYes").strip()
            print(f"{label} 막대: {t!r} / 단추 {y!r}")
            return t, y

        t1, y1 = check_and_read("1. 처음 확인 —")
        if "새 자료" not in t1 or y1 != "새로고침": BAD.append("첫 확인이 새 자료를 알리지 않습니다")

        pg.click("#noticeNo"); pg.wait_for_timeout(300)
        print("2. 닫기 — 막대 숨김:", pg.evaluate("()=>document.getElementById('notice').hidden"))

        t2, _ = check_and_read("3. 다시 확인 —")
        if "새 자료" not in t2: BAD.append(f"다시 확인했더니 {t2!r} — 아직 옛 화면인데 최신이라고 합니다")

        # 새로고침하면 진짜 최신이 된다
        pg.reload(wait_until="load"); pg.wait_for_selector(".item", timeout=25000)
        pg.wait_for_function("()=>navigator.serviceWorker.controller!==null", timeout=25000)
        pg.wait_for_timeout(1500)
        t3, _ = check_and_read("4. 새로고침 뒤 —")
        if "새 자료" in t3: BAD.append(f"새로고침했는데도 {t3!r}")
        print("   오류:", errs or "없음")
        b.close()
finally:
    _own.__exit__()
print("\n=== 문제:", "없음" if not BAD else "")
for x in BAD: print("  ★", x)
sys.exit(1 if BAD else 0)
