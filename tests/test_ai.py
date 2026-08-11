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

    # 주소와 그림 사이의 이름표 — 문장이 아니라 한 낱말이어야 한다
    lab = pg.eval_on_selector(".sai .lab", "e=>e.textContent.trim()")
    order = pg.evaluate("""()=>{const c=[...document.querySelector('.sai').children]
        .map(e=>e.className||e.tagName.toLowerCase());
        return [c.indexOf('box'), c.indexOf('lab'), c.findIndex(x=>x==='figure')];}""")
    print("5. 이름표:", repr(lab), "· 차례(주소·이름표·그림):", order)
    ck(lab == "사용 예", f"이름표가 {lab!r} 입니다")
    ck(order[0] < order[1] < order[2], f"이름표가 주소와 그림 사이에 있지 않습니다: {order}")

    cap = pg.eval_on_selector(".sai figcaption", "e=>e.textContent")
    ck("21학년도" in cap and "2020년" in cap, f"예시 설명이 이상합니다: {cap[:40]!r}")
    print("   설명:", cap[:46].replace("\n", " "))

    # 눌러서 크게 보기 — 패널에서는 작아서 글자가 안 읽힌다
    pg.click(".sai .zoom")
    pg.wait_for_selector(".lens:not([hidden])")
    big = pg.eval_on_selector(".lens img", "e=>Math.round(e.getBoundingClientRect().width)")
    scroll = pg.eval_on_selector(".lens", "e=>e.scrollWidth > e.clientWidth")
    covers = pg.evaluate("()=>{const l=document.querySelector('.lens').getBoundingClientRect();"
                         "return Math.round(l.width)===innerWidth && Math.round(l.height)===innerHeight;}")
    print(f"6. 크게 보기: {im['shown']}px → {big}px · 가로 스크롤 {scroll} · 화면 다 덮음 {covers}")
    ck(big > im["shown"] * 2, f"크게 보기가 {big}px — 패널의 {im['shown']}px와 별 차이가 없습니다")
    ck(scroll, "제 크기로 띄웠는데 좁은 화면에서 옆을 볼 수 없습니다")
    ck(covers, "겹판이 화면을 다 덮지 않습니다")

    # Esc는 겹판을 먼저 닫는다 — 시트가 먼저 닫히면 그림만 남는다
    pg.keyboard.press("Escape")
    pg.wait_for_timeout(300)
    ck(pg.is_hidden(".lens"), "Esc로 겹판이 닫히지 않습니다")
    ck(pg.is_visible("#sheet"), "겹판을 닫았는데 시트까지 닫혔습니다")
    ck(pg.evaluate("()=>document.activeElement.className") == "zoom",
       "겹판을 닫은 뒤 초점이 그림으로 돌아오지 않습니다")
    print("7. Esc — 겹판만 닫힘 · 시트 남음 · 초점 복귀")

    # 그림을 눌러도 닫힌다 (닫기 단추만으로는 손가락에 좁다)
    pg.click(".sai .zoom")
    pg.wait_for_selector(".lens:not([hidden])")
    pg.click(".lens img")
    pg.wait_for_timeout(300)
    ck(pg.is_hidden(".lens"), "그림을 눌러도 닫히지 않습니다")
    print("8. 그림을 눌러 닫힘")

    pg.keyboard.press("Escape")
    pg.wait_for_timeout(300)
    ck(pg.is_hidden("#sheet"), "Esc로 닫히지 않습니다")
    ck(pg.evaluate("()=>document.activeElement.id") == "aiBtn", "닫은 뒤 초점이 단추로 돌아오지 않습니다")
    print("9. Esc로 시트 닫힘 · 초점 복귀 정상")
    print("   오류:", errs or "없음")
    b.close()

print("\n=== 문제:", "없음" if not BAD else "")
for x in BAD:
    print("  ★", x)
sys.exit(1 if BAD else 0)
