"""수능 D-day — 맞는 날을 세는가, 지난 뒤엔 입을 다무는가.

시행일에는 관례가 있다 — 11월 13~19일 사이의 목요일이고, 2016년 시행분부터
12회 연속 예외가 없다. 그래도 평가원이 해마다 따로 공고하는 것이지 규칙으로
정해진 것이 아니라(2015년 이전에는 자주 한 주 빨랐다), index.html 의 SUNEUNG
한 줄에 박아 두고 해마다 고친다. 고치는 것을 잊는 것이 이 기능의 유일하고도
확실한 고장 방식이다. 그래서 **날이 지났으면 여기서 실패한다** — 사람이
알아차릴 자리가 여기 말고 없다.

셈은 한국 시각으로 한다. 기기 시간대를 그대로 쓰면 시차가 있는 곳에서 하루가
어긋나는데, 이 숫자를 보는 이유가 바로 그 하루다.

    python3 tests/test_dday.py --date

날짜만 본다. 브라우저도 서버도 쓰지 않아 몇 밀리초면 끝나므로, 매일 도는 자료
갱신 워크플로가 이 형태로 부른다 — 시험이 지나는 시점은 대개 아무도 코드를 밀지
않는 때라, 코드를 밀 때만 도는 시험으로는 영영 안 잡힌다.
"""
import sys, pathlib, re, json, datetime
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


# ── 관례에 비추어 보기 (망을 타지 않는다) ─────────────────────────────────
#
# 요일: 2007학년도부터 **예외 없이 목요일**이다. 문제지 배송 차량이 주말 고속도로
# 혼잡을 피하도록 그때 바꾼 것이라, 사정이 있어 옮길 만한 종류의 것이 아니다.
# 저장소 자료 21회가 전부 목요일이었다 — 지진·코로나로 연기된 해까지 그렇다.
#
# 날짜: **11월 13~19일 사이의 목요일**. 7일 창이라 목요일이 딱 하나뿐이다.
# 저장소 자료로 재 보면 2016년 시행분부터 12회 연속 예외가 없고, 연기된 두 해도
# '연기 전 예정일'은 이 창 안이었다(2017-11-16, 2020-11-19). 어긋나는 옛 해는
# 2009·2011·2012·2013·2015뿐이고 전부 정확히 일주일 빨랐다 — 늦은 적은 없다.
#
# 그래도 **이걸로 날짜를 만들지는 않는다.** 관례는 바뀔 수 있고, 실제로 2015년
# 이전에는 자주 한 주 빨랐다. 박아 둔 값이 관례에서 벗어났을 때 사람을 부르는
# 데에만 쓴다.

def convention(exam_date):
    """관례에 어긋나는지 본다. (치명적인가, 할 말) 로 돌려준다."""
    W = "월화수목금토일"[exam_date.weekday()]
    if exam_date.weekday() != 3:
        return True, (f"{W}요일입니다 — 수능은 2007학년도 이후 예외 없이 목요일입니다"
                      " (문제지 배송이 주말 혼잡을 피하도록 정해진 것입니다).")
    if not (exam_date.month == 11 and 13 <= exam_date.day <= 19):
        return False, (f"11월 13~19일 창 밖입니다 — 2016년 이후 12회가 모두 그 안이었습니다."
                       " 평가원이 관례를 벗어나 공고했다면 그대로 두셔도 됩니다.")
    return False, ""


# ── 바깥과 대조 ────────────────────────────────────────────────────────
#
# 공식 쪽에는 기계가 읽을 출처가 없다. 평가원에 RSS가 없고, 공공데이터포털에도
# 수능 시행일 API가 없다. 시행 공고는 보도자료 HTML로만 나온다.
#
# 그나마 규격이 일정한 것이 한국어 위키백과의 학년도별 인포박스다. 2024~2027
# 학년도를 실제 공고와 대조해 네 해 모두 맞는 것을 확인했다. 그래도 **이 값을
# 화면에 쓰지는 않는다** — 누구나 고칠 수 있는 문서라, 틀린 날짜가 조용히
# 나가는 것보다 아무것도 안 뜨는 편이 낫다. 어긋날 때 사람을 부르는 데에만 쓴다.

