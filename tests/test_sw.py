"""서비스 워커 — 미리 담기, 오프라인 동작, 캐시 상한, 셸 갱신 감지."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from harness import CHROME, ROOT, SHOT, site, Serve
_srv, SITE = site()
import re, shutil, subprocess, time, pathlib
from playwright.sync_api import sync_playwright


# 돌아가는 도중에 index.html을 고쳐야 하므로 저장소가 아니라 사본을 내준다.
_own = Serve(copy=True).__enter__()
TMP, URL = _own.dir, _own.url

PDF = b"%PDF-1.4\n" + b"0" * 500

def caches(pg):
    return pg.evaluate("""async () => {
        const out = {};
        for (const n of await caches.keys())
            out[n] = (await (await caches.open(n)).keys()).length;
        return out;
    }""")

try:
    with sync_playwright() as pw:
        b = pw.chromium.launch(executable_path=CHROME)
        ctx = b.new_context(viewport={"width": 412, "height": 900})
        ctx.route(re.compile(r"fonts\.(googleapis|gstatic)\.com"), lambda r: r.abort())
        ctx.route(re.compile(r"wdown\.ebsi\.co\.kr"), lambda r: r.fulfill(
            status=200, body=PDF,
            headers={"Content-Type": "application/pdf", "Access-Control-Allow-Origin": "*"}))
        pg = ctx.new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))

        # ---- 1. registers and precaches
        pg.goto(URL, wait_until="load")
        pg.wait_for_selector(".item", timeout=20000)
        pg.wait_for_function("() => navigator.serviceWorker.controller !== null", timeout=20000)
        print("1. SW 등록:", pg.evaluate("!!navigator.serviceWorker.controller"),
              "| 스코프:", pg.evaluate("navigator.serviceWorker.controller.scriptURL").split("/")[-1])
        pg.wait_for_function("() => caches.keys().then(k => k.some(n => n.startsWith('gijul-shell')))",
                             timeout=15000)
        print("   캐시:", caches(pg))

        # ---- 2. offline: app still works end to end
        ctx.set_offline(True)
        pg.reload(wait_until="domcontentloaded")
        pg.wait_for_selector(".item", timeout=20000)
        print("2. 오프라인 새로고침 — 표제:", pg.text_content(".tally .big"),
              "| 항목 수:", pg.eval_on_selector_all(".item", "e=>e.length"))
        pg.select_option("#grp", label="과학탐구")
        pg.select_option("#sub", label="지구과학Ⅰ")
        pg.select_option("#yr", index=2)
        pg.wait_for_timeout(150)
        print("   오프라인 필터 동작:", pg.text_content(".tally .big"), "|",
              pg.text_content(".tally .sm"))
        print("   내 과목/보내기 버튼 살아있음:",
              pg.is_visible("#favToggle"), pg.eval_on_selector_all(".send", "e=>e.length") > 0)
        ctx.set_offline(False)

        # ---- 3. 자료 파일 캐시 + 40개 상한
        pg.goto(URL, wait_until="load")
        pg.wait_for_selector(".item", timeout=20000)
        n = pg.evaluate("""async () => {
            for (let i = 0; i < 45; i++)
                await fetch('https://wdown.ebsi.co.kr/W61001/01exam/x/go3/f' + i + '.pdf');
            const c = await caches.open('gijul-files-v1');
            return (await c.keys()).length;
        }""")
        print("3. 자료 45개 요청 -> 캐시 보관:", n, "| 상한 지킴:", n <= 40)
        first = pg.evaluate("""async () => {
            const c = await caches.open('gijul-files-v1');
            return (await c.keys())[0].url.split('/').pop();
        }""")
        print("   가장 오래된 것부터 정리됨 (남은 첫 항목):", first)

        # ---- 4. 오프라인에서 캐시된 자료 재사용
        ctx.set_offline(True)
        ok = pg.evaluate("""async () => {
            try { const r = await fetch('https://wdown.ebsi.co.kr/W61001/01exam/x/go3/f44.pdf');
                  return r.ok && (await r.blob()).size; } catch(e) { return 'FAIL: ' + e.message; }
        }""")
        print("4. 오프라인 캐시된 PDF 재사용:", ok, "bytes")
        ctx.set_offline(False)

        # ---- 5. 셸 변경 -> 새 자료 알림
        p = TMP / "index.html"
        p.write_text(p.read_text(encoding="utf-8").replace("'06~", "'07~"), encoding="utf-8")
        pg.goto(URL, wait_until="load")
        try:
            pg.wait_for_selector("#notice:not([hidden])", timeout=15000)
            print("5. 셸 변경 감지 — 알림:", pg.text_content("#noticeText"),
                  "| 버튼:", pg.text_content("#noticeYes"))
            pg.click("#noticeYes")
            pg.wait_for_selector(".item", timeout=20000)
            print("   새로고침 후 반영:", pg.eval_on_selector(".mast-side .n:not(#cntPaper)",
                                                       "e=>e.textContent"))
        except Exception as ex:
            print("5. 알림 실패:", str(ex)[:90])

        # ---- 6. 버전 올리면 옛 캐시 정리
        sw = TMP / "sw.js"
        sw.write_text(sw.read_text(encoding="utf-8").replace('VERSION = "v1"', 'VERSION = "v2"'),
                      encoding="utf-8")
        pg.goto(URL, wait_until="load")
        pg.wait_for_selector(".item", timeout=20000)
        pg.evaluate("navigator.serviceWorker.getRegistration().then(r => r && r.update())")
        cleaned = True
        try:
            pg.wait_for_function(
                "() => caches.keys().then(k => k.some(n=>n.includes('-v2')) && !k.some(n=>n.includes('-v1')))",
                timeout=20000)
        except Exception:
            cleaned = False
        # 다음 실행에서 잔여물이 사라지는지 (교체된 워커가 되살린 통)
        pg.goto(URL, wait_until="load")
        pg.wait_for_selector(".item", timeout=20000)
        try:
            pg.wait_for_function("() => caches.keys().then(k => !k.some(n=>n.includes('-v1')))",
                                 timeout=20000)
        except Exception:
            pass
        after = caches(pg)
        print("   정리 완료 대기:", cleaned)
        print("6. v2 활성화 후 캐시:", list(after.keys()))
        print("   v1 잔존:", [k for k in after if "-v1" in k] or "없음")

        print("ERRORS:", errs or "none")
        b.close()
finally:
    _own.__exit__()
