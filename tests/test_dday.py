"""수능 D-day — 맞는 날을 세는가, 지난 뒤엔 입을 다무는가.

시행일은 평가원이 해마다 따로 공고해서 규칙으로 셀 수 없다. index.html 의
SUNEUNG 한 줄에 박아 두고 해마다 고치는데, 고치는 것을 잊는 것이 이 기능의
유일하고도 확실한 고장 방식이다. 그래서 **날이 지났으면 여기서 실패한다** —
사람이 알아차릴 자리가 여기 말고 없다.

셈은 한국 시각으로 한다. 기기 시간대를 그대로 쓰면 시차가 있는 곳에서 하루가
어긋나는데, 이 숫자를 보는 이유가 바로 그 하루다.

    python3 tests/test_dday.py --date

날짜만 본다. 브라우저도 서버도 쓰지 않아 몇 밀리초면 끝나므로, 매일 도는 자료
갱신 워크플로가 이 형태로 부른다 — 시험이 지나는 시점은 대개 아무도 코드를 밀지
않는 때라, 코드를 밀 때만 도는 시험으로는 영영 안 잡힌다.
"""
import sys, pathlib, re, datetime
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from harness import ROOT

DATE_ONLY = "--date" in sys.argv

BAD = []
def ck(cond, msg):
    if not cond:
        BAD.append(msg)

src = (ROOT / "index.html").read_text(encoding="utf-8")
m = re.search(r'const SUNEUNG = "(\d{4}-\d{2}-\d{2})"', src)
if not m:
    print("★ index.html 에서 SUNEUNG 을 찾지 못했습니다")
    sys.exit(1)
EXAM = datetime.date.fromisoformat(m.group(1))
TODAY = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).date()
left = (EXAM - TODAY).days
print(f"1. 박혀 있는 시행일 {EXAM} · 오늘(한국) {TODAY} · D-{left}")
if left < 0:
    # 여기서 끝낸다. 나머지를 돌려 봐야 지난 날짜를 셀 뿐이고, 정작 사람이
    # 읽어야 할 말이 뒤따르는 출력에 묻힌다.
    print(f"\n  ★ 시행일이 {-left}일 지났습니다 — index.html 의 SUNEUNG 을 다음 수능"
          " 날짜로 고치십시오.\n    (평가원 공고. 그때까지 화면에는 아무것도 뜨지 않습니다.)")
    sys.exit(1)

if DATE_ONLY:
    print("   (날짜만 확인했습니다)")
    sys.exit(0)

# 여기서부터는 화면을 연다. 위의 날짜 확인만 필요한 쪽(매일 도는 갱신)이
# 브라우저를 깔지 않아도 되도록, 무거운 것은 여기서 처음 불러온다.
from harness import CHROME, site                                   # noqa: E402
_srv, SITE = site()
from playwright.sync_api import sync_playwright                    # noqa: E402

def at(pw, when, tz="America/Los_Angeles"):
    """기기 시계를 그 순간으로, 시간대는 일부러 한국 밖으로 두고 연다."""
    b = pw.chromium.launch(executable_path=CHROME)
    ctx = b.new_context(viewport={"width": 412, "height": 800},
                        service_workers="block", timezone_id=tz)
    pg = ctx.new_page()
    pg.add_init_script(f"""
      const F = new Date('{when}').getTime();
      const D = Date; Date = class extends D {{
        constructor(...a){{ super(...(a.length ? a : [F])); }}
        static now(){{ return F; }} }};
      Date.parse = D.parse;""")
    pg.goto(SITE, wait_until="load")
    pg.wait_for_selector(".item", timeout=25000)
    return b, pg

def shown(pg):
    return pg.evaluate("()=>{const e=document.getElementById('dday');"
                       "return e && !e.hidden ? e.textContent : null;}")

with sync_playwright() as pw:
    # 시행일 100일 전 — 한국은 낮, 기기 시간대는 미국
    d100 = (EXAM - datetime.timedelta(days=100)).isoformat()
    b, pg = at(pw, d100 + "T02:00:00Z")            # 한국 11:00
    got = shown(pg)
    print("2. 100일 전(기기 시간대 미국):", got)
    ck(got == "수능 D-100", f"D-100 이어야 하는데 {got!r} 입니다")

    # 같은 한국 날짜인데 UTC로는 전날인 순간 — 시차로 하루가 밀리는지
    b2, pg2 = at(pw, (EXAM - datetime.timedelta(days=101)).isoformat() + "T20:00:00Z")
    got2 = shown(pg2)                               # 한국 05:00, 100일 전
    print("3. 같은 한국 날짜의 이른 새벽:", got2)
    ck(got2 == "수능 D-100", f"시차로 하루가 어긋났습니다: {got2!r}")
    b2.close()

    # 당일 — 자정 직후와 밤늦게 둘 다
    for t, label in (("T00:30:00Z", "한국 09:30"), ("T14:00:00Z", "한국 23:00")):
        b3, pg3 = at(pw, EXAM.isoformat() + t)
        g = shown(pg3)
        print(f"4. 시험 당일 {label}:", g)
        ck(g == "수능 D-DAY", f"당일에 {g!r} 이 떴습니다")
        b3.close()

    # 지난 뒤 — 아무 말도 하지 않아야 한다
    b4, pg4 = at(pw, (EXAM + datetime.timedelta(days=1)).isoformat() + "T01:00:00Z")
    g = shown(pg4)
    print("5. 다음 날:", g if g else "(숨김)")
    ck(g is None, f"시험이 지났는데 {g!r} 이 남아 있습니다 — 고쳐지지 않은 화면이 "
                  "스스로 틀린 소리를 하게 됩니다")
    b4.close()

    # 제목을 밀거나 화면을 넘치게 하지 않는가
    box = pg.evaluate("""()=>{const d=document.getElementById('dday');
      const r=d.getBoundingClientRect(), h=d.parentElement.getBoundingClientRect();
      return {넘침:document.documentElement.scrollWidth-innerWidth,
              제목줄안:r.top>=h.top-1&&r.bottom<=h.bottom+1,
              폭:Math.round(r.width)};}""")
    print("6. 자리:", box)
    ck(box["넘침"] == 0, f"가로로 {box['넘침']}px 넘칩니다")
    ck(box["제목줄안"], "제목 줄 밖으로 나갔습니다")
    b.close()

print("\n=== 문제:", "없음" if not BAD else "")
for x in BAD:
    print("  ★", x)
sys.exit(1 if BAD else 0)
