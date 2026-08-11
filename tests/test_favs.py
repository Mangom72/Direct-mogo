"""내 과목 — ★로 저장, 삭제, 편집, 손상된 저장값에서 되살아나기."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from harness import CHROME, ROOT, SHOT, site, Serve
_srv, SITE = site()
from playwright.sync_api import sync_playwright

URL = SITE
SHOT = str(SHOT) + "/"

def pills(p):
    return p.eval_on_selector_all(
        "#favBox .pill",
        "els => els.map(e => ({t: e.textContent, on: e.getAttribute('aria-pressed')}))")

with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path=CHROME)
    ctx = b.new_context(viewport={"width": 412, "height": 900}, device_scale_factor=2,
                        service_workers="block")
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("console", lambda m: errs.append("console." + m.type + ": " + m.text) if m.type == "error" else None)

    pg.goto(URL, wait_until="networkidle")
    pg.wait_for_selector(".item", timeout=15000)
    print("1. loaded, default sub =", pg.input_value("#sub"), "| empty hint:",
          pg.is_visible("#favBox .pill-empty"), "| edit btn hidden:", pg.is_hidden("#favEdit"))

    # star the default subject (D300 / 생명과학Ⅰ)
    pg.click("#favToggle")
    print("2. after star:", pills(pg), "star on =", pg.get_attribute("#favToggle", "aria-pressed"))

    # add 미적분 (same grade, different group)
    pg.select_option("#grp", label="수학")
    pg.select_option("#sub", label="미적분")
    print("3. star state on unsaved sub =", pg.get_attribute("#favToggle", "aria-pressed"))
    pg.click("#favToggle")

    # add a 고2 subject so the grade tag kicks in
    pg.click("#gradeBox button >> nth=1")
    pg.select_option("#sub", label="국어")
    pg.click("#favToggle")
    print("4. multi-grade pills:", pills(pg))

    # click a pill -> should switch grade + group + subject
    pg.click("#favBox .pill >> nth=0")
    print("5. after pill click -> grade pressed:",
          pg.eval_on_selector_all("#gradeBox button", "e=>e.map(x=>x.getAttribute('aria-pressed'))"),
          "grp =", pg.input_value("#grp"), "sub =", pg.input_value("#sub"),
          "| pills:", pills(pg))
    print("   tally:", pg.text_content(".tally .big"), "|", pg.text_content(".tally .sm"))

    pg.screenshot(path=SHOT + "shot-mobile.png", full_page=False)

    # persistence across reload
    pg.reload(wait_until="networkidle")
    pg.wait_for_selector(".item", timeout=15000)
    print("6. after reload:", pills(pg), "| localStorage =",
          pg.evaluate("localStorage.getItem('gijul.mysubs.v1')"))

    # edit mode -> remove one
    pg.click("#favEdit")
    print("7. edit mode pills:", pills(pg))
    pg.click("#favBox .pill >> nth=1")
    pg.click("#favEdit")
    print("8. after delete:", pills(pg))

    # remove all -> empty hint returns, edit button hides
    pg.click("#favEdit")
    pg.click("#favBox .pill >> nth=0")
    pg.click("#favBox .pill >> nth=0")
    print("9. emptied:", pills(pg), "| hint:", pg.is_visible("#favBox .pill-empty"),
          "| edit hidden:", pg.is_hidden("#favEdit"),
          "| ls =", pg.evaluate("localStorage.getItem('gijul.mysubs.v1')"))

    # corrupt storage should not break the page
    pg.evaluate("localStorage.setItem('gijul.mysubs.v1','{{{not json')")
    pg.reload(wait_until="networkidle")
    pg.wait_for_selector(".item", timeout=15000)
    print("10. corrupt storage -> hint:", pg.is_visible("#favBox .pill-empty"), "items rendered ok")

    print("ERRORS:", errs if errs else "none")
    b.close()
