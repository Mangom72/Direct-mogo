"""앱으로 넘기기: 자동으로는 절대 넘기지 않고, 누를 때만 넘어간다.

예전에는 안드로이드로 보이면 head에서 곧장 intent: 로 이동했다. 그 판정에
검색엔진 렌더러와 측정 도구까지 걸려 문서가 통째로 사라졌으므로 없앴다.
밖에서 온 링크는 App Links가 받고, 브라우저 안에서는 푸터 링크가 받는다.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from harness import CHROME, ROOT, SHOT, site, Serve
_srv, SITE = site()
from playwright.sync_api import sync_playwright
URL=SITE
UA="Mozilla/5.0 (Linux; Android 14; SM-S918N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Mobile Safari/537.36"
BOT=("Mozilla/5.0 (Linux; Android 6.0.1; Nexus 5X Build/MMB29P) AppleWebKit/537.36 (KHTML, like Gecko) "
     "Chrome/141.0.0.0 Mobile Safari/537.36 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)")
WIN="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
NATIVE=("window.GijulNative={systemDark:()=>false,listSaved:()=>'[]',savePaper:()=>{},shareFile:()=>{},"
        "openSaved:()=>{},deleteSaved:()=>{},where:()=>'/d',"
        "appVersion:()=>'{\"code\":28,\"name\":\"3.7\"}',checkUpdate:()=>{},installUpdate:()=>{}};")

def look(b, ua=UA, touch=True, pre=None):
    c=b.new_context(viewport={"width":412,"height":900},user_agent=ua,has_touch=touch,service_workers="block")
    if touch: c.add_init_script("Object.defineProperty(navigator,'maxTouchPoints',{get:()=>5});")
    if pre: c.add_init_script(pre)
    p=c.new_page(); p.goto(URL, wait_until="commit"); p.wait_for_timeout(2500)
    return c, p

with sync_playwright() as pw:
    b=pw.chromium.launch(executable_path=CHROME); ok=True
    print("1. 자동으로 넘어가지 않는다 (화면이 남아 있어야 한다)")
    for name, kw in [("안드로이드", dict()), ("Googlebot 스마트폰", dict(ua=BOT)),
                     ("윈도우", dict(ua=WIN, touch=False))]:
        c,p = look(b, **kw)
        alive = p.evaluate("()=>!!document.body")
        items = p.evaluate("()=>document.querySelectorAll('.item').length")
        good = alive and items > 0
        ok = ok and good
        print(f"   {name:<18} 살아있음 {alive!s:<5} 회차 {items:<4} → {'통과' if good else '★어긋남★'}")
        c.close()

    print("2. 누를 자리는 있다")
    c,p = look(b)
    href = p.eval_on_selector("#appInfo a", "a=>a.getAttribute('href')")
    shown = not p.eval_on_selector("#appInfo", "e=>e.hidden")
    good = shown and href.startswith("intent://") and "kr.gijul.direct" in href
    ok = ok and good
    print(f"   푸터 '앱으로 열기' 보임 {shown} · intent 주소 {good} → {'통과' if good else '★어긋남★'}")
    print("   막대 문구:", repr(p.text_content("#noticeText")))
    c.close()

    print("3. 앱 안에서는 권하지 않는다")
    c,p = look(b, pre=NATIVE)
    hid = p.eval_on_selector("#appInfo", "e=>e.innerHTML.indexOf('앱으로 열기')<0")
    ok = ok and hid
    print(f"   '앱으로 열기' 없음 {hid} → {'통과' if hid else '★어긋남★'}")
    c.close()
    print("\n전체:", "통과" if ok else "실패")
    b.close()
