"""수능 D-day — 관례대로 셈하는가, 연기됐을 때 손으로 덮을 수 있는가.

시행일은 **11월 13~19일 사이의 목요일**이다. 7일 창이라 목요일이 딱 하나뿐이어서
해만 알면 날이 정해진다. 2016년 시행분부터 이 기준이 정착했고 그 뒤로 예외가
없다 — 그 이전에는 '11월 둘째 주'가 기준이라 한 주 빨랐다. 요일이 목요일인 것은
2007년 시행분부터이며, 문제지 수송 차량이 주말 고속도로 혼잡을 피하도록 수요일에서
옮긴 것이다.

그래서 화면은 상수를 두지 않고 셈한다. 해마다 손댈 일이 없다.

지금까지의 예외는 **전부 연기**였다 — 2005 APEC, 2010 G20, 2017 포항 지진,
2020 코로나. 그때만 index.html 의 SUNEUNG_MOVED 에 실제 시행일을 적는다.

    python3 tests/test_dday.py --date

셈한 날짜를 한국어 위키백과와 대조만 한다. 브라우저도 서버도 쓰지 않아 몇
밀리초면 끝나므로 매일 도는 자료 갱신이 이 형태로 부른다 — 평가원이 관례를
벗어나 공고하거나 시험이 연기되면, 화면은 그것을 모른 채 옛 관례대로 세고 있다.
그것을 알아차릴 자리가 여기 말고 없다.
"""
import sys, pathlib, re, json, datetime
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from harness import ROOT

DATE_ONLY = "--date" in sys.argv

BAD = []
def ck(cond, msg):
    if not cond:
        BAD.append(msg)


def scheduled(year):
    """그 해 11월 13~19일 사이의 목요일. 화면의 셈과 같은 규칙."""
    for day in range(13, 20):
        d = datetime.date(year, 11, day)
        if d.weekday() == 3:
            return d


src = (ROOT / "index.html").read_text(encoding="utf-8")
m = re.search(r'const SUNEUNG_MOVED = "([^"]*)"', src)
if not m:
    print("★ index.html 에서 SUNEUNG_MOVED 를 찾지 못했습니다")
    sys.exit(1)
MOVED = m.group(1)
TODAY = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).date()

EXAM = scheduled(TODAY.year)
if TODAY > EXAM:
    EXAM = scheduled(TODAY.year + 1)
note = ""
if MOVED:
    mv = datetime.date.fromisoformat(MOVED)
    if mv >= TODAY:
        EXAM, note = mv, "  (연기됨 — SUNEUNG_MOVED)"
    else:
        note = f"  (SUNEUNG_MOVED={MOVED} 는 지난 날이라 무시됩니다 — 지우셔도 됩니다)"
print(f"1. 오늘(한국) {TODAY} · 다음 수능 {EXAM} · D-{(EXAM - TODAY).days}{note}")


# ── 바깥과 대조 ────────────────────────────────────────────────────────
#
# 공식 쪽에는 기계가 읽을 출처가 없다. 평가원에 RSS가 없고, 공공데이터포털에도
# 수능 시행일 API가 없다. 시행 공고는 보도자료 HTML로만 나온다.
#
# 그나마 규격이 일정한 것이 한국어 위키백과의 학년도별 인포박스다. 2024~2027
# 학년도를 실제 공고와 대조해 네 해 모두 맞는 것을 확인했다. 그래도 **이 값을
# 화면에 쓰지는 않는다** — 누구나 고칠 수 있는 문서라, 틀린 날짜가 조용히
# 나가는 것보다 관례대로 세는 편이 낫다. 어긋날 때 사람을 부르는 데에만 쓴다.

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


if DATE_ONLY:
    sy = EXAM.year + 1                           # 시행 연도 + 1 = 학년도
    got, why = wiki_date(sy)
    if got is None:
        print(f"   대조: {sy}학년도 — {why} (넘어갑니다)")
        sys.exit(0)
    if got == EXAM.isoformat():
        print(f"   대조: {sy}학년도 위키백과도 {got} — 같습니다")
        sys.exit(0)
    how = "SUNEUNG_MOVED" if note.startswith("  (연기") else "11월 13~19일 목요일"
    print(f"\n  ★ 화면이 세는 날과 위키백과가 다릅니다\n"
          f"    화면     : {EXAM}   ({how})\n"
          f"    위키백과 : {got}   ({sy}학년도 문서)\n"
          "    연기됐거나 평가원이 관례를 벗어나 공고한 것일 수 있습니다."
          " 공고를 확인하고,\n    맞으면 index.html 의 SUNEUNG_MOVED 에 실제"
          " 시행일을 적으십시오.\n    위키백과는 누구나 고칠 수 있으므로 그 값을"
          " 그대로 믿지는 마십시오.")
    sys.exit(1)


