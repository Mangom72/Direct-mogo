"""앱 뒤로가기 — 열어 둔 것부터 하나씩 닫고, 마지막에만 종료로 넘어간다.

앱은 뒤로가기를 받으면 먼저 페이지의 gijulBack()을 부른다. 무언가 닫았으면
true가 돌아오고 앱은 거기서 멈춘다. false 일 때만 '한 번 더 누르면 종료'로 간다.
그러니 여기서 지킬 것은 **무엇을 닫았을 때 true 가 나오는가**이다 — 닫을 것이
있는데 false 가 나오면 그 뒤로가기가 앱을 끄게 된다.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from harness import CHROME, ROOT, SHOT, site, Serve
_srv, SITE = site()
from playwright.sync_api import sync_playwright

BAD = []
def ck(cond, msg):
    if not cond:
        BAD.append(msg)

AND = ("Mozilla/5.0 (Linux; Android 14; SM-S918N) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/150 Mobile Safari/537.36")

def back(pg):
    return pg.evaluate("()=>window.gijulBack()")

with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path=CHROME)
    ctx = b.new_context(viewport={"width": 412, "height": 900}, service_workers="block")
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)[:140]))
    pg.goto(SITE, wait_until="load")
    pg.wait_for_selector(".item", timeout=25000)

    # 닫을 것이 없으면 앱에 넘긴다
    r = back(pg)
    print("1. 아무것도 안 열린 상태:", r, "(False여야 앱이 종료 절차로 갑니다)")
    ck(r is False, "닫을 것이 없는데 뒤로가기를 삼켰습니다 — 앱이 영영 안 꺼집니다")

    # 시트 하나
    pg.click(".item .send >> nth=0")
    pg.wait_for_selector("#sheet:not([hidden])")
    ck(back(pg) is True, "시트가 열려 있는데 뒤로가기가 그냥 넘어갑니다")
    pg.wait_for_timeout(200)
    ck(pg.is_hidden("#sheet"), "뒤로가기로 시트가 닫히지 않습니다")
    print("2. 시트 — 한 번에 닫힘")

    # 겹쳐 있으면 위에서부터
    pg.click("#aiBtn")
    pg.wait_for_selector("#sheet:not([hidden])")
    pg.wait_for_function("()=>{const i=document.querySelector('.sai img');return i&&i.complete;}", timeout=20000)
    pg.click(".sai .zoom")
    pg.wait_for_selector(".lens:not([hidden])")
    ck(back(pg) is True, "크게 보기가 떠 있는데 뒤로가기가 넘어갑니다")
    pg.wait_for_timeout(200)
    ck(pg.is_hidden(".lens"), "뒤로가기로 크게 보기가 닫히지 않습니다")
    ck(pg.is_visible("#sheet"), "크게 보기를 닫으면서 시트까지 닫혔습니다")
    ck(back(pg) is True, "시트가 남았는데 뒤로가기가 넘어갑니다")
    pg.wait_for_timeout(200)
    ck(pg.is_hidden("#sheet"), "두 번째 뒤로가기로 시트가 닫히지 않습니다")
    ck(back(pg) is False, "다 닫았는데도 뒤로가기를 삼킵니다")
    print("3. 겹판 → 시트 → 앱으로, 한 번에 하나씩")

    # 내 과목 편집 모드
    pg.click("#favToggle")                        # ★로 하나 담아 편집 단추를 띄운다
    pg.wait_for_timeout(200)
    if pg.is_visible("#favEdit"):
        pg.click("#favEdit")
        pg.wait_for_timeout(150)
        on = pg.eval_on_selector("#favBox", "e=>e.classList.contains('editing')")
        ck(on, "편집 모드로 들어가지 못했습니다")
        ck(back(pg) is True, "편집 중인데 뒤로가기가 넘어갑니다")
        pg.wait_for_timeout(200)
        off = pg.eval_on_selector("#favBox", "e=>!e.classList.contains('editing')")
        ck(off, "뒤로가기로 편집이 끝나지 않습니다")
        print("4. 내 과목 편집 — 한 번에 빠져나옴")
    ctx.close()

    # 알림 막대 — 뒤로가기는 '아니오'가 아니다
    ctx = b.new_context(viewport={"width": 412, "height": 900}, user_agent=AND,
                        has_touch=True, service_workers="block")
    ctx.add_init_script("Object.defineProperty(navigator,'maxTouchPoints',{get:()=>5});")
    pg = ctx.new_page()
    pg.on("pageerror", lambda e: errs.append(str(e)[:140]))
    pg.goto(SITE, wait_until="load")
    pg.wait_for_selector("#notice:not([hidden])", timeout=20000)
    pg.wait_for_selector(".item", timeout=25000)
    ck(back(pg) is True, "알림 막대가 떠 있는데 뒤로가기가 넘어갑니다")
    pg.wait_for_timeout(200)
    ck(pg.evaluate("()=>document.getElementById('notice').hidden"), "뒤로가기로 막대가 닫히지 않습니다")
    kept = pg.evaluate("()=>localStorage.getItem('gijul.apk.v1')")
    print("5. 알림 막대 — 닫힘 · 기억된 답:", repr(kept), "(None이어야 합니다)")
    ck(kept is None, "뒤로가기를 '다시 묻지 마'로 새겼습니다 — 그건 사용자가 고른 답이 아닙니다")
    print("   오류:", errs or "없음")
    b.close()

print("\n=== 문제:", "없음" if not BAD else "")
for x in BAD:
    print("  ★", x)
sys.exit(1 if BAD else 0)
