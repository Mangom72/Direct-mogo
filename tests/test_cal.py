"""푼 날 달력 — 이름을 제대로 줄이는가, 칸에 안 들어가는 것을 접는가.

세 군데가 어긋나기 쉽다.

1. **줄인 이름의 연도.** 목록 화면은 시행 연도로 적고(`2025.03.27`) 줄인 이름은
   학년도로 적는다(`26 3모`). 학생이 그렇게 부르기 때문인데, 한쪽 규칙을 다른
   쪽에 잘못 옮기면 한 해 어긋난 회차를 가리키게 된다. 그러고도 화면은 멀쩡해
   보인다 — 26이 25가 되어도 그럴듯하다.

2. **+n.** 칸 높이를 내용이 정하게 두면 넘칠 일이 없어져 접기가 통째로 죽는다.
   실제로 그렇게 한 번 죽어 있었다.

3. **자리가 넉넉한 곳.** 오른쪽 칸(폰은 아래 목록)은 줄이지 않는다. 거기까지
   줄이면 굳이 두 표기를 갖는 뜻이 없다.
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

# 여러 날에 걸쳐, 그리고 하루에 여러 개 찍어 둔 것처럼 만든다
SEED = """()=>{
  const now = new Date(), keys = [];
  document.querySelectorAll('.item .chk').forEach(c=>keys.push(c.dataset.k));
  SOLVED = {};
  keys.slice(0, 20).forEach((k,i)=>{
    const d = new Date(now); d.setDate(d.getDate() - (i < 9 ? 0 : (i % 9)));
    SOLVED[k] = d.getFullYear()+String(d.getMonth()+1).padStart(2,'0')+String(d.getDate()).padStart(2,'0');
  });
  saveSolved(); render();
}"""

def open_cal(pg):
    pg.wait_for_selector("#progBtn", timeout=10000)
    pg.click("#progBtn")
    pg.wait_for_selector("#cal:not([hidden])", timeout=5000)
    pg.wait_for_timeout(250)

with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path=CHROME)
    errs = []

    # ── 태블릿 ──────────────────────────────────────────────────────
    ctx = b.new_context(viewport={"width": 1280, "height": 720}, service_workers="block")
    pg = ctx.new_page()
    pg.on("pageerror", lambda e: errs.append(str(e)[:160]))
    pg.goto(SITE, wait_until="load")
    pg.wait_for_selector(".item .chk", timeout=25000)

    ck(pg.eval_on_selector_all("#progBtn", "e=>e.length") == 0,
       "아무것도 안 찍었는데 진도 단추가 있습니다")
    pg.evaluate(SEED)
    open_cal(pg)
    print("1. 진도를 눌러 달력이 열림")

    chips = pg.eval_on_selector_all(".cal .chip", "e=>e.map(x=>x.textContent.trim())")
    print("2. 칸 이름표(태블릿) 앞 6개:", chips[:6])
    ck(chips, "달력에 이름표가 하나도 없습니다")
    # 줄인 이름은 '<두 자리> <회차> <과목>' 꼴
    import re
    shape = re.compile(r"^\d{2} \S+ \S+$")
    bad = [c for c in chips if not shape.match(c)]
    ck(not bad, f"줄인 이름 꼴이 아닙니다: {bad[:3]}")
    ck(not any("학평" in c or "모평" in c for c in chips), "칸에 '학평·모평'이 그대로 있습니다")
    ck(not any("홀수형" in c or "짝수형" in c for c in chips), "칸에 홀짝이 남아 있습니다")

    # 평가원은 '평', 교육청은 '모'. 그리고 앞 두 자리는 둘 다 학년도.
    pairs = pg.evaluate("""()=>{
      const out = [];
      document.querySelectorAll('.cal .cell[data-k]').forEach(c=>{
        c.querySelectorAll('.chip').forEach(p=>out.push([p.className, p.textContent.trim()]));
      });
      return out;}""")
    gov = [t for cls, t in pairs if "edu" not in cls]
    edu = [t for cls, t in pairs if "edu" in cls]
    print("3. 평가원:", gov[:3], "· 교육청:", edu[:3])
    ck(all(("평" in t.split()[1] or "수능" in t.split()[1]) for t in gov),
       f"평가원 회차는 '수능' 또는 'N평'이어야 합니다: {gov[:3]}")
    ck(all("모" in t.split()[1] for t in edu),
       f"교육청 회차는 'N모'여야 합니다: {edu[:3]}")

    # 학년도인가 — 시행 연도 + 1
    got = pg.evaluate("""()=>{
      const k = Object.keys(SOLVED)[0], p = k.split('/');
      const meta = SUBINDEX[p[0]+'/'+p[1]];
      return { yy: shortName(p[2].slice(0,4), p.slice(3).join('/'), meta.name),
               year: p[2].slice(0,4) };}""")
    print("4. 줄인 이름:", got["yy"], "· 시행 연도:", got["year"])
    ck(got["yy"].startswith(str(int(got["year"]) + 1)[2:]),
       f"줄인 이름의 연도가 학년도가 아닙니다: {got['yy']} (시행 {got['year']})")

    # 오른쪽 칸은 줄이지 않는다
    right = pg.eval_on_selector_all(".cal-right .nm", "e=>e.map(x=>x.textContent.trim())")
    print("5. 오른쪽 칸:", right[:2])
    ck(right, "고른 날의 목록이 비어 있습니다")
    ck(any("학년도" in r or "년" in r for r in right), f"오른쪽이 줄여 적혀 있습니다: {right[:2]}")

    # 달 넘기기
    m0 = pg.eval_on_selector("#calM", "e=>e.textContent")
    pg.click("#calPrev"); pg.wait_for_timeout(150)
    m1 = pg.eval_on_selector("#calM", "e=>e.textContent")
    pg.click("#calToday"); pg.wait_for_timeout(150)
    m2 = pg.eval_on_selector("#calM", "e=>e.textContent")
    print(f"6. 달 넘기기: {m0} → {m1} → {m2}")
    ck(m0 != m1, "이전 달로 안 넘어갑니다")
    ck(m0 == m2, "'오늘'이 이번 달로 안 돌아옵니다")

    # 목록의 회차를 누르면 그 과목으로 간다
    pg.eval_on_selector_all(".dlist button", "e=>e[0].click()")
    pg.wait_for_timeout(300)
    print("7. 회차를 눌러 이동 · 달력 닫힘:", pg.eval_on_selector("#cal", "e=>e.hidden"))
    ck(pg.eval_on_selector("#cal", "e=>e.hidden"), "회차를 눌렀는데 달력이 안 닫힙니다")

    # 뒤로가기로도 닫힌다
    open_cal(pg)
    closed = pg.evaluate("()=>window.gijulBack()")
    print("8. 뒤로가기가 달력을 닫는가:", closed, "· hidden", pg.eval_on_selector("#cal", "e=>e.hidden"))
    ck(closed and pg.eval_on_selector("#cal", "e=>e.hidden"), "뒤로가기가 달력을 안 닫습니다")

    pg.screenshot(path=str(SHOT / "cal-tab.png"))
    ctx.close()

    # ── 폰 ──────────────────────────────────────────────────────────
    ctx = b.new_context(viewport={"width": 412, "height": 900}, service_workers="block")
    pg = ctx.new_page()
    pg.on("pageerror", lambda e: errs.append(str(e)[:160]))
    pg.goto(SITE, wait_until="load")
    pg.wait_for_selector(".item .chk", timeout=25000)
    pg.evaluate(SEED)
    open_cal(pg)

    chips = pg.eval_on_selector_all(".cal .chip", "e=>e.map(x=>x.textContent.trim())")
    more = pg.eval_on_selector_all(".cal .more", "e=>e.map(x=>x.textContent)")
    print("9. 칸 이름표(폰):", chips[:4], "· 접힘:", more)
    ck(chips and all(" " not in c for c in chips),
       f"폰 칸에는 과목만 적어야 합니다: {chips[:3]}")
    ck(more, "하루에 아홉을 찍었는데 +n 이 없습니다 — 칸이 안 넘칩니다")
    ck(all(x.startswith("+") for x in more), f"접힘 표시가 이상합니다: {more}")

    below = pg.eval_on_selector_all(".cal-right .nm", "e=>e.map(x=>x.textContent.trim())")
    print("10. 아래 목록:", below[:2])
    ck(any("년" in r for r in below), f"아래 목록이 줄여 적혀 있습니다: {below[:2]}")

    pg.screenshot(path=str(SHOT / "cal-ph.png"))
    print("   오류:", errs or "없음")
    ck(not errs, f"스크립트 오류: {errs}")
    ctx.close()
    b.close()

print("\n=== 문제:", "없음" if not BAD else "")
for x in BAD:
    print("  ★", x)
sys.exit(1 if BAD else 0)