# ── 셈이 실제 역사와 맞는가 (망을 타지 않는다) ────────────────────────────
#
# 2016년 시행분부터, 연기된 해를 빼고 전부. 연기된 해는 '연기 전 예정일'이
# 나오는 것이 맞다 — 그 자리가 곧 SUNEUNG_MOVED 로 덮을 자리다.
HISTORY = [
    (2016, "2016-11-17", None),
    (2017, "2017-11-16", "2017-11-23"),   # 포항 지진 — 하루 전 긴급 연기
    (2018, "2018-11-15", None),
    (2019, "2019-11-14", None),
    (2020, "2020-11-19", "2020-12-03"),   # 코로나 — 2주 연기
    (2021, "2021-11-18", None),
    (2022, "2022-11-17", None),
    (2023, "2023-11-16", None),
    (2024, "2024-11-14", None),           # 창의 이른 쪽
    (2025, "2025-11-13", None),           # 가장 이른 날
    (2026, "2026-11-19", None),           # 가장 늦은 날
    (2027, "2027-11-18", None),
]
for y, want, moved in HISTORY:
    got = scheduled(y).isoformat()
    ck(got == want, f"{y}년 예정일: {got} (기대 {want})")
moved_n = sum(1 for *_, mv in HISTORY if mv)
print(f"2. 2016~2027 예정일 {len(HISTORY)}회 — "
      f"{'전부 맞음' if not BAD else '어긋남'} (그중 {moved_n}회는 뒤에 연기됨)")

# 관례가 정착하기 전(2015년 이전)은 셈과 다르다. 그 사실을 못박아 둔다 —
# 누군가 '옛날 것도 세지지 않느냐'고 규칙을 되돌리지 않도록.
OLD = [(2015, "2015-11-12"), (2013, "2013-11-07"), (2011, "2011-11-10")]
for y, real in OLD:
    ck(scheduled(y).isoformat() != real,
       f"{y}년은 관례 이전이라 셈과 달라야 하는데 같습니다")
print(f"3. 2015년 이전 {len(OLD)}회는 셈과 다름 — 관례 정착 이전이 맞음")

FIXTURES = [
    ("|날짜 = [[2026년]] [[11월 19일]] (목)", "2026-11-19"),
    ("|날짜 = 2021년 11월 18일 ([[목요일]])", "2021-11-18"),
    ("|  날짜   =   [[2024년]] [[11월 14일]]", "2024-11-14"),
    ("|이름 = 2027학년도\n|날짜 = [[2026년]] [[11월 19일]]\n|응시자 = 50만", "2026-11-19"),
    ("|응시일 = [[2026년]] [[11월 19일]]", None),      # 다른 칸은 읽지 않는다
    ("|날짜 = 미정", None),
]
for text, want in FIXTURES:
    ck(parse_infobox_date(text) == want,
       f"인포박스 읽기: {text[:34]!r} → {parse_infobox_date(text)!r} (기대 {want!r})")
print(f"4. 인포박스 읽는 규칙 {len(FIXTURES)}가지 — "
      f"{'전부 맞음' if not BAD else '어긋남'}")

# 여기서부터는 화면을 연다. 위의 확인만 필요한 쪽(매일 도는 갱신)이 브라우저를
# 깔지 않아도 되도록, 무거운 것은 여기서 처음 불러온다.
from harness import CHROME, site                                   # noqa: E402
_srv, SITE = site()
from playwright.sync_api import sync_playwright                    # noqa: E402


def at(pw, when, tz="America/Los_Angeles"):
    """기기 시계를 그 순간으로, 시간대는 일부러 한국 밖으로 두고 연다.

    시계는 굳어 있지 않다. `__at('...')` 으로 옮길 수 있어서, 열어 둔 채
    자정을 넘기는 상황을 그대로 만들어 볼 수 있다. 예약된 setTimeout 은
    `__timeouts` 에 쌓인다 — 다음 0시에 스스로 깨어나는지 보려는 것이다.
    """
    b = pw.chromium.launch(executable_path=CHROME)
    ctx = b.new_context(viewport={"width": 412, "height": 800},
                        service_workers="block", timezone_id=tz)
    pg = ctx.new_page()
    pg.add_init_script(f"""
      const D = Date; let F = D.parse('{when}');
      Date = class extends D {{
        constructor(...a){{ super(...(a.length ? a : [F])); }}
        static now(){{ return F; }} }};
      Date.parse = D.parse; Date.UTC = D.UTC;
      globalThis.__at = t => {{ F = D.parse(t); }};
      globalThis.__timeouts = [];
      const ST = setTimeout.bind(globalThis);
      globalThis.setTimeout = (fn, ms, ...r) => {{
        __timeouts.push(ms); return ST(fn, ms, ...r); }};""")
    pg.goto(SITE, wait_until="load")
    pg.wait_for_selector(".item", timeout=25000)
    return b, pg


def badge(pg):
    return pg.evaluate("()=>{const e=document.getElementById('dday');"
                       "return e && !e.hidden ? [e.textContent, e.title] : null;}")


