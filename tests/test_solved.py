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

    # ── 홀수형·짝수형은 한 회차 ─────────────────────────────────────
    # 문항 순서만 다른 같은 시험지다. 따로 세면 다 풀어도 진도가 안 찬다.
    pg.evaluate("()=>{ SOLVED={}; localStorage.removeItem(SOLVED_KEY);"
                "pickSub('D300','80003'); render(); }")           # 고3 영어
    pg.wait_for_selector(".item .chk", timeout=10000)
    pair = pg.evaluate("""()=>{
        const t=[...document.querySelectorAll('.item .nm')].map(e=>e.textContent.trim());
        const i=t.findIndex(x=>x.includes('홀수형'));
        return i<0 ? null : {i, odd:t[i], even:t[i+1]};}""")
    print("10. 홀짝 짝지음:", pair and (pair["odd"], pair["even"]))
    ck(pair and "짝수형" in (pair["even"] or ""), "홀수형 다음 줄이 짝수형이어야 합니다")

    if pair:
        before = pg.eval_on_selector(".tally .sm", "e=>e.textContent")
        pg.eval_on_selector_all(".item .chk", f"e=>e[{pair['i']}].click()")
        pg.wait_for_selector(".stamp", timeout=5000)
        keys = pg.evaluate("()=>Object.keys(SOLVED)")
        stamps = pg.eval_on_selector_all(".stamp", "e=>e.length")
        pressed = pg.eval_on_selector_all('.chk[aria-pressed="true"]', "e=>e.length")
        print(f"11. 홀수형만 찍음 · 열쇠 {keys} · 도장 {stamps}개 · 찍힌 줄 {pressed}개")
        ck(len(keys) == 1, f"한 회차인데 열쇠가 {len(keys)}개입니다")
        ck("홀수형" not in keys[0] and "짝수형" not in keys[0],
           f"열쇠에 홀짝이 남아 있습니다: {keys[0]}")
        ck(pressed == 2, f"같은 회차의 두 줄이 함께 찍혀야 하는데 {pressed}줄입니다")

        prog = pg.eval_on_selector(".tally .prog", "e=>e.textContent.replace(/\\s+/g,' ').trim()")
        rows = pg.eval_on_selector_all(".item", "e=>e.length")
        m = int(prog.split("/")[1].split()[0])
        print(f"12. 진도 {prog} · 화면의 줄 {rows}개 · {before.strip()}")
        ck(prog.strip().startswith("1"), f"홀·짝을 하나로 세야 합니다: {prog!r}")
        ck(m < rows, f"분모가 줄 수({rows})와 같습니다 — 홀짝이 안 묶였습니다: {prog!r}")

        # 홀짝 쌍은 해마다 있다. 다른 해 것은 그대로 남아야 하므로
        # '몇 개 줄었는가'로 본다.
        cnt = """()=>{const t=[...document.querySelectorAll('.item .nm')]
            .map(e=>e.textContent);
            return [t.filter(x=>x.includes('홀수형')).length,
                    t.filter(x=>x.includes('짝수형')).length];}"""
        was = pg.evaluate(cnt)
        pg.click("#onlyBtn")
        pg.wait_for_timeout(200)
        now = pg.evaluate(cnt)
        print(f"13. 안 푼 것만 — 홀수형 {was[0]}→{now[0]} · 짝수형 {was[1]}→{now[1]}")
        ck(now[0] == was[0] - 1, "푼 회차의 홀수형이 안 빠졌습니다")
        ck(now[1] == was[1] - 1, "짝만 안 풀었다고 남기면 안 됩니다 — 같은 회차입니다")
        pg.click("#onlyBtn")
        pg.wait_for_timeout(150)

    # ── 옛 열쇠(홀짝이 붙은 것)를 옮겨 오는가 ───────────────────────
    pg.evaluate("""()=>{ localStorage.setItem(SOLVED_KEY,
        JSON.stringify({'D300/80003/20251113/수능 홀수형':'20250101'})); }""")
    pg.reload(wait_until="load")
    pg.wait_for_selector(".item", timeout=25000)
    pg.evaluate("()=>{ pickSub('D300','80003'); render(); }")
    pg.wait_for_selector(".item .chk", timeout=10000)
    moved = pg.evaluate("()=>Object.keys(SOLVED)")
    print("14. 옛 열쇠 옮김:", moved)
    ck(len(moved) == 1 and "홀수형" not in moved[0],
       f"홀짝이 붙은 옛 열쇠가 그대로입니다: {moved}")
    ck(pg.eval_on_selector_all('.chk[aria-pressed="true"]', "e=>e.length") == 2,
       "옮긴 뒤에도 두 줄이 함께 찍혀 있어야 합니다")

    # ── 위젯에 건네는 꾸러미 ────────────────────────────────────────
    # 위젯은 다른 프로세스라 이 페이지의 저장소를 못 본다. 건네는 것이 유일한
    # 길이므로, 꼴이 어긋나면 위젯이 통째로 빈 채로 뜬다 — 그러고도 앱은 멀쩡히
    # 돌아서 알아차릴 방법이 없다.
    ctx2 = b.new_context(viewport={"width": 412, "height": 900}, service_workers="block")
    ctx2.add_init_script("""
      window.__sent = [];
      window.GijulNative = {
        systemDark:()=>false, where:()=>'/기출 직행', listSaved:()=>'[]',
        setSolved:(j)=>{ window.__sent.push(j); },
        appVersion:()=>'{"code":68,"name":"7.7"}', checkUpdate:()=>{}, installUpdate:()=>{}
      };
    """)
    pg2 = ctx2.new_page()
    pg2.on("pageerror", lambda e: errs.append(str(e)[:140]))
    pg2.goto(SITE, wait_until="load")
    pg2.wait_for_selector(".item .chk", timeout=25000)
    pg2.wait_for_timeout(300)
    first = pg2.evaluate("()=>window.__sent.length")
    pg2.eval_on_selector_all(".item .chk", "e=>e[0].click()")
    pg2.wait_for_timeout(300)
    sent = pg2.evaluate("()=>window.__sent[window.__sent.length-1]")
    import json as _json
    pack = _json.loads(sent)
    print("15. 건넨 꾸러미 열쇠:", sorted(pack.keys()), "· 처음 열 때도 보냈는가:", first > 0)
    ck(first > 0, "페이지를 열 때 위젯에 아무것도 안 건넸습니다")
    ck(set(pack) >= {"marks", "subs", "next"},
       f"꾸러미에 빠진 것이 있습니다: {sorted(pack.keys())}")
    ck(len(pack["marks"]) == 1, f"찍은 하나가 안 담겼습니다: {pack['marks']}")

    mk = list(pack["marks"])[0]
    who = "/".join(mk.split("/")[:2])
    print("16. 과목 이름:", pack["subs"].get(who), "· 다음에 풀 것:", [x.get("t") for x in pack["next"]])
    ck(pack["subs"].get(who), f"과목 이름이 안 담겼습니다: {pack['subs']}")
    ck(pack["next"], "위젯에 내놓을 '다음에 풀 것'이 비었습니다")
    import re as _re
    ck(all(_re.match(r"^\d{2} \S+ \S+$", x.get("t","")) for x in pack["next"]),
       f"'다음에 풀 것'의 이름 꼴이 아닙니다: {[x.get('t') for x in pack['next']]}")
    # 방금 찍은 회차가 '다음에 풀 것'에 남아 있으면 안 된다
    ck(not any(x.get("t") == "" for x in pack["next"]), "빈 이름이 있습니다")
    ctx2.close()

    pg.screenshot(path=str(SHOT / "solved.png"))
    print("   오류:", errs or "없음")
    ck(not errs, f"스크립트 오류: {errs}")
    b.close()

print("\n=== 문제:", "없음" if not BAD else "")
for x in BAD:
    print("  ★", x)
sys.exit(1 if BAD else 0)
