"""시험 시간 — 잰 것이 회차에 남는가, 옛 앱에서도 자료가 열리는가.

<h3>왜 부호로 안 적는가</h3>
재는 동안에는 `+`가 <b>넘겼다</b>는 뜻이다. 그런데 끝난 뒤 남기는 값은
(고사 시간 − 소요 시간)이라 양수가 <b>남겼다</b>는 뜻이 된다. 같은 기호가
반대를 가리키게 되므로 말로 적는다 — '8분 남김' · '8분 넘김'.

<h3>옛 앱</h3>
회차 열쇠를 받는 창구(openPaperAt)는 새 앱에만 있다. 페이지는 앱보다 먼저
갱신되므로, 그 창구가 없다고 자료가 안 열리면 갱신한 사람 전부가 그날
문제지를 못 연다. 예전 길이 그대로 살아 있어야 한다.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from harness import CHROME, SHOT, site
_srv, SITE = site()
from playwright.sync_api import sync_playwright

BAD = []
def ck(cond, msg):
    if not cond:
        BAD.append(msg)

FAKE = """
window.__timings = [];
window.__opened = null;
window.GijulNative = { systemDark: () => false, setSolved: () => {},
  takeTimings: () => { const t = JSON.stringify(window.__timings); window.__timings = []; return t; },
  openPaper:   () => { window.__opened = {via:"openPaper"}; },
  openPaperIn: () => { window.__opened = {via:"openPaperIn"}; },
  openPaperAt: (u,n,g,s,k) => { window.__opened = {via:"openPaperAt", g:g, s:s, k:k}; },
};
"""

with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path=CHROME)
    ctx = b.new_context(viewport={"width": 412, "height": 900}, service_workers="block")
    ctx.add_init_script(FAKE)
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)[:180]))
    pg.goto(SITE, wait_until="load")
    pg.wait_for_selector(".item .chk", timeout=25000)
    key = pg.eval_on_selector(".item .chk", "e=>e.dataset.k")

    def feed(spent, limit):
        pg.evaluate("""a=>{ window.__timings=[{k:a[0], spent:a[1], limit:a[2]}];
                            takeTimings(); render(); }""", [key, spent, limit])
        pg.wait_for_timeout(180)
        return pg.eval_on_selector_all(".took", "e=>e.map(x=>x.textContent)")

    # ---- 1. 남긴 것과 넘긴 것 ----
    got = feed(92 * 60, 100 * 60)
    print("1. 92분 / 100분 →", got[:1])
    ck(got and got[0] == "92분 · 8분 남김", f"남긴 것을 잘못 적습니다: {got[:1]}")

    got = feed(108 * 60, 100 * 60)
    print("   108분 / 100분 →", got[:1])
    ck(got and got[0] == "108분 · 8분 넘김", f"넘긴 것을 잘못 적습니다: {got[:1]}")

    got = feed(100 * 60, 100 * 60)
    print("   100분 / 100분 →", got[:1])
    ck(got and got[0] == "100분 · 딱 맞춤", f"딱 맞춘 것을 잘못 적습니다: {got[:1]}")

    got = feed(75 * 60, 0)          # 시간을 안 정하고 잰 경우
    print("   시간을 안 정했을 때 →", got[:1])
    ck(got and got[0] == "75분", f"시간을 안 정했을 때가 이상합니다: {got[:1]}")

    # ---- 2. 시간을 쟀으면 푼 것이다 ----
    #
    # 재고 나서 ✓를 또 누르게 하는 것은 같은 말을 두 번 시키는 일이다.
    pg.evaluate("()=>{ SOLVED={}; saveSolved(); render(); }")
    feed(92 * 60, 100 * 60)
    marked = pg.evaluate("k=>!!SOLVED[k]", key)
    print("2. 시간을 재면 표시도 찍히는가:", marked)
    ck(marked, "시간을 쟀는데 푼 회차로 안 찍힙니다")

    # ---- 3. 이상한 것은 안 받는다 ----
    before = pg.evaluate("()=>Object.keys(TIMES).length")
    pg.evaluate("""()=>{ window.__timings=[
        {k:"열쇠가아님", spent:600, limit:600},
        {k:"D300/158/20250101/수능", spent:0, limit:600},
        {k:null, spent:600, limit:600},
        null ]; takeTimings(); render(); }""")
    pg.wait_for_timeout(150)
    after = pg.evaluate("()=>Object.keys(TIMES).length")
    print(f"3. 망가진 줄 넷 → 늘어난 것 {after - before}개")
    ck(after == before, f"이상한 것을 받아들였습니다: {after - before}개")

    # ---- 4. 백업에 함께 담기고 돌아온다 ----
    feed(92 * 60, 100 * 60)
    b64 = pg.evaluate("()=>JSON.stringify(makeBackup())")
    has = pg.evaluate("t=>{const o=JSON.parse(t); return o.times && Object.keys(o.times).length;}", b64)
    print("4. 백업에 담긴 잰 시간:", has, "개")
    ck(has, "백업에 잰 시간이 안 담깁니다")

    pg.evaluate("()=>{ SOLVED={}; TIMES={}; saveSolved(); saveTimes(); render(); }")
    pg.evaluate("t=>{ const b=readBackup(t); applyBackup(b, 'merge'); }", b64)
    pg.wait_for_timeout(200)
    back = pg.eval_on_selector_all(".took", "e=>e.map(x=>x.textContent)")
    print("   되살린 뒤:", back[:1])
    ck(back and back[0] == "92분 · 8분 남김", f"백업에서 돌아오지 않습니다: {back[:1]}")

    # 표시 없이 시간만 있는 것은 안 받는다 — 화면에 나타날 자리가 없다
    orphan = pg.evaluate("""()=>{ const b = readBackup(JSON.stringify(
        { v:1, subs:[], solved:{}, times:{"D300/158/20250101/수능":{spent:600,limit:600}} }));
        return Object.keys(b.times).length; }""")
    print("   표시 없는 시간:", orphan, "개 (0이어야 맞음)")
    ck(orphan == 0, "표시가 없는데 시간만 들어왔습니다")

    # ---- 5. 옛 앱에서도 자료가 열린다 ----
    pg.eval_on_selector_all(".acts a.q", "e=>e[0].click()")
    pg.wait_for_timeout(200)
    now = pg.evaluate("()=>window.__opened")
    print("5. 새 앱:", now)
    ck(now and now["via"] == "openPaperAt", f"열쇠를 안 넘깁니다: {now}")
    ck(now and now.get("k") and now["k"].count("/") >= 3, f"열쇠 꼴이 아닙니다: {now}")

    for drop, want in (("openPaperAt", "openPaperIn"), ("openPaperIn", "openPaper")):
        pg.evaluate("d=>{ delete GijulNative[d]; window.__opened=null; }", drop)
        pg.eval_on_selector_all(".acts a.q", "e=>e[0].click()")
        pg.wait_for_timeout(200)
        got = pg.evaluate("()=>window.__opened")
        print(f"   {drop} 없는 앱 →", got)
        ck(got and got["via"] == want, f"{drop} 가 없으면 {want} 로 가야 합니다: {got}")

    pg.screenshot(path=str(pathlib.Path(SHOT) / "timer.png"))
    print("   오류:", errs or "없음")
    ck(not errs, f"스크립트 오류: {errs}")
    ctx.close()
    b.close()

print("\n=== 문제:", "없음" if not BAD else "")
for x in BAD:
    print("  ★", x)
sys.exit(1 if BAD else 0)
