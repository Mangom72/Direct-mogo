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

    print("WebKit gzip:", supported, "| 목록:", before, "→", after,
          "| 저장소:", kept, "| 오류:", errors or "없음")
    browser.close()

if not supported or before <= 0 or after <= 0 or kept != "ok" or errors:
    print("★ WebKit 기본 기능이 동작하지 않습니다")
    raise SystemExit(1)
