"""내 과목 순서 바꾸기 — 끌어서, 그리고 키보드로."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from harness import CHROME, ROOT, SHOT, site, Serve
_srv, SITE = site()
from playwright.sync_api import sync_playwright

URL = SITE
SHOT = str(SHOT) + "/"

HOLD = 0.55  # > HOLD_MS (400)

def order(pg):
    return pg.eval_on_selector_all("#favBox .pill", "e=>e.map(x=>x.dataset.s)")

def names(pg):
    return pg.eval_on_selector_all("#favBox .pill",
        "e=>e.map(x=>x.textContent.replace('×',''))")

def stored(pg):
    return pg.evaluate("JSON.parse(localStorage.getItem('gijul.mysubs.v1')||'[]').map(f=>f.s)")

def add(pg, grp, sub):
    pg.select_option("#grp", label=grp)
    pg.select_option("#sub", label=sub)
    pg.click("#favToggle")

def center(pg, i):
    box = pg.locator("#favBox .pill").nth(i).bounding_box()
    return box["x"] + box["width"] / 2, box["y"] + box["height"] / 2

def drag(pg, src, dst, hold=HOLD, steps=14):
    """Long-press pill at index src, then move onto pill at index dst."""
    sx, sy = center(pg, src)
    dx, dy = center(pg, dst)
    pg.mouse.move(sx, sy)
    pg.mouse.down()
    pg.wait_for_timeout(int(hold * 1000))
    for k in range(1, steps + 1):
        pg.mouse.move(sx + (dx - sx) * k / steps, sy + (dy - sy) * k / steps)
    pg.wait_for_timeout(60)
    pg.mouse.up()
    pg.wait_for_timeout(60)

with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path=CHROME)
    ctx = b.new_context(viewport={"width": 412, "height": 900}, device_scale_factor=2,
                        service_workers="block")
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("console", lambda m: errs.append("console:" + m.text)
          if m.type == "error" and "ERR_CONNECTION" not in m.text else None)
    pg.goto(URL, wait_until="domcontentloaded")
    pg.wait_for_selector(".item", timeout=20000)

    # 4 subjects: 화법과 작문, 미적분, 생명과학Ⅰ, 한국사
    add(pg, "국어", "화법과 작문")
    add(pg, "수학", "미적분")
    add(pg, "과학탐구", "생명과학Ⅰ")
    add(pg, "영어·한국사", "한국사")
    print("0. 초기:", names(pg))
    base = order(pg)

    # ---- 1. edit mode UI
    pg.click("#favEdit")
    print("1. 편집 진입 — 힌트:", pg.is_visible("#favHint"),
          "| 버튼:", pg.text_content("#favEdit"),
          "| touch-action:", pg.eval_on_selector("#favBox .pill",
              "e=>getComputedStyle(e).touchAction"))

    # ---- 2. drag first pill to the end
    drag(pg, 0, 3)
    got = order(pg)
    exp = base[1:] + [base[0]]
    print("2. 0->끝:", names(pg), "| DOM맞음:", got == exp, "| 저장됨:", stored(pg) == got)

    # ---- 3. drag it back to the front
    drag(pg, 3, 0)
    print("3. 끝->0:", names(pg), "| 원복:", order(pg) == base, "| 저장됨:", stored(pg) == base)

    # ---- 4. adjacent swap
    drag(pg, 1, 2)
    exp = [base[0], base[2], base[1], base[3]]
    print("4. 1<->2:", names(pg), "| 맞음:", order(pg) == exp, "| 저장됨:", stored(pg) == order(pg))

    # ---- 5. long-press then release in place must NOT delete
    n = len(order(pg))
    sx, sy = center(pg, 0)
    pg.mouse.move(sx, sy); pg.mouse.down(); pg.wait_for_timeout(600); pg.mouse.up()
    pg.wait_for_timeout(80)
    print("5. 꾹 눌렀다 제자리 놓기 — 개수 유지:", len(order(pg)) == n,
          "| 순서 유지:", order(pg) == exp)

    # ---- 6. quick tap still deletes
    doomed = order(pg)[1]
    sx, sy = center(pg, 1)
    pg.mouse.move(sx, sy); pg.mouse.down(); pg.wait_for_timeout(60); pg.mouse.up()
    pg.wait_for_timeout(80)
    print("6. 짧은 탭 삭제:", doomed not in order(pg), "|", names(pg),
          "| 저장됨:", stored(pg) == order(pg))

    # ---- 7. keyboard reorder
    pg.eval_on_selector("#favBox .pill", "e=>e.focus()")
    before = order(pg)
    pg.keyboard.press("ArrowRight")
    pg.wait_for_timeout(60)
    after_r = order(pg)
    focused_ok = pg.evaluate("document.activeElement.dataset.s") == before[0]
    pg.keyboard.press("ArrowLeft")
    pg.wait_for_timeout(60)
    print("7. →:", after_r == [before[1], before[0]] + before[2:],
          "| 포커스 따라감:", focused_ok, "| ←로 원복:", order(pg) == before)
    pg.keyboard.press("ArrowLeft")   # 맨 앞에서 더 왼쪽 — 무시되어야
    pg.wait_for_timeout(60)
    print("   맨 앞에서 ← 무시:", order(pg) == before)

    pg.screenshot(path=SHOT + "shot-drag.png", clip={"x": 0, "y": 150, "width": 412, "height": 330})

    # ---- 8. leaving edit mode ends drag state; pills select again
    pg.click("#favEdit")
    print("8. 편집 종료 — 힌트 숨김:", pg.is_hidden("#favHint"),
          "| dragging 잔여:", pg.eval_on_selector_all("#favBox .dragging", "e=>e.length"),
          "| transform 잔여:", pg.eval_on_selector_all("#favBox .pill",
              "e=>e.filter(x=>x.style.transform).length"))
    pg.click("#favBox .pill >> nth=1")
    pg.wait_for_timeout(120)
    print("   알약 선택 정상:", pg.text_content(".tally .big"))

    # ---- 9. order survives reload
    final = order(pg)
    pg.reload(wait_until="domcontentloaded")
    pg.wait_for_selector(".item", timeout=20000)
    print("9. 새로고침 후 순서 유지:", order(pg) == final, "|", names(pg))

    print("ERRORS:", errs or "none")
    b.close()