def parse_infobox_date(wikitext):
    """인포박스의 '날짜' 칸에서 날짜를 꺼낸다.

    두 가지 모양이 쓰인다. 링크로 감싼 해와 그냥 쓴 해가 섞여 있다.
        |날짜 = [[2026년]] [[11월 19일]] (목)
        |날짜 = 2021년 11월 18일 ([[목요일]])
    """
    m = re.search(r"^\s*\|\s*날짜\s*=\s*(.+)$", wikitext, re.M)
    if not m:
        return None
    raw = m.group(1).replace("[[", "").replace("]]", "")
    d = re.search(r"(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일", raw)
    return (f"{d.group(1)}-{int(d.group(2)):02d}-{int(d.group(3)):02d}"
            if d else None)


def wiki_date(schoolyear):
    """위키백과가 말하는 그 학년도의 시행일. 못 읽으면 (None, 까닭)."""
    import urllib.error, urllib.parse, urllib.request
    t = urllib.parse.quote(f"{schoolyear}학년도 대학수학능력시험")
    url = ("https://ko.wikipedia.org/w/api.php?action=query&prop=revisions"
           f"&rvprop=content&rvslots=main&format=json&formatversion=2&titles={t}")
    req = urllib.request.Request(url, headers={
        "User-Agent": "gijul-jikhaeng/1.0 (https://github.com/Mangom72/Direct-mogo)"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            page = json.load(r)["query"]["pages"][0]
    except Exception as e:                       # 못 닿는 것은 잘못이 아니다
        return None, f"닿지 못했습니다 ({type(e).__name__})"
    if page.get("missing"):
        return None, "아직 문서가 없습니다"
    got = parse_infobox_date(page["revisions"][0]["slots"]["main"]["content"])
    return (got, "") if got else (None, "인포박스 모양이 달라졌습니다")


def cross_check(exam_date, why):
    """박아 둔 날짜를 위키백과와 견준다. 어긋날 때만 실패로 돌려준다."""
    sy = exam_date.year + 1                      # 시행 연도 + 1 = 학년도
    got, note = wiki_date(sy)
    if got is None:
        print(f"   대조: {sy}학년도 — {note} (넘어갑니다)")
        return True
    if got == exam_date.isoformat():
        print(f"   대조: {sy}학년도 위키백과도 {got} — 같습니다")
        return True
    print(f"\n  ★ 박아 둔 날짜와 위키백과가 다릅니다{why}\n"
          f"    index.html : {exam_date}\n"
          f"    위키백과   : {got}  ({sy}학년도 문서)\n"
          "    평가원 공고를 확인하고 맞는 쪽으로 고치십시오. 위키백과는 누구나"
          " 고칠 수 있으므로\n    그 값을 그대로 믿지는 마십시오.")
    return False


if left < 0:
    # 여기서 끝낸다. 나머지를 돌려 봐야 지난 날짜를 셀 뿐이고, 정작 사람이
    # 읽어야 할 말이 뒤따르는 출력에 묻힌다.
    print(f"\n  ★ 시행일이 {-left}일 지났습니다 — index.html 의 SUNEUNG 을 다음 수능"
          " 날짜로 고치십시오.\n    (평가원 공고. 그때까지 화면에는 아무것도 뜨지 않습니다.)")
    if DATE_ONLY:
        # 다음 시험 날짜를 짐작해 함께 알려 준다 — 고치러 갈 때 손에 들려 보낸다.
        nxt, note = wiki_date(EXAM.year + 2)
        print(f"    다음 회차: 위키백과에는 {nxt}로 적혀 있습니다 (확인 필요)"
              if nxt else f"    다음 회차: {note}")
    sys.exit(1)

fatal, say = convention(EXAM)
print(f"   관례: ★ {say}" if say else
      "   관례: 11월 13~19일 사이의 목요일 — 맞습니다")

if DATE_ONLY:
    ok = cross_check(EXAM, "")
    if fatal:
        # 목요일이 아닌 것은 거의 확실히 잘못 적은 것이다. 창 밖인 것은
        # 평가원이 관례를 바꿨을 수도 있으므로 말만 하고 넘어간다.
        print("\n  ★ 요일이 관례와 다릅니다 — 잘못 적었는지 확인하십시오.")
        sys.exit(1)
    sys.exit(0 if ok else 1)

# 인포박스 읽는 규칙 — 실제로 쓰이는 두 모양과, 읽지 말아야 할 것들.
# 망을 타지 않고 여기서 본다. 위키백과가 문서 틀을 바꾸면 --date 쪽이 조용히
# '모양이 달라졌습니다'로 넘어가 버리므로, 규칙 자체는 손에서 붙잡아 둔다.
FIXTURES = [
    ("|날짜 = [[2026년]] [[11월 19일]] (목)", "2026-11-19"),
    ("|날짜 = 2021년 11월 18일 ([[목요일]])", "2021-11-18"),
    ("|  날짜   =   [[2024년]] [[11월 14일]]", "2024-11-14"),
    ("|이름 = 2027학년도\n|날짜 = [[2026년]] [[11월 19일]]\n|응시자 = 50만", "2026-11-19"),
    ("|응시일 = [[2026년]] [[11월 19일]]", None),      # 다른 칸은 읽지 않는다
    ("|날짜 = 미정", None),
]
for text, want in FIXTURES:
    got = parse_infobox_date(text)
    ck(got == want, f"인포박스 읽기: {text[:34]!r} → {got!r} (기대 {want!r})")
print(f"2. 인포박스 읽는 규칙 {len(FIXTURES)}가지 — "
      f"{'전부 맞음' if not BAD else '어긋남'}")

# 관례 판정 — 실제로 있었던 날들로 견준다.
CONV = [
    ("2026-11-19", False, False),   # 2027학년도, 공고
    ("2025-11-13", False, False),   # 창의 첫날
    ("2016-11-17", False, False),
    ("2015-11-12", False, True),    # 관례 이전 — 창 밖이지만 잘못은 아니다
    ("2020-12-03", False, True),    # 코로나로 12월 (요일은 목요일)
    ("2026-11-18", True,  True),    # 수요일 — 잘못 적은 것
    ("2026-11-21", True,  True),    # 토요일
]
for iso, want_fatal, want_say in CONV:
    f, s = convention(datetime.date.fromisoformat(iso))
    ck(f == want_fatal and bool(s) == want_say,
       f"관례 판정 {iso}: 치명={f}(기대 {want_fatal}) 할말={bool(s)}(기대 {want_say})")
print(f"3. 관례 판정 {len(CONV)}가지 — {'전부 맞음' if not BAD else '어긋남'}")

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
    print("4. 100일 전(기기 시간대 미국):", got)
    ck(got == "수능 D-100", f"D-100 이어야 하는데 {got!r} 입니다")

    # 같은 한국 날짜인데 UTC로는 전날인 순간 — 시차로 하루가 밀리는지
    b2, pg2 = at(pw, (EXAM - datetime.timedelta(days=101)).isoformat() + "T20:00:00Z")
    got2 = shown(pg2)                               # 한국 05:00, 100일 전
    print("5. 같은 한국 날짜의 이른 새벽:", got2)
    ck(got2 == "수능 D-100", f"시차로 하루가 어긋났습니다: {got2!r}")
    b2.close()

    # 당일 — 자정 직후와 밤늦게 둘 다
    for t, label in (("T00:30:00Z", "한국 09:30"), ("T14:00:00Z", "한국 23:00")):
        b3, pg3 = at(pw, EXAM.isoformat() + t)
        g = shown(pg3)
        print(f"6. 시험 당일 {label}:", g)
        ck(g == "수능 D-DAY", f"당일에 {g!r} 이 떴습니다")
        b3.close()

    # 지난 뒤 — 아무 말도 하지 않아야 한다
    b4, pg4 = at(pw, (EXAM + datetime.timedelta(days=1)).isoformat() + "T01:00:00Z")
    g = shown(pg4)
    print("7. 다음 날:", g if g else "(숨김)")
    ck(g is None, f"시험이 지났는데 {g!r} 이 남아 있습니다 — 고쳐지지 않은 화면이 "
                  "스스로 틀린 소리를 하게 됩니다")
    b4.close()

    # 제목을 밀거나 화면을 넘치게 하지 않는가
    box = pg.evaluate("""()=>{const d=document.getElementById('dday');
      const r=d.getBoundingClientRect(), h=d.parentElement.getBoundingClientRect();
      return {넘침:document.documentElement.scrollWidth-innerWidth,
              제목줄안:r.top>=h.top-1&&r.bottom<=h.bottom+1,
              폭:Math.round(r.width)};}""")
    print("8. 자리:", box)
    ck(box["넘침"] == 0, f"가로로 {box['넘침']}px 넘칩니다")
    ck(box["제목줄안"], "제목 줄 밖으로 나갔습니다")
    b.close()

print("\n=== 문제:", "없음" if not BAD else "")
for x in BAD:
    print("  ★", x)
sys.exit(1 if BAD else 0)
