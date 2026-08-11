"""보내기 시트 — 파일을 받아 공유로 넘기는 길과 그 길이 막혔을 때."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from harness import CHROME, ROOT, SHOT, site, Serve
_srv, SITE = site()
import re
from playwright.sync_api import sync_playwright

URL = SITE
SHOT = str(SHOT) + "/"

# Records the File handed to navigator.share, and makes share behave as told.
STUB = """(mode) => {
  window.__shared = [];
  navigator.canShare = (d) => !!(d && d.files && d.files.length);
  navigator.share = async (d) => {
    const f = d.files[0];
    window.__shared.push({name: f.name, type: f.type, size: f.size, title: d.title});
    if (mode === 'notallowed' && window.__shared.length === 1) {
      const e = new Error('x'); e.name = 'NotAllowedError'; throw e;
    }
    if (mode === 'abort') { const e = new Error('x'); e.name = 'AbortError'; throw e; }
  };
}"""

# The sandboxed browser has no route to EBSi, so serve fixtures with the same
# headers curl observed on the real server (Access-Control-Allow-Origin: *).
PDF = b"%PDF-1.4\n" + b"0" * 4000
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 900

def stub_ebsi(pg):
    def handler(route):
        u = route.request.url
        body, ctype = (PNG, "image/png") if u.endswith(".png") else (PDF, "application/pdf")
        route.fulfill(status=200, body=body, headers={
            "Content-Type": ctype,
            "Content-Length": str(len(body)),
            "Access-Control-Allow-Origin": "*",
        })
    pg.route(re.compile(r"wdown\.ebsi\.co\.kr"), handler)

def rows(pg):
    return pg.eval_on_selector_all("#sheetList .sfile", """els => els.map(e => ({
        kind: e.querySelector('.k').textContent,
        name: e.querySelector('.x').textContent,
        btn: e.querySelector('.go').textContent,
        state: e.querySelector('.go').dataset.state || ''}))""")

def open_first_sheet(pg):
    pg.wait_for_selector(".item .send")
    pg.click(".item .send >> nth=0")
    pg.wait_for_selector("#sheet:not([hidden])")

with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path=CHROME)

    def page(mode=None):
        ctx = b.new_context(viewport={"width": 412, "height": 900}, device_scale_factor=2,
                            accept_downloads=True, service_workers="block")
        pg = ctx.new_page()
        pg.errs = []
        pg.on("pageerror", lambda e: pg.errs.append(str(e)))
        pg.on("console", lambda m: pg.errs.append("console:" + m.text) if m.type == "error"
              and "ERR_CONNECTION" not in m.text else None)
        if mode:
            pg.add_init_script("(" + STUB + ")(" + repr(mode).replace("'", '"') + ")")
        stub_ebsi(pg)
        pg.goto(URL, wait_until="domcontentloaded")
        pg.wait_for_selector(".item", timeout=20000)
        return pg

    # ---- 1. sheet contents + filenames
    pg = page("ok")
    n_items = pg.eval_on_selector_all(".item", "e=>e.length")
    n_send = pg.eval_on_selector_all(".item .send", "e=>e.length")
    no_file = pg.eval_on_selector_all(".item",
        "e=>e.filter(x=>x.querySelectorAll('.acts .off').length===3).length")
    print(f"1. items={n_items} send-buttons={n_send} all-missing-items={no_file} "
          f"-> {'OK' if n_send == n_items - no_file else 'MISMATCH'}")
    open_first_sheet(pg)
    print("   header:", pg.text_content("#sheetNm"), "|", pg.text_content("#sheetSb"))
    for r in rows(pg):
        print("   row:", r["kind"], "->", r["name"])
    pg.screenshot(path=SHOT + "shot-sheet.png")

    # ---- 2. happy path share
    pg.click("#sheetList .go >> nth=0")
    pg.wait_for_function("() => window.__shared.length === 1")
    got = pg.evaluate("window.__shared[0]")
    print("2. shared File:", got)
    print("   button now:", rows(pg)[0]["btn"], "/ state:", rows(pg)[0]["state"])

    print("   size matches served bytes:", got["size"] == len(PDF), f"({got['size']} vs {len(PDF)})")
    print("   mime correct:", got["type"] == "application/pdf")

    # the 정답 row is a PNG -> different mime must flow through
    pg.click("#sheetList .go >> nth=1")
    pg.wait_for_function("() => window.__shared.length === 2")
    png = pg.evaluate("window.__shared[1]")
    print("   png row:", png["name"], png["type"], png["size"],
          "->", "OK" if png["type"] == "image/png" and png["size"] == len(PNG) else "BAD")
    print("   ERRORS:", pg.errs or "none")
    pg.context.close()

    # ---- 3. NotAllowedError -> confirm button -> second tap shares from cache
    pg = page("notallowed")
    reqs = []
    pg.on("request", lambda r: reqs.append(r.url) if ".pdf" in r.url else None)
    open_first_sheet(pg)
    pg.click("#sheetList .go >> nth=0")
    pg.wait_for_function("() => document.querySelector('#sheetList .go').dataset.state === 'confirm'")
    print("3. after NotAllowedError:", rows(pg)[0]["btn"], "| note:", pg.text_content("#sheetNote")[:34])
    before = len([r for r in reqs if ".pdf" in r])
    pg.click("#sheetList .go >> nth=0")
    pg.wait_for_function("() => window.__shared.length === 2")
    after = len([r for r in reqs if ".pdf" in r])
    print("   2nd tap shared:", rows(pg)[0]["btn"],
          "| refetched:", after > before, f"(pdf requests {before} -> {after})")
    print("   ERRORS:", pg.errs or "none")
    pg.context.close()

    # ---- 4. AbortError -> silent revert
    pg = page("abort")
    open_first_sheet(pg)
    note_before = pg.text_content("#sheetNote")
    pg.click("#sheetList .go >> nth=0")
    pg.wait_for_function("() => window.__shared.length === 1")
    pg.wait_for_function("() => document.querySelector('#sheetList .go').textContent === '보내기'")
    print("4. after AbortError: btn =", rows(pg)[0]["btn"],
          "| sheet still open:", not pg.is_hidden("#sheet"),
          "| note unchanged:", pg.text_content("#sheetNote") == note_before)
    print("   ERRORS:", pg.errs or "none")
    pg.context.close()

    # ---- 5. no Web Share -> download fallback with Korean filename
    pg = page()
    pg.add_init_script("delete navigator.share; delete navigator.canShare;")
    pg.reload(wait_until="domcontentloaded")
    pg.wait_for_selector(".item", timeout=20000)
    open_first_sheet(pg)
    expected = rows(pg)[0]["name"]
    with pg.expect_download() as dl:
        pg.click("#sheetList .go >> nth=0")
    d = dl.value
    print("5. download:", repr(d.suggested_filename),
          "| matches sheet:", d.suggested_filename == expected,
          "| btn:", rows(pg)[0]["btn"])
    print("   note:", pg.text_content("#sheetNote"))
    print("   ERRORS:", pg.errs or "none")
    pg.context.close()

    # ---- 6. fetch failure -> new tab + message
    pg = page("ok")
    pg.route(re.compile(r"wdown\.ebsi\.co\.kr.*\.pdf"), lambda r: r.abort())
    open_first_sheet(pg)
    with pg.context.expect_page() as popup:
        pg.click("#sheetList .go >> nth=0")
    print("6. fetch blocked -> popup:", popup.value.url[:58])
    print("   btn reset:", rows(pg)[0]["btn"], "| note:", pg.text_content("#sheetNote")[:30])
    # 이 자리는 내려받기를 일부러 막은 경우다 — 그때 나는 네트워크 오류는 기대한 것이다.
    print("   ERRORS:", [e for e in pg.errs if "ERR_FAILED" not in e] or "none (막은 요청 1건 제외)")
    pg.context.close()

    # ---- 7. a11y: esc / backdrop / focus / scroll lock
    pg = page("ok")
    open_first_sheet(pg)
    locked = pg.evaluate("document.body.style.overflow")
    focused = pg.evaluate("document.activeElement.id")
    pg.keyboard.press("Escape")
    pg.wait_for_selector("#sheet[hidden]", state="attached")
    restored = pg.evaluate("document.activeElement.classList.contains('send')")
    print(f"7. scroll-lock={locked!r} focus-on-open={focused!r} esc-closes=True "
          f"focus-restored={restored} unlocked={pg.evaluate('document.body.style.overflow')!r}")
    open_first_sheet(pg)
    pg.click("#sheetBg", position={"x": 5, "y": 5})
    print("   backdrop closes:", pg.is_hidden("#sheet"))

    # ---- 8. regression: existing links + 내 과목 still fine
    a = pg.eval_on_selector(".item .acts a.q", "e=>({t:e.textContent,h:e.href,tg:e.target})")
    pg.click("#favToggle")
    pg.reload(wait_until="domcontentloaded")
    pg.wait_for_selector(".item", timeout=20000)
    print("8. 문제 link:", a["t"], a["tg"], a["h"][:52])
    print("   내 과목 persisted:", pg.eval_on_selector_all("#favBox .pill", "e=>e.map(x=>x.textContent)"))
    print("   ERRORS:", pg.errs or "none")

    b.close()
