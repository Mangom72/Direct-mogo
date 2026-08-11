"""화면 테마 — 자동·밝게·어둡게, 그리고 어두운 화면의 글자 대비."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from harness import CHROME, ROOT, SHOT, site, Serve
_srv, SITE = site()
from playwright.sync_api import sync_playwright

URL = SITE
SHOT = str(SHOT) + "/"

# Contrast of every foreground role against the surfaces it actually sits on.
CONTRAST = """() => {
  const cs = getComputedStyle(document.documentElement);
  const v = n => cs.getPropertyValue(n).trim();
  const lum = h => {
    const c = h.replace('#','');
    const p = c.length === 3 ? [...c].map(x=>x+x) : c.match(/../g);
    const [r,g,b] = p.map(x=>{ const s = parseInt(x,16)/255;
      return s <= 0.03928 ? s/12.92 : Math.pow((s+0.055)/1.055, 2.4); });
    return 0.2126*r + 0.7152*g + 0.0722*b;
  };
  const ratio = (a,b) => { const [x,y]=[lum(a),lum(b)].sort((m,n)=>n-m);
    return Math.round(((x+0.05)/(y+0.05))*100)/100; };
  const pairs = [
    ['ink','card'], ['ink2','card'], ['mark','card'], ['gov','card'], ['edu','card'],
    ['ink','paper'], ['ink2','paper'], ['ink','btn'], ['off','card'],
  ];
  const out = {};
  for (const [f,b] of pairs) out[f+' on '+b] = ratio(v('--'+f), v('--'+b));
  out['onmark on mark'] = ratio(v('--onmark'), v('--mark'));
  out['card on ink'] = ratio(v('--card'), v('--ink'));   // 반전 칩
  return out;
}"""

def check(pg, label):
    r = pg.evaluate(CONTRAST)
    bad = {k: x for k, x in r.items() if x < 4.5 and not k.startswith('off')}
    weak = {k: x for k, x in r.items() if k.startswith('off')}
    print(f"  {label}: 최저 {min(r.values())} | 4.5 미만(비활성 제외): {bad or '없음'}")
    print(f"    비활성 텍스트: {weak}")
    return bad

with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path=CHROME)
    fails = []

    # ---- 1. OS 다크 선호 -> 자동으로 어둡게
    ctx = b.new_context(viewport={"width": 412, "height": 900}, color_scheme="dark",
                        device_scale_factor=2)
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(URL, wait_until="domcontentloaded")
    pg.wait_for_selector(".item", timeout=20000)
    print("1. OS=dark, 저장값 없음 -> data-theme:",
          pg.evaluate("document.documentElement.dataset.theme"),
          "| 버튼:", pg.text_content("#thLab"),
          "| theme-color:", pg.get_attribute('meta[name=theme-color]', "content"))
    fails += check(pg, "다크 대비")
    pg.screenshot(path=SHOT + "shot-dark.png", clip={"x":0,"y":0,"width":412,"height":760})

    # ---- 2. 토글 순환 + 저장
    seq = []
    for _ in range(3):
        pg.click("#thBtn")
        seq.append((pg.text_content("#thLab"),
                    pg.evaluate("document.documentElement.dataset.theme")))
    print("2. 토글 순환:", seq)
    pg.click("#thBtn")  # -> 밝게
    pref = pg.evaluate("localStorage.getItem('gijul.theme.v1')")
    pg.reload(wait_until="domcontentloaded")
    pg.wait_for_selector(".item", timeout=20000)
    print("   저장값:", pref, "| 새로고침 후:",
          pg.evaluate("document.documentElement.dataset.theme"),
          "| OS는 dark인데 수동 밝게 유지:",
          pg.evaluate("document.documentElement.dataset.theme") == "light")
    print("   theme-color:", pg.get_attribute('meta[name=theme-color]', "content"))
    fails += check(pg, "라이트 대비")

    # ---- 3. 첫 페인트 전 적용 (흰 섬광 없음)
    early = pg.evaluate("""() => {
        // <head> 안 스크립트가 <body> 파싱 전에 돌았는지: style 태그 뒤, body 앞
        const s = [...document.querySelectorAll('head script')];
        return s.length > 0 && document.documentElement.hasAttribute('data-theme');
    }""")
    print("3. head에서 선적용:", early)

    # ---- 4. 자동 모드에서 OS 변경 추종
    pg.evaluate("localStorage.setItem('gijul.theme.v1','auto')")
    pg.reload(wait_until="domcontentloaded")
    pg.wait_for_selector(".item", timeout=20000)
    a = pg.evaluate("document.documentElement.dataset.theme")
    pg.emulate_media(color_scheme="light")
    pg.wait_for_timeout(120)
    bb = pg.evaluate("document.documentElement.dataset.theme")
    pg.emulate_media(color_scheme="dark")
    pg.wait_for_timeout(120)
    c = pg.evaluate("document.documentElement.dataset.theme")
    print(f"4. 자동 추종: dark={a} -> light={bb} -> dark={c}",
          "| 통과:", (a, bb, c) == ("dark", "light", "dark"))

    # ---- 5. 손상된 저장값
    pg.evaluate("localStorage.setItem('gijul.theme.v1','쓰레기값')")
    pg.reload(wait_until="domcontentloaded")
    pg.wait_for_selector(".item", timeout=20000)
    print("5. 손상값 -> 라벨:", pg.text_content("#thLab"),
          "| theme:", pg.evaluate("document.documentElement.dataset.theme"))

    # ---- 6. 리터럴 색 잔존 여부 (변수화 누락 탐지)
    leftover = pg.evaluate("""() => {
        const bad = [];
        for (const el of document.querySelectorAll('*')) {
            const s = getComputedStyle(el);
            if (s.backgroundColor === 'rgb(255, 255, 255)') bad.push(el.className || el.tagName);
        }
        return [...new Set(bad)].slice(0, 8);
    }""")
    print("6. 다크에서 흰 배경 잔존:", leftover or "없음")

    print("ERRORS:", errs or "none")
    print("=== 대비 실패:", fails or "없음", "===")
    b.close()
