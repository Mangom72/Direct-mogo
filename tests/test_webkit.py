"""WebKit 최소 기능 — iPhone 안내를 UA 흉내만으로 시험하지 않는다."""
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from harness import site  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

_srv, SITE = site()
required = os.environ.get("GIJUL_REQUIRE_WEBKIT") == "1"

with sync_playwright() as pw:
    try:
        browser = pw.webkit.launch()
    except Exception as exc:
        if required:
            raise
        print("WebKit 실행 환경이 없어 로컬에서는 건너뜁니다:", str(exc).splitlines()[0])
        raise SystemExit(0)

    page = browser.new_page(viewport={"width": 390, "height": 844})
    errors = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    page.goto(SITE, wait_until="load")
    page.wait_for_selector(".item", timeout=20000)

    supported = page.evaluate("'DecompressionStream' in window")
    before = page.locator(".item").count()
    page.select_option("#grp", label="과학탐구")
    page.select_option("#sub", label="생명과학Ⅰ")
    page.wait_for_timeout(100)
    after = page.locator(".item").count()
    page.evaluate("localStorage.setItem('gijul.webkit.smoke','ok')")
    page.reload(wait_until="load")
    kept = page.evaluate("localStorage.getItem('gijul.webkit.smoke')")

    page.locator(".item .record").first.click()
    page.click("#recordOmr"); page.click("#omrManual")
    assert page.locator(".omr-bubble").count() == 100
    assert "0/20" in page.locator(".omr-progress").inner_text()
    page.locator('.omr-bubble[data-question="1"][data-value="3"]').click()
    assert "1/20" in page.locator(".omr-progress").inner_text()
    page.set_viewport_size({"width":1024,"height":768})
    page.wait_for_function("()=>document.querySelector('.omr-sheet').classList.contains('omr-full-input')")
    sheet=page.locator('.omr-sheet').bounding_box();frame=page.locator('.omr-sheet-scroll').bounding_box()
    assert sheet['width']<=frame['width'] and sheet['height']<=frame['height']
    page.locator('.omr-bubble[data-question="20"][data-value="4"]').click()
    assert page.locator('.omr-bubble[data-question="20"][data-value="4"]').get_attribute('aria-pressed')=='true'
    page.set_viewport_size({"width":390,"height":844})
    page.wait_for_function("()=>!document.querySelector('.omr-sheet').classList.contains('omr-full-input')")
    page.click("#omrMode"); page.click("#omrPhoto")
    import base64
    # Actual unmodified source exercises WebKit's PNG header, resize and canvas paths.
    raw = page.evaluate("""async()=>{const r=await fetch(GijulOmrForms.forms.inquiry.image),b=await createImageBitmap(await r.blob()),c=document.createElement('canvas');c.width=b.width;c.height=b.height;c.getContext('2d').drawImage(b,0,0);b.close();return c.toDataURL('image/png').split(',')[1];}""")
    page.set_input_files("#omrFile", {"name":"specimen.png","mimeType":"image/png","buffer":base64.b64decode(raw)})
    page.wait_for_selector("#omrFormCheck")
    assert page.locator(".omr-actions button").is_disabled()
    page.locator(".omr-close").click()
    assert page.evaluate("document.body.style.overflow") == ""

    page.evaluate("GijulOMR.open({grade:'D300',subjectId:'140120',subject:'미적분',group:'수학',date:'20260902',title:'9월 모평(평가원)'},{demo:true})")
    page.click('#omrManual'); page.select_option('#omrQuestion','16')
    page.wait_for_function("()=>document.querySelector('.omr-sheet img').naturalWidth===3420")
    page.locator('.omr-digit[data-question="16"][data-digit="2"][data-value="0"]').click()
    assert '16번 · 0' in page.locator('#omrCurrent').inner_text()
    page.locator('.omr-digit[data-question="16"][data-digit="0"][data-value="1"]').click()
    assert '미완성' in page.locator('#omrCurrent').inner_text()
    page.locator('.omr-digit[data-question="16"][data-digit="1"][data-value="0"]').click()
    assert '16번 · 100' in page.locator('#omrCurrent').inner_text()
    page.click('#omrKey')
    assert sum(map(int,page.locator('#omrKeyPoints').input_value().split()))==100
    page.locator('.omr-close').click()

    print("WebKit gzip:", supported, "| 목록:", before, "→", after,
          "| 저장소:", kept, "| 오류:", errors or "없음")
    browser.close()

if not supported or before <= 0 or after <= 0 or kept != "ok" or errors:
    print("★ WebKit 기본 기능이 동작하지 않습니다")
    raise SystemExit(1)
