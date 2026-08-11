"""오프라인 저장 — 회차를 통째로 내려받아 앱 폴더에 보관하는 흐름."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from harness import CHROME, ROOT, SHOT, site, Serve
_srv, SITE = site()
import re
from playwright.sync_api import sync_playwright

URL = SITE
PDF = b"%PDF-1.4\n" + b"0" * 3000
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 800

def stub(pg, fail=False):
    def h(route):
        if fail:
            return route.abort()
        u = route.request.url
        body, ct = (PNG, "image/png") if u.endswith(".png") else (PDF, "application/pdf")
        route.fulfill(status=200, body=body, headers={
            "Content-Type": ct, "Access-Control-Allow-Origin": "*"})
    pg.route(re.compile(r"wdown\.ebsi\.co\.kr"), h)

with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path=CHROME)

    def page(fail=False):
        ctx = b.new_context(viewport={"width": 412, "height": 900}, accept_downloads=True,
                            service_workers="block")
        pg = ctx.new_page()
        pg.errs = []
        pg.on("pageerror", lambda e: pg.errs.append(str(e)))
        pg.on("console", lambda m: pg.errs.append("console:" + m.text)
              if m.type == "error" and "ERR_" not in m.text else None)
        stub(pg, fail)
        pg.goto(URL, wait_until="domcontentloaded")
        pg.wait_for_selector(".item .send", timeout=20000)
        pg.click(".item .send >> nth=0")
        pg.wait_for_selector("#sheet:not([hidden])")
        return pg

    # ---- 1. button present, labelled, and all three files download
    pg = page()
    print("1. 버튼:", repr(pg.text_content("#sheetAll")), "| 보임:", pg.is_visible("#sheetAll"))
    rows = pg.eval_on_selector_all("#sheetList .sfile .x", "e=>e.map(x=>x.textContent)")
    print("   회차 파일:", len(rows), "개")
    got = []
    pg.on("download", lambda d: got.append(d.suggested_filename))
    pg.click("#sheetAll")
    pg.wait_for_function("() => !document.querySelector('#sheetAll').disabled", timeout=30000)
    pg.wait_for_timeout(600)
    print("   저장된 파일:", len(got))
    for g in got:
        print("     ", g)
    print("   파일명이 목록과 일치:", sorted(got) == sorted(rows))
    print("   안내:", pg.text_content("#sheetNote"))
    print("   버튼 원복:", repr(pg.text_content("#sheetAll")))
    print("   ERRORS:", pg.errs or "none")
    pg.context.close()

    # ---- 2. cached blobs are reused (no refetch after a share/save)
    pg = page()
    reqs = []
    pg.on("request", lambda r: reqs.append(r.url) if "wdown" in r.url else None)
    pg.click("#sheetList .go >> nth=0")          # 첫 파일을 먼저 받아 캐시에 넣음
    pg.wait_for_timeout(900)
    before = len(reqs)
    pg.click("#sheetAll")
    pg.wait_for_function("() => !document.querySelector('#sheetAll').disabled", timeout=30000)
    after = len(reqs)
    print(f"2. 이미 받은 파일 재사용: 요청 {before} -> {after} (파일 3개 중 1개는 캐시 적중:",
          after - before == 2, ")")
    pg.context.close()

    # ---- 3. network failure is reported, button recovers
    pg = page(fail=True)
    pg.click("#sheetAll")
    pg.wait_for_function("() => !document.querySelector('#sheetAll').disabled", timeout=30000)
    print("3. 전부 실패 시 —", pg.text_content("#sheetNote"))
    print("   버튼 다시 누를 수 있음:", not pg.evaluate("document.querySelector('#sheetAll').disabled"),
          "| 라벨:", repr(pg.text_content("#sheetAll")))
    print("   ERRORS:", pg.errs or "none")
    pg.context.close()

    # ---- 4. 시트를 다른 회차로 다시 열면 상태가 새로 시작되는지
    pg = page()
    pg.click("#sheetAll")
    pg.wait_for_function("() => !document.querySelector('#sheetAll').disabled", timeout=30000)
    pg.click("#sheetX")
    pg.click(".item .send >> nth=1")
    pg.wait_for_selector("#sheet:not([hidden])")
    print("4. 다른 회차 열기 — 안내 초기화:", pg.text_content("#sheetNote")[:28],
          "| 라벨:", repr(pg.text_content("#sheetAll")),
          "| 헤더:", pg.text_content("#sheetNm"))
    print("   ERRORS:", pg.errs or "none")

    b.close()
