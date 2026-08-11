"""이미 받아둔 회차의 저장 단추가 잠기는가.

신고: 한 번 저장한 뒤에도 단추가 계속 눌리고 저장되는 것처럼 보인다. 실제로는
같은 폴더에 다시 담을 뿐이라 자료가 늘지 않는데, 화면은 '받는 중…'을 거쳐
성공한 것처럼 보였다. 앱 안에서만 판단할 수 있는 일이라 GijulNative를 흉내낸다.
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

# 앱인 척한다. listSaved()가 담아 둔 회차를 돌려주는 창구다 —
# 저장하면 __saved에 넣고 gijulSaveResult로 알린다.
STUB = """
window.__saved = [];
window.GijulNative = {
  systemDark:()=>false, where:()=>'/기출 직행',
  listSaved:()=>JSON.stringify(window.__saved),
  savePaper:(folder)=>{ window.__lastFolder = folder; },
  saveAll:(folder, json)=>{ window.__lastFolder = folder; },
  shareFile:()=>{}, openSaved:()=>{}, deleteSaved:()=>{},
  appVersion:()=>'{"code":38,"name":"4.7"}', checkUpdate:()=>{}, installUpdate:()=>{}
};
"""

def state(pg):
    return pg.evaluate("""()=>{const b=document.getElementById('sheetAll');
      return {label:b.textContent.trim(), disabled:b.disabled,
              kept:b.classList.contains('kept'),
              note:document.getElementById('sheetNote').textContent.trim()};}""")

def open_sheet(pg, n):
    pg.eval_on_selector_all(".item .send", f"e=>e[{n}].click()")
    pg.wait_for_selector("#sheet:not([hidden])")

with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path=CHROME)
    ctx = b.new_context(viewport={"width": 412, "height": 900}, service_workers="block")
    ctx.add_init_script(STUB)
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)[:140]))
    pg.goto(SITE, wait_until="load")
    pg.wait_for_selector(".item .send", timeout=25000)

    # 첫 회차의 폴더 이름을 앱이 이미 들고 있는 것처럼 만든다
    folder = pg.evaluate("""()=>{const r=ROWS[0];
      return `${r.y} ${r.title} ${r.sub}`.replace(/[\\/\\\\:*?"<>|\\x00-\\x1f]/g,'')
             .replace(/\\s+/g,' ').trim();}""")
    pg.evaluate("f=>{window.__saved=[{folder:f, name:'문제.pdf', size:1000}];}", folder)
    pg.evaluate("()=>{savedCache=null; render();}")
    print("1. 앱이 들고 있는 회차:", folder)

    open_sheet(pg, 0)
    s = state(pg)
    print(f"   그 회차의 단추: {s['label']!r} · 잠김 {s['disabled']} · 표시 {s['kept']}")
    print(f"   안내: {s['note'][:40]!r}")
    ck(s["disabled"], "이미 받아둔 회차인데 단추가 눌립니다")
    ck("이미" in s["label"], f"단추 글이 그대로입니다: {s['label']!r}")
    ck("이미" in s["note"], "안내가 이미 받아둔 것임을 말하지 않습니다")

    # 눌러도 아무 일이 없어야 한다
    before = pg.evaluate("()=>window.__lastFolder || ''")
    pg.eval_on_selector("#sheetAll", "e=>e.click()")
    pg.wait_for_timeout(300)
    after = pg.evaluate("()=>window.__lastFolder || ''")
    ck(before == after, "잠긴 단추를 눌렀는데 앱 창구가 불렸습니다")
    print("   눌러도 창구 호출 없음:", before == after)

    pg.keyboard.press("Escape"); pg.wait_for_timeout(200)

    # 아직 안 받은 회차는 그대로 눌려야 한다
    open_sheet(pg, 1)
    s = state(pg)
    print(f"2. 아직 안 받은 회차: {s['label']!r} · 잠김 {s['disabled']}")
    ck(not s["disabled"], "아직 받지 않은 회차인데 단추가 잠겨 있습니다")
    ck("이미" not in s["label"], "받지도 않았는데 이미 받았다고 합니다")

    # 저장이 끝나면 그 자리에서 잠겨야 한다
    f2 = pg.evaluate("""()=>{const r=sheetRow;
      return `${r.y} ${r.title} ${r.sub}`.replace(/[\\/\\\\:*?"<>|\\x00-\\x1f]/g,'')
             .replace(/\\s+/g,' ').trim();}""")
    pg.evaluate("f=>{window.__saved.push({folder:f, name:'문제.pdf', size:1000});"
                "window.gijulSaveResult(true, 3, '3개 담았습니다');}", f2)
    pg.wait_for_timeout(300)
    s = state(pg)
    print(f"3. 저장 직후: {s['label']!r} · 잠김 {s['disabled']}")
    ck(s["disabled"], "막 저장했는데 단추가 다시 눌립니다")

    print("   오류:", errs or "없음")
    b.close()

print("\n=== 문제:", "없음" if not BAD else "")
for x in BAD:
    print("  ★", x)
sys.exit(1 if BAD else 0)
