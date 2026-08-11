"""앱 자체 업데이트의 페이지 쪽 동작. GijulNative를 흉내내 붙인다."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from harness import CHROME, ROOT, SHOT, site, Serve
_srv, SITE = site()
from playwright.sync_api import sync_playwright

URL = SITE
STUB = """
window.__calls = [];
window.GijulNative = {
  systemDark: () => false,
  listSaved: () => "[]",
  savePaper: a => window.__calls.push(["savePaper", a]),
  shareFile: (a,b) => window.__calls.push(["shareFile", a]),
  openSaved: () => {}, deleteSaved: () => {}, where: () => "/data",
  appVersion: () => '{"code":7,"name":"1.6"}',
  checkUpdate: f => window.__calls.push(["checkUpdate", f]),
  installUpdate: () => window.__calls.push(["installUpdate"]),
};
"""

def txt(pg, sel):
    return (pg.text_content(sel) or "").strip()

with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path=CHROME)
    ctx = b.new_context(viewport={"width": 412, "height": 900}, service_workers="block")
    ctx.add_init_script(STUB)
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("console", lambda m: errs.append("console:" + m.text) if m.type == "error" else None)
    pg.goto(URL, wait_until="load")
    pg.wait_for_selector(".item", timeout=20000)

    # 1. 실행하면 앱이 스스로 확인을 건다 (강제 아님)
    calls = pg.evaluate("window.__calls")
    print("1. 실행 시 확인 호출:", [c for c in calls if c[0] == "checkUpdate"])

    # 2. 새 버전이 있다고 알려주면 알림 막대가 뜬다
    pg.evaluate("""window.gijulUpdateFound(JSON.stringify(
        {state:"available", versionName:"1.7", size:1617566, notes:"한국사 자료 보강"}))""")
    print("2. 알림:", repr(txt(pg, "#noticeText")))
    print("   버튼:", repr(txt(pg, "#noticeYes")), "| 보임:", pg.is_visible("#notice"))

    # 3. 업데이트를 누르면 네이티브 설치가 시작되고 막대는 닫힌다
    pg.click("#noticeYes")
    print("3. 설치 호출:", any(c[0] == "installUpdate" for c in pg.evaluate("window.__calls")),
          "| 막대 닫힘:", not pg.is_visible("#notice"))

    # 4. 진행 상태
    pg.evaluate("window.gijulUpdate('downloading','')")
    print("4. 내려받는 중:", repr(txt(pg, "#noticeText")))
    pg.evaluate("window.gijulUpdate('installing','')")
    print("   설치 화면 뜨면 막대 닫힘:", not pg.is_visible("#notice"))

    # 5. 권한·실패는 이유가 보여야 한다
    pg.evaluate("window.gijulUpdate('permission','이 앱에서 설치를 허용해 주세요')")
    print("5. 권한 안내:", repr(txt(pg, "#noticeText")))
    pg.evaluate("window.gijulUpdate('error','서명이 이 앱과 다릅니다')")
    print("   실패 안내:", repr(txt(pg, "#noticeText")))
    pg.click("#noticeNo")
    print("   닫기 동작:", not pg.is_visible("#notice"))

    # 6. 브라우저(네이티브 없음)에서는 아무 일도 없어야 한다
    ctx2 = b.new_context(viewport={"width": 412, "height": 900}, service_workers="block")
    pg2 = ctx2.new_page()
    e2 = []
    pg2.on("pageerror", lambda e: e2.append(str(e)))
    pg2.goto(URL, wait_until="load")
    pg2.wait_for_selector(".item", timeout=20000)
    print("6. 브라우저 — gijulUpdateFound 없음:",
          pg2.evaluate("typeof window.gijulUpdateFound === 'undefined'"),
          "| 막대 숨김:", not pg2.is_visible("#notice"), "| 오류:", e2 or "없음")

    print("ERRORS:", errs or "없음")
    b.close()
with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path=CHROME)

    ctx = b.new_context(viewport={"width": 412, "height": 900}, service_workers="block")
    ctx.add_init_script(STUB)
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(URL, wait_until="load")
    pg.wait_for_selector(".item", timeout=20000)
    print("7. 앱 — 판 정보 보임:", pg.is_visible("#appInfo"), "|", repr(txt(pg, "#appInfo")))
    pg.click("#appInfo button")
    print("   확인 버튼 -> 네이티브 호출:",
          [c for c in pg.evaluate("window.__calls") if c[0] == "checkUpdate"])
    pg.evaluate("window.gijulUpdate('latest','이미 최신 버전입니다')")
    print("   최신일 때 안내:", repr(txt(pg, "#noticeText")))
    print("   푸터 맨 아래에 있는지:",
          pg.evaluate("!!document.querySelector('footer').contains(document.querySelector('#appInfo'))"),
          "| 마지막 자식:",
          pg.evaluate("document.querySelector('footer').lastElementChild.id"))

    ctx2 = b.new_context(viewport={"width": 412, "height": 900}, service_workers="block")
    pg2 = ctx2.new_page()
    pg2.goto(URL, wait_until="load")
    pg2.wait_for_selector(".item", timeout=20000)
    print("8. 브라우저 — 판 정보 숨김:", not pg2.is_visible("#appInfo"),
          "| 내용 비어있음:", txt(pg2, "#appInfo") == "")
    print("ERRORS:", errs or "없음")
    b.close()
