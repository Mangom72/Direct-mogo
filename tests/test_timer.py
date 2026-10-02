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
    pg.select_option("#grp", label="과학탐구")
    pg.select_option("#sub", label="생명과학Ⅰ")
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

    # 실제 편집 화면: 초까지 보존하고, 오답 범위·중복을 정리한다.
    pg.locator(".record.took").first.click()
    ck(pg.locator("#recordScore").get_attribute("placeholder") == "0~50", "50점 과목의 점수 안내가 틀립니다")
    pg.locator("#recordScore").fill("51")
    pg.locator(".record-save").click()
    ck(pg.locator("#recordForm").is_visible() and not pg.locator("#recordScore").evaluate("e=>e.validity.valid"), "50점을 넘는 점수를 저장했습니다")
    ck(pg.evaluate("k=>!(RECORDS[k] && 'score' in RECORDS[k])", key), "범위 밖 입력이 기존 기록을 바꿨습니다")
    pg.locator("#recordScore").fill("50")
    pg.locator(".record-save").click()
    ck(pg.evaluate("k=>RECORDS[k].score", key) == 50, "50점 만점 기록이 저장되지 않았습니다")
    pg.locator(".record.took").first.click()
    pg.locator("#recordMinutes").fill("105")
    pg.locator("#recordSeconds").fill("30")
    pg.locator("#recordScore").fill("42.5")
    pg.locator(".record-save").click()
    ck(pg.locator("#recordForm").is_visible() and not pg.locator("#recordScore").evaluate("e=>e.validity.valid"), "소수점 점수를 저장했습니다")
    ck(pg.evaluate("k=>RECORDS[k].score", key) == 50, "소수점 입력이 기존 점수를 바꿨습니다")
    pg.locator("#recordScore").fill("42")
    pg.locator("#recordWrong").fill("7, 3, 7, 12-14")
    pg.locator(".record-save").click()
    edited = pg.evaluate("k=>({time:TIMES[k],record:RECORDS[k],solved:SOLVED[k]})", key)
    print("6. 수동 수정·점수·오답:", edited)
    ck(edited["time"] == {"spent": 6330, "limit": 6000}, "수동 수정이 초 또는 고사 시간을 바꿨습니다")
    ck(edited["record"] == {"score": 42, "wrong": [3, 7, 12, 13, 14]}, "점수·오답 범위·중복 처리가 틀립니다")
    ck("105분 30초" in pg.locator(".record.took").first.inner_text(), "수정한 초가 표시되지 않습니다")

    pg.locator(".record.took").first.click()
    pg.locator("#recordWrong").fill("14-12")
    pg.locator(".record-save").click()
    ck(pg.locator(".record-error").inner_text() and pg.locator("#recordForm").is_visible(), "잘못된 오답 범위를 저장했습니다")
    ck(pg.evaluate("k=>RECORDS[k].wrong", key) == [3, 7, 12, 13, 14], "잘못 입력한 값이 기존 기록을 바꿨습니다")
    pg.locator("#recordWrong").fill("99")
    pg.locator("#sheetX").click()
    ck(pg.evaluate("k=>RECORDS[k].wrong", key) == [3, 7, 12, 13, 14], "취소한 값이 저장됐습니다")
    pg.reload(wait_until="load")
    pg.wait_for_selector(".record.took")
    ck(pg.evaluate("k=>RECORDS[k].score", key) == 42, "새로 열면 점수가 사라집니다")
    ck(pg.evaluate("k=>TIMES[k].spent", key) == 6330, "새로 열면 수정한 시간이 사라집니다")

    # 공통/선택 과목과 학년별 100점/50점 분류, 실제 100점 폼의 경계값.
    limits = pg.evaluate("()=>Object.fromEntries(Object.keys(SUBINDEX).map(k=>[SUBINDEX[k].name,scoreLimit(k+'/20260101/시험')]))")
    for name in ("국어", "화법과 작문", "언어와 매체", "수학", "확률과 통계", "미적분", "기하", "영어"):
        ck(limits[name] == 100, name + " 만점이 100이 아닙니다")
    for name in ("한국사", "통합사회", "통합과학", "생명과학Ⅰ", "성공적인 직업 생활", "독일어Ⅰ"):
        ck(limits[name] == 50, name + " 만점이 50이 아닙니다")
    pg.select_option("#grp", label="국어")
    pg.select_option("#sub", label="화법과 작문")
    pg.locator(".record").first.click()
    ck(pg.locator("#recordScore").get_attribute("placeholder") == "0~100", "100점 과목의 점수 안내가 틀립니다")
    hundred_key = pg.locator(".record").first.get_attribute("data-k")
    pg.locator("#recordScore").fill("101")
    pg.locator(".record-save").click()
    ck(pg.locator("#recordForm").is_visible(), "100점을 넘는 점수를 저장했습니다")
    pg.locator("#recordScore").fill("100")
    pg.locator(".record-save").click()
    ck(pg.evaluate("k=>RECORDS[k].score", hundred_key) == 100, "100점 만점 기록이 저장되지 않았습니다")
    pg.select_option("#grp", label="과학탐구")
    pg.select_option("#sub", label="생명과학Ⅰ")

    # 파일 백업과 네이티브 사본에 모두 들어가야 한다.
    archived = pg.evaluate("()=>JSON.stringify(makeBackup())")
    payload = pg.evaluate("""()=>{let sent; GijulNative.setSolved=x=>sent=JSON.parse(x); tellSolved(); return sent;}""")
    ck(payload["records"][key]["score"] == 42 and payload["times"][key]["spent"] == 6330,
       "앱의 사본·자동 백업에 시간이나 점수가 빠집니다")
    pg.evaluate("()=>{RECORDS={}; TIMES={}; SOLVED={};}")
    pg.evaluate("x=>applyBackup(readBackup(x),'merge')", archived)
    ck(pg.evaluate("k=>RECORDS[k].wrong", key) == [3, 7, 12, 13, 14], "백업에서 오답이 돌아오지 않습니다")
    pg.evaluate("""k=>applyBackup(readBackup(JSON.stringify({v:1,subs:[],solved:{},
      records:{[k]:{score:99,wrong:[1]},'모르는/과목/20250101/시험':{score:0,wrong:[]}}})), 'merge')""", key)
    ck(pg.evaluate("k=>RECORDS[k].score", key) == 42, "합치기가 이 기기의 점수를 덮어썼습니다")
    ck(pg.evaluate("()=>RECORDS['모르는/과목/20250101/시험'].score") == 0, "모르는 과목·0점 기록이 버려졌습니다")
    dirty = pg.evaluate("""()=>readBackup(JSON.stringify({v:1, records:{
      'a/b/c/d':{score:-1,wrong:[0]},'a/b/c/e':{score:'85',wrong:[2.5]},
      'a/b/c/f':{score:0,wrong:[3,3,1]},'bad':{score:80}}})).records""")
    ck(dirty == {"a/b/c/f": {"score": 0, "wrong": [1, 3]}}, "잘못된 백업 기록을 받아들였습니다")

    pg.locator(".record.took").first.click()
    pg.locator("#recordMinutes").fill("")
    pg.locator("#recordSeconds").fill("")
    pg.locator("#recordScore").fill("0")
    pg.locator("#recordWrong").fill("없음")
    pg.locator(".record-save").click()
    ck(pg.evaluate("k=>!TIMES[k] && RECORDS[k].score===0 && RECORDS[k].wrong.length===0", key),
       "시간 지우기·0점·오답 없음이 저장되지 않습니다")
    pg.evaluate("()=>applyBackup(readBackup(JSON.stringify({v:1,subs:[],solved:{}})), 'replace')")
    ck(pg.evaluate("()=>Object.keys(RECORDS).length===0"), "옛 백업으로 덮어쓸 때 기록이 남습니다")
    pg.locator(".record").first.click()
    pg.locator("#recordMinutes").fill("30")
    pg.locator(".record-save").click()
    ck(pg.evaluate("k=>!!SOLVED[k] && TIMES[k].limit===0", key), "타이머 없이 수동으로 기록할 수 없습니다")
    print("   입력 검증·취소·재실행·백업·0점·오답 없음·옛 백업 확인")

    pg.screenshot(path=str(pathlib.Path(SHOT) / "timer.png"))
    print("   오류:", errs or "없음")
    ck(not errs, f"스크립트 오류: {errs}")
    ctx.close()
    b.close()

print("\n=== 문제:", "없음" if not BAD else "")
for x in BAD:
    print("  ★", x)
sys.exit(1 if BAD else 0)
