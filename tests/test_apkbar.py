"""앱 권유 막대가 첫 그림부터 떠 있을 때, 뒤에 오는 알림이 삼켜지지 않는가."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from harness import CHROME, ROOT, SHOT, site, Serve
_srv, SITE = site()
from playwright.sync_api import sync_playwright

AND="Mozilla/5.0 (Linux; Android 14; SM-S918N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150 Mobile Safari/537.36"
WIN="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150 Safari/537.36"
SUBS="#subs=D300.140117-D300.140119-D300.80003"
NATIVE=("window.GijulNative={systemDark:()=>false,listSaved:()=>'[]',savePaper:()=>{},shareFile:()=>{},"
        "openSaved:()=>{},deleteSaved:()=>{},where:()=>'/d',"
        "appVersion:()=>'{\"code\":28,\"name\":\"3.7\"}',checkUpdate:()=>{},installUpdate:()=>{}};")
def ctxof(b, ua=AND, pre=None):
    c=b.new_context(viewport={"width":412,"height":900}, user_agent=ua, has_touch=True, service_workers="block")
    c.add_init_script("Object.defineProperty(navigator,'maxTouchPoints',{get:()=>5});")
    if pre: c.add_init_script(pre)
    return c
ok=True
with sync_playwright() as pw:
    b=pw.launch=pw.chromium.launch(executable_path=CHROME)

    print("1. 첫 그림에 이미 떠 있는가")
    c=ctxof(b); p=c.new_page(); p.goto(SITE, wait_until="commit")
    early = p.evaluate("()=>{const n=document.getElementById('notice');return n && !n.hidden ? document.getElementById('noticeText').textContent.slice(0,20) : null}")
    print(f"   파싱 직후 막대: {early!r}"); ok = ok and bool(early)
    p.wait_for_timeout(2500)
    still = p.evaluate("()=>!document.getElementById('notice').hidden")
    print(f"   스크립트가 다 돈 뒤에도 떠 있음: {still}"); ok = ok and still
    c.close()

    print("2. 막대가 떠 있는데 링크로 과목이 오면")
    c=ctxof(b); p=c.new_page(); p.goto(SITE+SUBS, wait_until="load"); p.wait_for_timeout(2500)
    first = p.text_content("#noticeText")
    print(f"   먼저 뜬 것: {first[:24]!r}")
    p.click("#noticeNo")                      # 앱 권유를 닫는다
    p.wait_for_timeout(400)
    second = p.evaluate("()=>{const n=document.getElementById('notice');return n.hidden?null:document.getElementById('noticeText').textContent}")
    good = bool(second) and "과목 3개" in (second or "")
    ok = ok and good
    print(f"   닫으니 뒤엣것이 나옴: {second[:38] if second else None!r} → {'통과' if good else '★어긋남★'}")
    p.click("#noticeYes"); p.wait_for_timeout(400)
    pills = p.eval_on_selector_all("#favBox .pill", "e=>e.map(x=>x.textContent)")
    print(f"   추가 결과 알약 {len(pills)}개: {pills}"); ok = ok and len(pills)==3
    c.close()

    print("3. 닫으면 다시 안 뜬다")
    c=ctxof(b); p=c.new_page(); p.goto(SITE, wait_until="load"); p.wait_for_timeout(2000)
    p.click("#noticeNo"); p.wait_for_timeout(300)
    p.reload(wait_until="commit"); p.wait_for_timeout(1500)
    again = p.evaluate("()=>!document.getElementById('notice').hidden")
    print(f"   새로고침 뒤 떠 있음: {again} (False여야 함)"); ok = ok and not again
    c.close()

    print("4. 해당 없는 경우")
    for name, kw in (("윈도우", dict(ua=WIN)), ("앱 안(네이티브)", dict(pre=NATIVE))):
        c=ctxof(b, **kw); p=c.new_page(); p.goto(SITE, wait_until="load"); p.wait_for_timeout(2000)
        shown = p.evaluate("()=>!document.getElementById('notice').hidden")
        print(f"   {name:<12} 막대 {shown} (False여야 함)"); ok = ok and not shown
        c.close()
    print("\n전체:", "통과" if ok else "실패")
