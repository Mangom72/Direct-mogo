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

BAD = []                      # 이것이 차면 시험이 진다

# 통 이름에 붙는 판. sw.js에서 읽는다 — 여기에 적어 두면 판을 올릴 때마다
# 시험이 같이 깨지고, 그때 고치는 것은 시험이지 코드가 아니게 된다.
NOW = re.search(r'VERSION = "(v\d+)"', (ROOT / "sw.js").read_text(encoding="utf-8")).group(1)
NEXT = "v" + str(int(NOW[1:]) + 1)

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
        print("   오프라인 필터 동작:", pg.text_content(".tally .big"),
              "| 연도:", pg.input_value("#yr"))
        print("   내 과목/보내기 버튼 살아있음:",
              pg.is_visible("#favToggle"), pg.eval_on_selector_all(".send", "e=>e.length") > 0)
        ctx.set_offline(False)

        # ---- 3. 자료 파일 캐시 + 40개 상한
        pg.goto(URL, wait_until="load")
        pg.wait_for_selector(".item", timeout=20000)
        n = pg.evaluate("""async () => {
            for (let i = 0; i < 45; i++)
                await fetch('https://wdown.ebsi.co.kr/W61001/01exam/x/go3/f' + i + '.pdf');
            const c = await caches.open('gijul-files-%s');
            return (await c.keys()).length;
        }""" % NOW)
        print("3. 자료 45개 요청 -> 캐시 보관:", n, "| 상한 지킴:", n <= 40)
        first = pg.evaluate("""async () => {
            const c = await caches.open('gijul-files-%s');
            return (await c.keys())[0].url.split('/').pop();
        }""" % NOW)
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

        # ---- 5b. 문서가 그대로여도 글꼴만 바뀌면 다시 받는가
        #
        # 글꼴은 자라는 파일이다 — 페이지에 새 글자가 늘면 부분집합이 다시
        # 만들어져 같은 이름으로 나간다. 셸은 캐시 우선이라 다시 묻지 않으므로,
        # 여기서 안 챙기면 기기에 처음 깔릴 때의 글꼴이 영영 남고 그 뒤에 늘어난
        # 글자만 시스템 글꼴로 떨어진다. 한 제목 안에서 글꼴이 갈린다.
        f = TMP / "fonts" / "SongMyung-400.woff2"
        f.write_bytes(f.read_bytes() + b"NEWGLYPHS")
        marker = TMP / "fonts" / "version.json"
        marker.write_text('{"sha256":"font-only-change"}\n', encoding="utf-8")
        want = len(f.read_bytes())
        pg.goto(URL, wait_until="load")
        got = 0
        try:
            pg.wait_for_function("""(n) => caches.open('gijul-shell-%s')
                .then(c => c.match(new URL('./fonts/SongMyung-400.woff2', location).href))
                .then(r => r ? r.arrayBuffer() : null)
                .then(b => !!b && b.byteLength === n)""" % NOW, arg=want, timeout=20000)
            got = want
        except Exception as ex:
            got = pg.evaluate("""async () => {
                const c = await caches.open('gijul-shell-%s');
                const r = await c.match(new URL('./fonts/SongMyung-400.woff2', location).href);
                return r ? (await r.arrayBuffer()).byteLength : -1;
            }""" % NOW)
        print("5b. 글꼴만 바뀌어도 다시 받음:", got == want, f"(캐시 {got} / 서버 {want})")
        if got != want:
            BAD.append("문서는 그대로이고 글꼴만 바뀌었을 때 캐시에 옛것이 남았습니다")

        # ---- 6. 버전 올리면 옛 캐시 정리
        sw = TMP / "sw.js"
        sw.write_text(sw.read_text(encoding="utf-8")
                      .replace('VERSION = "%s"' % NOW, 'VERSION = "%s"' % NEXT),
                      encoding="utf-8")
        pg.goto(URL, wait_until="load")
        pg.wait_for_selector(".item", timeout=20000)
        pg.evaluate("navigator.serviceWorker.getRegistration().then(r => r && r.update())")
        cleaned = True
        try:
            pg.wait_for_function(
                "() => caches.keys().then(k => k.some(n=>n.includes('-%s')) && !k.some(n=>n.includes('-%s')))"
                % (NEXT, NOW), timeout=20000)
        except Exception:
            cleaned = False
        # 다음 실행에서 잔여물이 사라지는지 (교체된 워커가 되살린 통)
        pg.goto(URL, wait_until="load")
        pg.wait_for_selector(".item", timeout=20000)
        try:
            pg.wait_for_function(
                "() => caches.keys().then(k => !k.some(n=>n.includes('-%s')))" % NOW,
                timeout=20000)
        except Exception:
            pass
        after = caches(pg)
        print("   정리 완료 대기:", cleaned)
        print("6.", NEXT, "활성화 후 캐시:", list(after.keys()))
        print("  ", NOW, "잔존:", [k for k in after if "-" + NOW in k] or "없음")

        print("ERRORS:", errs or "none")
        b.close()
finally:
    _own.__exit__()

if BAD:
    print("\n=== 문제:")
    for x in BAD:
        print("  ★", x)
    sys.exit(1)
