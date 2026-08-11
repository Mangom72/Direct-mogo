"""자료 갱신 내역 — 아무것도 안 바뀐 날과 실패한 날이 보이는가.

자동 갱신이 잘 돌고 있는지 사용자가 볼 수 있어야 한다는 요구에서 나왔다.
새 자료가 없는 날은 저장소에 커밋이 남지 않으므로, 깃허브가 들고 있는 실행
기록을 읽는다. 이 환경의 브라우저는 깃허브로 나갈 수 없어 응답을 흉내낸다.
"""
import sys, pathlib, json
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from harness import CHROME, ROOT, SHOT, site, Serve
_srv, SITE = site()
from playwright.sync_api import sync_playwright

BAD = []
def ck(cond, msg):
    if not cond:
        BAD.append(msg)

RUNS = {"workflow_runs": [
    {"created_at": "2026-08-11T14:03:00Z", "status": "completed", "conclusion": "success"},
    {"created_at": "2026-08-10T14:02:00Z", "status": "completed", "conclusion": "success"},
    {"created_at": "2026-08-09T14:02:00Z", "status": "completed", "conclusion": "failure"},
    {"created_at": "2026-08-08T14:02:00Z", "status": "in_progress", "conclusion": None},
]}
# 11일에만 자료가 늘었다 — 나머지는 확인만 하고 끝난 날이다.
COMMITS = [{"commit": {"message": "Refresh exam data from EBSi (새 회차 12건, 늦게 올라온 자료 3칸)",
                       "committer": {"date": "2026-08-11T14:05:00Z"}}}]

def rows(pg):
    return pg.eval_on_selector_all(".slog", """e=>e.map(x=>({
        day:(x.querySelector('.d')||{}).textContent||'',
        mark:(x.querySelector('.m')||{}).textContent||'',
        what:(x.querySelector('.w')||{}).textContent||''}))""")

def page(b, ok=True):
    ctx = b.new_context(viewport={"width": 412, "height": 900}, service_workers="block")
    def api(route):
        if not ok:
            return route.abort()
        u = route.request.url
        body = RUNS if "/runs" in u else COMMITS
        route.fulfill(status=200, body=json.dumps(body),
                      headers={"Content-Type": "application/json",
                               "Access-Control-Allow-Origin": "*"})
    ctx.route("https://api.github.com/**", api)
    pg = ctx.new_page()
    pg.errs = []
    pg.on("pageerror", lambda e: pg.errs.append(str(e)[:140]))
    pg.goto(SITE, wait_until="load")
    pg.wait_for_selector("#logBtn", timeout=20000)
    return pg

with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path=CHROME)

    pg = page(b)
    ck(not pg.is_visible("#sheet"), "열기 전에 이미 떠 있습니다")
    pg.click("#logBtn")
    pg.wait_for_selector("#sheet:not([hidden])")
    pg.wait_for_function("()=>document.querySelectorAll('.slog').length > 1", timeout=15000)
    got = rows(pg)
    print("1. 제목:", repr(pg.text_content("#sheetNm")), "|", repr(pg.text_content("#sheetSb")))
    for r in got:
        print(f"   {r['day']:<8} [{r['mark']}] {r['what']}")

    ck(len(got) == 4, f"실행 기록이 {len(got)}줄입니다 (4줄이어야 합니다)")
    marks = [r["mark"] for r in got]
    ck(marks[0] == "새 자료", f"자료가 는 날의 표시가 {marks[0]!r} 입니다")
    ck("12건" in got[0]["what"], f"늘어난 건수가 안 보입니다: {got[0]['what']!r}")
    ck(marks[1] == "변경 없음", f"아무것도 안 바뀐 날이 {marks[1]!r} 로 나옵니다")
    ck("없었습니다" in got[1]["what"], f"0건인 날의 설명이 없습니다: {got[1]['what']!r}")
    ck(marks[2] == "실패", f"실패한 날이 {marks[2]!r} 로 나옵니다")
    ck(marks[3] == "도는 중", f"아직 도는 중인 날이 {marks[3]!r} 로 나옵니다")
    ck(pg.is_hidden("#sheetAll"), "갱신 내역인데 저장 단추가 보입니다")

    # 시트의 기본 동작(Esc, 초점 복귀)이 그대로여야 한다
    pg.keyboard.press("Escape")
    pg.wait_for_timeout(300)
    ck(pg.is_hidden("#sheet"), "Esc로 닫히지 않습니다")
    ck(pg.evaluate("()=>document.activeElement.id") == "logBtn", "닫은 뒤 초점이 단추로 돌아오지 않습니다")
    print("2. Esc로 닫힘 · 초점 복귀 정상")
    print("   오류:", pg.errs or "없음")
    pg.context.close()

    # 깃허브에 닿지 못할 때
    pg = page(b, ok=False)
    pg.click("#logBtn")
    pg.wait_for_selector("#sheet:not([hidden])")
    pg.wait_for_function("()=>/못했|않습니다/.test(document.querySelector('.slog').textContent)", timeout=15000)
    txt = pg.text_content(".slog")
    link = pg.eval_on_selector_all(".slog a", "e=>e.map(x=>x.href)")
    print("3. 닿지 못할 때:", repr(txt[:44]))
    ck("못했" in txt or "않습니다" in txt, "실패했는데 아무 말이 없습니다")
    ck(any("actions" in u for u in link), "직접 볼 수 있는 길을 주지 않습니다")
    pg.context.close()
    b.close()

print("\n=== 문제:", "없음" if not BAD else "")
for x in BAD:
    print("  ★", x)
sys.exit(1 if BAD else 0)
