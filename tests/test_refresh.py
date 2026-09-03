"""EBSi 목록 파싱과 덧붙이기 원칙 — 실제 갱신 전에 망 없이 확인한다."""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import refresh_data as R

bad = []


def ck(ok, message):
    if not ok:
        bad.append(message)


print("1. 폼과 회차 행")
form = '''<form name="paperListFrm">
<input type="hidden" name="token" value="abc">
<input type="checkbox" name="monthAll" value="all" checked>
<input type="checkbox" name="ignored" value="x">
<input name="year" value="2026"><input name="year" value="2025">
<input name="month" value="09"><input name="month" value="11">
</form>'''
defaults, years, months = R.form_defaults(form)
ck(years == ["2026", "2025"], f"연도: {years}")
ck(months == ["09", "11"], f"월: {months}")
ck(defaults.get("monthAll") == "all" and "ignored" not in defaults,
   f"체크값: {defaults}")

row = '''
<div class="qus_box sample">
 <div class="qus_tit"><b>고3</b> 9월 모평(평가원)&nbsp;국어 홀수형&nbsp;</div>
 <span class="flag_subject_col1">2026</span>
 <a onclick="goDownLoadP('/202609031/go3/problem.pdf','full','record','301','2','140118');"></a>
 <a onclick="goDownLoadJ('/202609031/go3/answer.png','full','record','301','2','140118');"></a>
 <a onclick="goDownLoadH('/202609031/go3/solution.pdf','full','record','301','2','140118');"></a>
</div>'''
rows = R.parse_rows(row)
ck(len(rows) == 1, f"행 수: {len(rows)}")
if rows:
    subj, year, title, date, problem, answer, solution = rows[0]
    ck((subj, year, title, date) ==
       ("140118", "2026", "9월 모평(평가원) 홀수형", "202609031"),
       f"행 내용: {rows[0][:4]}")
    ck((problem, answer, solution) ==
       ("!/202609031/go3/problem.pdf", "!/202609031/go3/answer.png",
        "!/202609031/go3/solution.pdf"),
       f"파일 코드: {rows[0][4:]}")

print("2. 덧붙이기와 늦은 자료")
current = {"D300": {"140118": {"2026": [
    ["6월 모평(평가원)", "20260604", "old.pdf", "", ""]
]}}}
scraped = {"D300": {"140118": {"2026": [
    ["6월 모평(평가원)", "20260604", "new.pdf", "answer.png", "solution.pdf"],
    ["9월 모평(평가원)", "20260903", "sep.pdf", "sep.png", "sep-sol.pdf"],
]}, "999999": {"2026": [["모르는 과목", "20260903", "x", "", ""]]}}}
added, filled, skipped = R.merge(current, scraped, {"D300": {"140118"}})
bucket = current["D300"]["140118"]["2026"]
old = next(x for x in bucket if x[1] == "20260604")
ck((added, filled) == (1, 2), f"추가/채움: {added}/{filled}")
ck(old[2:] == ["old.pdf", "answer.png", "solution.pdf"], f"기존값 보존: {old}")
ck(skipped == ["D300/999999"], f"모르는 과목: {skipped}")

print("3. 순간 장애 재시도")
retry = R.new_session().get_adapter("https://").max_retries
ck(retry.total == 4 and {"GET", "POST"} <= set(retry.allowed_methods),
   f"재시도 설정: {retry}")
ck({429, 500, 502, 503, 504} <= set(retry.status_forcelist),
   f"재시도 상태: {retry.status_forcelist}")

print("4. 학년·활성 과목 단위 안전장치")
baseline = {
    "D300": {"100": {"2026": [["3월", "20260301", "p", "", ""]]}},
    "D200": {"200": {"2026": [["3월", "20260301", "p", "", ""]]}},
    "D100": {"300": {"2026": [["3월", "20260301", "p", "", ""]] * 10}},
}
known = {"D300": {"100"}, "D200": {"200"}, "D100": {"300"}}
missing_grade = {"D300": baseline["D300"], "D200": baseline["D200"], "D100": {}}
problems = R.coverage(baseline, missing_grade, known)
ck(any("D100" in p for p in problems), f"고1 전체 누락을 잡지 못함: {problems}")
missing_subject = {"D300": {}, "D200": baseline["D200"], "D100": baseline["D100"]}
problems = R.coverage(baseline, missing_subject, known)
ck(any("활성 과목" in p and "100" in p for p in problems),
   f"활성 과목 누락을 잡지 못함: {problems}")

report = R.unknown_report(
    {"D300": {"100": {"2026": [["3월", "20260301", "p", "", ""]]},
               "999": {"2026": [["미등록", "20260401", "p", "", ""]]}},
     "D200": {}, "D100": {}}, known)
ck(report["grades"]["D300"] ==
   [{"subjectId": "999", "count": 1, "latestDate": "20260401"}],
   f"미등록 과목 보고: {report}")

print("5. 화면·공개 JSON의 자료 수와 갱신 안내")
html = (ROOT / "index.html").read_text(encoding="utf-8")
payload_count = R.count(R.load_current(html))
api_count = json.loads((ROOT / "data/index.json").read_text(encoding="utf-8"))["count"]
ck(payload_count == api_count, f"자료 수: 화면 {payload_count} / JSON {api_count}")
ck("매일 오후 3시 23분과 밤 11시 23분에 EBSi를 확인합니다" in html,
   "화면의 갱신 시각이 예약 실행과 다릅니다")
ck("5,059회차" not in html, "화면에 오래된 고정 회차 수가 남았습니다")

print("\n=== 문제:", bad or "없음")
for message in bad:
    print("  ★", message)
raise SystemExit(1 if bad else 0)