with sync_playwright() as pw:
    # 화면이 실제로 역사와 같은 날을 가리키는가 — 그 해 1월에 열어 본다
    for y, want, _ in HISTORY[:6]:
        b, pg = at(pw, f"{y}-01-15T02:00:00Z")
        got = badge(pg)
        ck(got and got[1].startswith(want.replace("-", ".")),
           f"{y}년 1월에 열었을 때 화면이 {got} 를 가리킵니다 (기대 {want})")
        b.close()
    print(f"5. 화면이 가리키는 날 {min(6, len(HISTORY))}회 — "
          f"{'역사와 같음' if not BAD else '어긋남'}")

    NEXT = scheduled(2027)                      # 2026 다음 회차
    # 시차 — 기기가 미국인데 한국 날짜로 세는가
    b, pg = at(pw, "2026-08-11T02:00:00Z")      # 한국 11:00
    ck(badge(pg)[0] == "수능 D-100", f"D-100 이어야 하는데 {badge(pg)} 입니다")
    b2, pg2 = at(pw, "2026-08-10T20:00:00Z")    # 한국 11일 05:00, 같은 날
    ck(badge(pg2)[0] == "수능 D-100", f"시차로 하루 어긋남: {badge(pg2)}")
    b2.close()
    print("6. 시차 — 기기가 미국이어도 한국 날짜로 셈")

    # 당일과 그 다음 날 — 넘어가는가
    b3, pg3 = at(pw, "2026-11-19T14:00:00Z")    # 한국 23:00, 당일
    ck(badge(pg3)[0] == "수능 D-DAY", f"당일에 {badge(pg3)}")
    b3.close()
    b4, pg4 = at(pw, "2026-11-20T01:00:00Z")    # 한국 10:00, 다음 날
    g = badge(pg4)
    ck(g and g[1].startswith(NEXT.isoformat().replace("-", ".")),
       f"다음 날 이듬해({NEXT})로 넘어가야 하는데 {g} 입니다")
    b4.close()
    print(f"7. 당일 D-DAY · 다음 날 {NEXT} 로 넘어감")

    # 자정을 넘겨도 그 자리에서 바뀌는가.
    #
    # 앱은 닫아도 죽지 않고 접히기만 한다. 숫자를 열 때 한 번만 세면, 이튿날
    # 아침에 다시 펴도 어제 숫자가 그대로 남는다 — 실제로 그랬다. 그래서
    # 화면으로 돌아오는 길목(visibilitychange·pageshow·focus)마다 다시 세고,
    # 열어 둔 채로도 다음 0시에 스스로 깨어난다.
    b5, pg5 = at(pw, "2026-08-12T02:00:00Z")        # 한국 12일 11:00
    ck(badge(pg5)[0] == "수능 D-99", f"D-99 여야 하는데 {badge(pg5)} 입니다")

    # (1) 다음 한국 0시에 맞춰 예약해 두는가. 13시간 뒤 + 1초.
    due = 13 * 3600e3 + 1000
    ck(due in pg5.evaluate("()=>__timeouts"),
       f"다음 0시({due:.0f}ms 뒤)에 다시 그릴 예약이 없습니다")

    # (2) 접었다 편 사이에 날이 바뀌었다 — 펴는 순간 다시 세는가.
    #     시계만 옮기고 아직 아무 일도 일으키지 않았으면 옛 숫자가 남아 있어야
    #     한다. 그래야 뒤이어 바뀌는 것이 '돌아왔기 때문'임이 분명해진다.
    pg5.evaluate("()=>__at('2026-08-13T01:00:00Z')")   # 한국 13일 10:00
    ck(badge(pg5)[0] == "수능 D-99", "돌아오기 전인데 벌써 바뀌었습니다")

    BACK = [                       # 어디에 무엇을 보내면 다시 세는가
        ("visibilitychange", "document", "2026-08-13T01:00:00Z", "수능 D-98"),
        ("pageshow",         "window",   "2026-08-14T01:00:00Z", "수능 D-97"),
        ("focus",            "window",   "2026-08-15T01:00:00Z", "수능 D-96"),
    ]
    for how, where, when, want in BACK:
        pg5.evaluate(f"()=>__at('{when}')")
        pg5.evaluate(f"()=>{where}.dispatchEvent(new Event('{how}'))")
        ck(badge(pg5)[0] == want,
           f"{how} 로 돌아왔을 때 {badge(pg5)} — {want} 여야 합니다")
    b5.close()
    print("9. 자정 넘김 — 다음 0시 예약 · 돌아오는 길목 3가지에서 다시 셈")

    # 자리 — 제목을 밀거나 화면을 넘치게 하지 않는가
    box = pg.evaluate("""()=>{const d=document.getElementById('dday');
      const r=d.getBoundingClientRect(), h=d.parentElement.getBoundingClientRect();
      return {넘침:document.documentElement.scrollWidth-innerWidth,
              제목줄안:r.top>=h.top-1&&r.bottom<=h.bottom+1};}""")
    print("8. 자리:", box)
    ck(box["넘침"] == 0, f"가로로 {box['넘침']}px 넘칩니다")
    ck(box["제목줄안"], "제목 줄 밖으로 나갔습니다")
    b.close()

print("\n=== 문제:", "없음" if not BAD else "")
for x in BAD:
    print("  ★", x)
sys.exit(1 if BAD else 0)
