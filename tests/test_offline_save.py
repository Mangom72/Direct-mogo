"""오프라인 저장 — 회차를 통째로 담아 두고 연결 없이 여는 흐름.

앱은 앱 폴더에, 웹은 Cache Storage 의 회차별 통(`gijul-vault:회차`)에 담는다.
이 시험은 웹 뒤판만 본다 — 앱 쪽은 창구를 부르는 데서 끝나고 그 뒤는 자바다.

담은 뒤에 단추가 **잠기는 것이 정상이다.** 같은 회차를 두 번 담아 봐야 자료는
늘지 않는데 화면만 '받는 중'을 거쳐 성공한 것처럼 보이던 것을 막은 것이다.
"""
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

KEPT = "() => document.querySelector('#sheetAll').classList.contains('kept')"
FREE = "() => !document.querySelector('#sheetAll').disabled"
BOXES = "async () => (await caches.keys()).filter(n => n.startsWith('gijul-vault:'))"

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
        return pg

    def sheet(pg, nth=0):
        pg.click(f".item .send >> nth={nth}")
        pg.wait_for_selector("#sheet:not([hidden])")

    # ---- 1. 담기 — 통이 생기고 단추가 잠긴다
    pg = page(); sheet(pg)
    label = pg.text_content("#sheetAll")
    print("1. 단추:", repr(label), "| 보임:", pg.is_visible("#sheetAll"))
    assert "보관함" in label, label
    rows = pg.eval_on_selector_all("#sheetList .sfile .x", "e=>e.map(x=>x.textContent)")
    print("   회차 파일:", len(rows), "개")

    pg.click("#sheetAll")
    pg.wait_for_function(KEPT, timeout=30000)
    boxes = pg.evaluate(BOXES)
    print("   담긴 통:", len(boxes), "개 —", boxes[0] if boxes else "(없음)")
    assert len(boxes) == 1, boxes

    names = pg.evaluate(
        "async n => { const c = await caches.open(n);"
        " const r = await c.match(new URL('__vault__', location.href).href);"
        " return (await r.json()).map(x => x.name); }", boxes[0])
    print("   통 안의 파일:", len(names), "| 목록과 일치:", sorted(names) == sorted(rows))
    assert sorted(names) == sorted(rows), (names, rows)

    print("   안내:", pg.text_content("#sheetNote").split("파일로")[0].strip())
    print("   단추:", repr(pg.text_content("#sheetAll")),
          "| 잠김:", pg.evaluate("document.querySelector('#sheetAll').disabled"))
    assert pg.evaluate("document.querySelector('#sheetAll').disabled")
    print("   ERRORS:", pg.errs or "none")

    # ---- 2. 목록에 '담김'이 붙고 '받아둔 자료'가 열린다
    pg.click("#sheetX")
    pg.wait_for_selector(".item .meta .kept", timeout=10000)
    marks = pg.eval_on_selector_all(".item .meta .kept", "e=>e.length")
    print("2. 목록의 '담김' 표시:", marks, "개 | 받아둔 자료 단추:", pg.is_visible("#vaultBtn"))
    assert marks == 1 and pg.is_visible("#vaultBtn")

    pg.click("#vaultBtn")
    pg.wait_for_selector(".svault", timeout=10000)
    print("   보관함:", repr(pg.text_content("#sheetSb")),
          "| 회차:", repr(pg.text_content(".svault .nm")))
    kinds = pg.eval_on_selector_all(".svault .row button:not(.del)", "e=>e.map(x=>x.textContent)")
    print("   단추:", kinds)
    assert kinds == ["문제", "정답", "해설", "내려받기"], kinds

    # 밖으로 꺼내는 길이 늘 함께 있다 — 브라우저가 blob 을 제 뷰어로 펴 주는지에
    # 기대지 않는다(iOS 사파리가 PDF blob 을 어떻게 다루는지는 판마다 달랐다).
    out = []
    pg.on("download", lambda d: out.append(d.suggested_filename))
    pg.click(".svault .row button >> nth=3")
    pg.wait_for_timeout(2600)
    print("   내려받기:", len(out), "개 | 통은 그대로:", len(pg.evaluate(BOXES)), "개")
    assert len(out) == 3, out
    assert len(pg.evaluate(BOXES)) == 1

    # ---- 3. 지우면 통도 표시도 함께 사라진다
    pg.click(".svault .row .del")          # 한 번 더 물어본다
    pg.click(".svault .row .del")
    pg.wait_for_function("async () => (await caches.keys())"
                         ".filter(n => n.startsWith('gijul-vault:')).length === 0", timeout=10000)
    pg.wait_for_function("() => !document.querySelector('.item .meta .kept')", timeout=10000)
    print("3. 지운 뒤 — 통:", len(pg.evaluate(BOXES)),
          "개 | '담김' 표시:", pg.eval_on_selector_all(".item .meta .kept", "e=>e.length"),
          "개 | 안내:", pg.text_content("#sheetNote")[:20])
    print("   ERRORS:", pg.errs or "none")
    pg.context.close()

    # ---- 4. 이미 받은 파일은 다시 받지 않는다
    pg = page(); sheet(pg)
    reqs = []
    pg.on("request", lambda r: reqs.append(r.url) if "wdown" in r.url else None)
    pg.click("#sheetList .go >> nth=0")     # 첫 파일을 먼저 받아 캐시에 넣음
    pg.wait_for_timeout(900)
    before = len(reqs)
    pg.click("#sheetAll")
    pg.wait_for_function(KEPT, timeout=30000)
    after = len(reqs)
    print(f"4. 이미 받은 파일 재사용: 요청 {before} -> {after} (3개 중 1개 캐시 적중:",
          after - before == 2, ")")
    assert after - before == 2, (before, after)
    pg.context.close()

    # ---- 5. 중간에 끊기면 반만 담긴 회차를 남기지 않는다
    pg = page(fail=True); sheet(pg)
    pg.click("#sheetAll")
    pg.wait_for_function(FREE, timeout=30000)
    print("5. 전부 실패 시 —", pg.text_content("#sheetNote").split("파일로")[0].strip())
    print("   남은 통:", len(pg.evaluate(BOXES)), "개 (반만 담긴 회차를 남기지 않는다)")
    assert pg.evaluate(BOXES) == []
    print("   단추 다시 누를 수 있음:", not pg.evaluate("document.querySelector('#sheetAll').disabled"),
          "| 라벨:", repr(pg.text_content("#sheetAll")))
    print("   ERRORS:", pg.errs or "none")
    pg.context.close()

    # ---- 6. 파일 자체를 원하는 사람의 길은 남아 있다
    pg = page(); sheet(pg)
    got = []
    pg.on("download", lambda d: got.append(d.suggested_filename))
    dl = pg.wait_for_selector("#sheetNote button", timeout=10000)
    print("6. 곁길:", repr(dl.text_content()))
    dl.click()
    pg.wait_for_timeout(2600)
    print("   내려받은 파일:", len(got))
    for g in got:
        print("     ", g)
    print("   통은 안 늘어남:", len(pg.evaluate(BOXES)), "개")
    assert len(got) == 3, got
    print("   ERRORS:", pg.errs or "none")

    # ---- 7. 다른 회차를 열면 상태가 새로 시작된다
    pg.click("#sheetX")
    sheet(pg, 1)
    print("7. 다른 회차 — 안내:", pg.text_content("#sheetNote")[:24],
          "| 라벨:", repr(pg.text_content("#sheetAll")),
          "| 헤더:", pg.text_content("#sheetNm"))
    print("   ERRORS:", pg.errs or "none")

    b.close()
