"""주소로 화면을 가리키기 — 해시 딥링크, 뒤로 가기, 되돌아오기."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from harness import CHROME, ROOT, SHOT, site, Serve
_srv, SITE = site()
from playwright.sync_api import sync_playwright

URL = SITE
def state(pg):
    return pg.evaluate("""() => ({
        grade: [...document.querySelectorAll('#gradeBox button')]
                 .findIndex(b => b.getAttribute('aria-pressed') === 'true'),
        grp: document.querySelector('#grp').value,
        grpName: document.querySelector('#grp').selectedOptions[0].textContent,
        sub: document.querySelector('#sub').value,
        subName: document.querySelector('#sub').selectedOptions[0].textContent,
        kind: [...document.querySelectorAll('#kindBox button')]
                .find(b => b.getAttribute('aria-pressed') === 'true').dataset.k,
        year: document.querySelector('#yr').value,
        hash: location.hash,
    })""")

with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path=CHROME)
    ctx = b.new_context(viewport={"width": 412, "height": 900},
                        permissions=["clipboard-read", "clipboard-write"])
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))

    def go(hash_=""):
        pg.goto(URL + hash_, wait_until="domcontentloaded")
        pg.wait_for_selector(".item, .empty", timeout=20000)
        pg.wait_for_function("() => !!document.querySelector('.tally')", timeout=20000)

    # ---- 1. deep link
    go("#/D200/17022/2023/edu")
    s = state(pg)
    print("1. #/D200/17022/2023/edu ->", {k: s[k] for k in ("grade","grpName","subName","kind","year")})
    print("   맞음:", (s["grade"], s["sub"], s["kind"], s["year"]) == (1, "17022", "edu", "2023"),
          "| 표제:", pg.text_content(".tally .big"), "|", pg.text_content(".tally .sm"))

    # ---- 2. filter change updates hash
    pg.select_option("#yr", "2021")
    pg.wait_for_timeout(80)
    h1 = pg.evaluate("location.hash")
    pg.click("#kindBox button[data-k='all']")
    pg.wait_for_timeout(80)
    print("2. 연도 변경 ->", h1, "| 기관 변경 ->", pg.evaluate("location.hash"))

    # ---- 3. reload restores (hash present)
    before = state(pg)
    pg.reload(wait_until="domcontentloaded")
    pg.wait_for_function("() => !!document.querySelector('.tally')", timeout=20000)
    print("3. 새로고침 복원:", state(pg) == before)

    # ---- 4. no hash -> last state from localStorage
    pg.goto(URL, wait_until="domcontentloaded")
    pg.wait_for_function("() => !!document.querySelector('.tally')", timeout=20000)
    s2 = state(pg)
    print("4. 해시 없이 재방문 -> 지난 화면 복원:",
          (s2["sub"], s2["kind"], s2["year"]) == (before["sub"], before["kind"], before["year"]),
          "| 해시 재작성:", s2["hash"])

    # ---- 5. bad hashes fall back safely
    for bad in ["#/D999/000/2024/gov", "#/D300/158", "#쓰레기", "#/D300/158/9999/xx"]:
        go(bad)
        s3 = state(pg)
        print(f"5. {bad:24} -> 과목 {s3['subName']!r} 연도 {s3['year']!r} 기관 {s3['kind']!r}")

    # ---- 6. 내 과목 공유 링크 생성 (고3에서 시작하도록 저장값 초기화)
    pg.evaluate("localStorage.clear()")
    go()
    pg.select_option("#grp", label="과학탐구"); pg.select_option("#sub", label="생명과학Ⅰ")
    pg.click("#favToggle")
    pg.select_option("#grp", label="수학"); pg.select_option("#sub", label="미적분")
    pg.click("#favToggle")
    print("6. 공유 버튼 노출:", pg.is_visible("#favShare"))
    pg.click("#favShare")
    pg.wait_for_timeout(200)
    link = pg.evaluate("navigator.clipboard.readText()")
    print("   복사된 링크:", link.split("/")[-1])
    print("   안내:", pg.text_content("#noticeText")[:34])

    # ---- 7. import on another "device"
    ctx2 = b.new_context(viewport={"width": 412, "height": 900})
    pg2 = ctx2.new_page()
    pg2.on("pageerror", lambda e: errs.append(str(e)))
    pg2.goto(link, wait_until="domcontentloaded")
    pg2.wait_for_function("() => !!document.querySelector('.tally')", timeout=20000)
    print("7. 새 기기에서 열기 — 안내:", pg2.text_content("#noticeText")[:60])
    print("   해시 정리됨:", pg2.evaluate("location.hash"))
    pg2.click("#noticeYes")
    pg2.wait_for_timeout(120)
    print("   추가 결과:", pg2.eval_on_selector_all("#favBox .pill", "e=>e.map(x=>x.textContent)"))
    print("   저장됨:", pg2.evaluate("JSON.parse(localStorage.getItem('gijul.mysubs.v1')).length"), "개")

    # ---- 8a. 앱이 떠 있는 상태에서 같은 링크를 타고 들어옴 (같은 문서, hashchange)
    pg2.evaluate("location.hash = 'subs=D300.158,D300.140120'")
    pg2.wait_for_timeout(200)
    print("8a. 실행 중 같은 링크:", pg2.is_visible("#notice"), "|",
          pg2.text_content("#noticeText")[:40],
          "| 해시 정리:", pg2.evaluate("location.hash"))

    # ---- 8b. 실행 중 새 과목이 담긴 링크
    pg2.evaluate("location.hash = 'subs=D300.158,D200.17022'")
    pg2.wait_for_timeout(200)
    print("8b. 새 과목 1개 포함:", pg2.text_content("#noticeText")[:46])
    pg2.click("#noticeYes"); pg2.wait_for_timeout(150)
    print("    추가 후:", pg2.eval_on_selector_all("#favBox .pill", "e=>e.map(x=>x.textContent)"))

    # ---- 8c. 완전 새로고침으로 재방문해도 중복 추가 없음
    pg2.goto(URL, wait_until="domcontentloaded")
    pg2.goto(link, wait_until="domcontentloaded")
    pg2.wait_for_function("() => !!document.querySelector('.tally')", timeout=20000)
    print("8c. 새 문서로 재방문:", pg2.text_content("#noticeText")[:40],
          "| 개수 유지:", pg2.evaluate("JSON.parse(localStorage.getItem('gijul.mysubs.v1')).length"))

    # ---- 8d. 실행 중 화면 딥링크
    pg2.evaluate("location.hash = '/D300/140121/2019/gov'")
    pg2.wait_for_timeout(250)
    print("8d. 실행 중 화면 딥링크 ->", pg2.text_content(".tally .big"), "|",
          pg2.text_content(".tally .sm"))

    # ---- 9. 뒤로가기가 필터 이력에 갇히지 않는지 (replaceState)
    n = pg2.evaluate("history.length")
    pg2.select_option("#yr", index=1); pg2.wait_for_timeout(60)
    pg2.select_option("#grp", index=1); pg2.wait_for_timeout(60)
    print("9. 필터 3회 변경 후 history.length 증가:", pg2.evaluate("history.length") - n)

    print("ERRORS:", errs or "none")
    b.close()
