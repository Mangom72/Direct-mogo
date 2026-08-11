"""AI로 쓰기 — 주소를 복사할 수 있고, 예가 실제로 보이는가.

이 화면은 자료를 압축해 품고 있어 AI가 그대로 읽지 못한다. 같은 자료를 스크립트
없이 읽히는 /s/ 로도 내는데, 그 사실을 알 방법이 없어 각주에 단추로 두었다.
주된 쓰임이 아니므로 '있는지'와 '망가지지 않았는지'만 지킨다.
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

with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path=CHROME)
    ctx = b.new_context(viewport={"width": 412, "height": 900}, service_workers="block")
    ctx.grant_permissions(["clipboard-read", "clipboard-write"])
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)[:140]))
    pg.on("console", lambda m: errs.append(m.type + ": " + m.text[:110]) if m.type == "error" else None)
    pg.goto(SITE, wait_until="load")
    pg.wait_for_selector("#aiBtn", timeout=20000)

    # 각주에 있고, 주된 자리를 차지하지 않는다
    where = pg.eval_on_selector("#aiBtn", "e=>!!e.closest('footer')")
    ck(where, "AI 단추가 각주 밖에 있습니다 — 주된 자리에 두지 않기로 했습니다")
    print("1. 각주 안에 있음:", where)

    pg.click("#aiBtn")
    pg.wait_for_selector("#sheet:not([hidden])")
    ck(pg.is_hidden("#sheetAll"), "안내인데 저장 단추가 보입니다")

    url = pg.eval_on_selector(".sai input", "e=>e.value")
    ro = pg.eval_on_selector(".sai input", "e=>e.readOnly")
    print("2. 주소:", url, "· 읽기 전용", ro)
    ck(url.endswith("/Direct-mogo/s/"), f"건네는 주소가 {url!r} 입니다")
    ck(ro, "주소 칸이 고쳐질 수 있습니다")

    # 눌러 고르기 — 복사가 막혀도 손으로 긁을 수 있어야 한다
    pg.click(".sai input")
    picked = pg.evaluate("()=>{const i=document.querySelector('.sai input');"
                         "return i.value.slice(i.selectionStart, i.selectionEnd);}")
    ck(picked == url, f"눌렀는데 전체가 골라지지 않습니다: {picked!r}")

    pg.click(".sai .box button")
    pg.wait_for_timeout(400)
    label = pg.eval_on_selector(".sai .box button", "e=>e.textContent")
    clip = pg.evaluate("()=>navigator.clipboard.readText()")
    print("3. 복사 뒤 단추:", repr(label), "· 클립보드:", clip)
    ck("복사했" in label, f"복사하고도 아무 말이 없습니다: {label!r}")
    ck(clip == url, f"클립보드에 {clip!r} 이 들어갔습니다")

    # 예시 그림이 실제로 뜨는가 (주소만 적어 두고 파일이 없으면 빈 칸이 된다)
    pg.wait_for_function("()=>{const i=document.querySelector('.sai img');"
                         "return i && i.complete;}", timeout=20000)
    im = pg.eval_on_selector(".sai img", """e=>({w:e.naturalWidth, alt:(e.alt||'').length,
        src:e.getAttribute('src'), shown:Math.round(e.getBoundingClientRect().width)})""")
    print("4. 그림:", im)
    ck(im["w"] > 0, f"예시 그림이 뜨지 않습니다 ({im['src']})")
    ck(im["alt"] > 20, "그림에 설명이 없습니다 — 화면을 못 보는 사람에게는 빈 자리입니다")
    ck(im["shown"] > 200, f"그림이 {im['shown']}px로 그려집니다")

    cap = pg.eval_on_selector(".sai figcaption", "e=>e.textContent")
    ck("21학년도" in cap and "2020년" in cap, f"예시 설명이 이상합니다: {cap[:40]!r}")
    print("5. 설명:", cap[:46].replace("\n", " "))

    pg.keyboard.press("Escape")
    pg.wait_for_timeout(300)
    ck(pg.is_hidden("#sheet"), "Esc로 닫히지 않습니다")
    ck(pg.evaluate("()=>document.activeElement.id") == "aiBtn", "닫은 뒤 초점이 단추로 돌아오지 않습니다")
    print("6. Esc로 닫힘 · 초점 복귀 정상")
    print("   오류:", errs or "없음")
    b.close()

print("\n=== 문제:", "없음" if not BAD else "")
for x in BAD:
    print("  ★", x)
sys.exit(1 if BAD else 0)
