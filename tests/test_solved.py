"""푼 회차 표시 — 찍은 것이 남는가, 셈이 사실대로인가, 날짜를 고칠 수 있는가.

이 기능은 손으로 찍는 것이라 화면이 유일한 진실이다. 세 군데가 어긋나기 쉽다.

1. **회차를 가리키는 열쇠.** 같은 날 다른 과목이 시행되고, 같은 과목 같은 날에
   가형·나형이 따로 있던 해가 있다. 열쇠가 모자라면 한 회차를 찍었는데 옆
   회차까지 찍힌다 — 찍고 나서야 알게 되는 종류의 잘못이다.

2. **'안 푼 것만'을 켠 채의 셈.** 거른 뒤에 세면 늘 0 / 0 이 된다. 진도를
   보려고 켠 거르개가 진도를 지우는 셈이다.

3. **푼 날.** 참·거짓만 적어 두면 '언제 풀었더라'를 영영 잃는다. 그것이
   다시 풀 때가 됐는지를 정하는 유일한 실마리다.
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

with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path=CHROME)
    ctx = b.new_context(viewport={"width": 412, "height": 900}, service_workers="block")
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)[:140]))
    pg.goto(SITE, wait_until="load")
    pg.wait_for_selector(".item .chk", timeout=25000)

    n = pg.eval_on_selector_all(".item", "e=>e.length")
    print(f"1. 회차 {n}개 · 체크 단추 {pg.eval_on_selector_all('.chk','e=>e.length')}개")
    ck(pg.eval_on_selector_all(".chk", "e=>e.length") == n, "회차마다 체크 단추가 있어야 합니다")
    ck(pg.eval_on_selector_all(".stamp", "e=>e.length") == 0, "아무것도 안 찍었는데 도장이 있습니다")
    ck(pg.eval_on_selector_all("#onlyBtn", "e=>e.length") == 0,
       "찍은 것이 없는데 '안 푼 것만'이 떠 있습니다")

    # ── 첫 회차를 찍는다 ────────────────────────────────────────────
    pg.eval_on_selector_all(".item .chk", "e=>e[0].click()")
    pg.wait_for_selector(".item .stamp", timeout=5000)
    marked = pg.evaluate("()=>Object.keys(SOLVED).length")
    print("2. 하나 찍음 · 저장된 열쇠", marked, "· 도장",
          pg.eval_on_selector_all(".stamp", "e=>e.length"))
    ck(marked == 1, f"하나를 찍었는데 {marked}개가 적혔습니다")
    ck(pg.eval_on_selector_all(".stamp", "e=>e.length") == 1,
       "찍은 회차 하나에만 도장이 있어야 합니다")
    ck(pg.eval_on_selector_all('.chk[aria-pressed="true"]', "e=>e.length") == 1,
       "찍힌 표시가 한 줄에만 있어야 합니다")

    # 열쇠에 학년·과목·시행일·이름이 다 들어 있는가
    key = pg.evaluate("()=>Object.keys(SOLVED)[0]")
    print("   열쇠:", key)
    ck(key.count("/") >= 3, f"열쇠가 회차를 다 가리키지 못합니다: {key}")
    ck(key.startswith(pg.evaluate("()=>sel.grade+'/'+sel.sub+'/'")),
       "열쇠가 지금 과목을 가리키지 않습니다")

    # ── 새로고침해도 남는가 ─────────────────────────────────────────
    pg.reload(wait_until="load")
    pg.wait_for_selector(".item .stamp", timeout=25000)
    print("3. 새로고침 뒤 도장", pg.eval_on_selector_all(".stamp", "e=>e.length"))
    ck(pg.eval_on_selector_all(".stamp", "e=>e.length") == 1, "새로고침하니 표시가 사라졌습니다")

    # ── 셈 ──────────────────────────────────────────────────────────
    prog = pg.eval_on_selector(".tally .prog", "e=>e.textContent.replace(/\\s+/g,' ').trim()")
    print("4. 표제 진도:", prog)
    ck("1" in prog and "풂" in prog, f"표제에 진도가 안 보입니다: {prog!r}")

    # '안 푼 것만'을 켜도 셈은 사실대로여야 한다
    pg.click("#onlyBtn")
    pg.wait_for_timeout(200)
    prog2 = pg.eval_on_selector(".tally .prog", "e=>e.textContent.replace(/\\s+/g,' ').trim()")
    left = pg.eval_on_selector_all(".item", "e=>e.length")
    print(f"5. 안 푼 것만: 남은 줄 {left}개 · 진도 {prog2}")
    ck(prog2 == prog, f"거르고 나니 진도가 달라졌습니다: {prog!r} → {prog2!r}")
    ck(left == n - 1, f"한 줄만 빠져야 하는데 {n}개에서 {left}개가 됐습니다")
    ck(pg.eval_on_selector_all(".stamp", "e=>e.length") == 0,
       "'안 푼 것만'인데 푼 회차가 남아 있습니다")

    pg.click("#onlyBtn")
    pg.wait_for_timeout(200)
    ck(pg.eval_on_selector_all(".item", "e=>e.length") == n, "거르개를 껐는데 줄이 안 돌아옵니다")

    # ── 푼 날 고치기 ────────────────────────────────────────────────
    was = pg.evaluate("()=>SOLVED[Object.keys(SOLVED)[0]]")
    pg.evaluate("""()=>{const st=document.querySelector('.stamp'); editStamp(st);}""")
    pg.wait_for_selector(".stampin", timeout=5000)
    print("6. 도장 자리가 날짜 칸이 됨 · 원래 값", was)
    ck(pg.eval_on_selector(".stampin", "e=>e.value") == f"{was[:4]}-{was[4:6]}-{was[6:]}",
       "날짜 칸이 적혀 있던 날을 안 들고 옵니다")

    pg.eval_on_selector(".stampin", """e=>{ e.value='2020-03-04';
        e.dispatchEvent(new Event('change',{bubbles:true})); }""")
    pg.wait_for_selector(".stamp", timeout=5000)
    now = pg.evaluate("()=>SOLVED[Object.keys(SOLVED)[0]]")
    txt = pg.eval_on_selector(".stamp", "e=>e.textContent.trim()")
    print("7. 고친 뒤:", now, "·", txt)
    ck(now == "20200304", f"고친 날이 안 적혔습니다: {now}")
    ck("3.4" in txt, f"도장이 고친 날을 안 보여줍니다: {txt!r}")

    # ── 찍은 것을 무르기 ────────────────────────────────────────────
    pg.eval_on_selector_all(".item .chk", "e=>e[0].click()")
    pg.wait_for_timeout(250)
    rest = pg.evaluate("()=>Object.keys(SOLVED).length")
    print("8. 무른 뒤 남은 열쇠:", rest)
    ck(rest == 0, "무른 회차가 저장소에 남아 있습니다")
    ck(pg.eval_on_selector_all(".stamp", "e=>e.length") == 0, "무른 회차에 도장이 남았습니다")

    # 손으로 고친 저장소에서 오는 엉뚱한 값에 넘어가지 않아야 한다
    pg.evaluate("""()=>{ SOLVED={}; SOLVED[solvedKey('99999999','없는회차')]='아무거나';
        localStorage.setItem(SOLVED_KEY, JSON.stringify(SOLVED)); }""")
    pg.reload(wait_until="load")
    pg.wait_for_selector(".item", timeout=25000)
    print("9. 망가진 값으로 다시 열기 · 오류", errs or "없음")
    ck(pg.eval_on_selector_all(".stamp", "e=>e.length") == 0,
       "날짜가 아닌 값에 도장이 찍혔습니다")

    pg.screenshot(path=str(SHOT / "solved.png"))
    print("   오류:", errs or "없음")
    ck(not errs, f"스크립트 오류: {errs}")
    b.close()

print("\n=== 문제:", "없음" if not BAD else "")
for x in BAD:
    print("  ★", x)
sys.exit(1 if BAD else 0)
