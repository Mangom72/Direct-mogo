"""홈 화면 웹 앱 권유(iPhone·iPad) — 안드로이드 APK 권유와 같은 자리, 같은 방식.

iOS 에는 받을 앱이 없다. 대신 '공유 → 홈 화면에 추가'가 이쪽의 설치이고,
그렇게 넣어야 저장소가 이레 만에 지워지지 않는다.

여기서 지키는 것 넷.
  - iPhone·iPad 에서만 뜬다. 안드로이드·데스크톱에는 안 뜬다.
  - **저장소가 사파리와 갈린다는 말이 반드시 함께 나간다.** 모르고 옮기면
    표시해 둔 것이 통째로 사라진 것처럼 보인다 — 사고 예방이다.
  - 이미 홈 화면에서 열렸으면 권하지 않는다.
  - 한 번 닫으면 다시 안 뜬다.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from harness import CHROME, ROOT, SHOT, site, Serve
_srv, SITE = site()
from playwright.sync_api import sync_playwright
URL = SITE

IPHONE = ("Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 "
          "(KHTML, like Gecko) Version/18.5 Mobile/15E148 Safari/604.1")
# iPadOS 는 기본이 '데스크톱 화면'이라 UA 에 iPad 가 없고 맥으로 보인다
IPAD_DESK = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
             "(KHTML, like Gecko) Version/18.5 Safari/605.1.15")
ANDROID = ("Mozilla/5.0 (Linux; Android 14; SM-S918N) AppleWebKit/537.36 (KHTML, like Gecko) "
           "Chrome/126 Mobile Safari/537.36")
MAC = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
       "Chrome/126 Safari/537.36")

def look(b, ua=IPHONE, touch=5, home=False, seen=None):
    c = b.new_context(viewport={"width": 402, "height": 874}, user_agent=ua,
                      has_touch=touch > 0, service_workers="block")
    c.add_init_script(f"Object.defineProperty(navigator,'maxTouchPoints',{{get:()=>{touch}}});")
    if home:
        # 홈 화면에서 열린 웹 앱 — iOS 의 옛 깃발과 표준 질의를 둘 다 세운다
        c.add_init_script(
            "Object.defineProperty(navigator,'standalone',{get:()=>true});"
            "const mm=window.matchMedia;window.matchMedia=q=>q.includes('standalone')"
            "?{matches:true,media:q,addListener(){},removeListener(){},addEventListener(){},"
            "removeEventListener(){}}:mm.call(window,q);")
    if seen:
        c.add_init_script(f"try{{localStorage.setItem('{seen}','off');}}catch(e){{}}")
    p = c.new_page()
    p.goto(URL, wait_until="commit")
    p.wait_for_timeout(2600)
    return c, p

def bar(p):
    if p.eval_on_selector("#notice", "e=>e.hidden"):
        return None
    return p.text_content("#noticeText")

with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path=CHROME)
    ok = True

    print("1. 어디에 뜨는가")
    for name, kw, want in [("iPhone", dict(), True),
                           ("iPad(데스크톱 화면)", dict(ua=IPAD_DESK), True),
                           ("안드로이드", dict(ua=ANDROID), False),
                           ("맥(터치 없음)", dict(ua=MAC, touch=0), False)]:
        c, p = look(b, **kw)
        t = bar(p) or ""
        got = "홈 화면에 추가" in t
        good = got == want
        ok = ok and good
        print(f"   {name:<18} 막대 {('홈 화면' if got else ('앱 받기' if '앱' in t else '없음')):<7}"
              f" → {'통과' if good else '어긋남'}")
        c.close()

    print("2. 저장소가 갈린다는 말이 함께 나간다")
    c, p = look(b)
    p.click("#noticeYes")
    steps = p.text_content("#noticeText")
    has_how = "공유" in steps and "홈 화면에 추가" in steps
    has_warn = "따라오지 않습니다" in steps and "백업" in steps
    hid = p.eval_on_selector("#noticeYes", "e=>e.hidden")
    ok = ok and has_how and has_warn and hid
    print("   방법 두 단계:", has_how, "| 기록이 안 따라온다는 경고:", has_warn,
          "| '방법 보기'는 물러남:", hid)
    print("  ", steps[:52].replace("\n", " "), "…")
    c.close()

    print("3. 푸터에도 늘 있다")
    c, p = look(b, seen="gijul.pwa.v1")
    shown = not p.eval_on_selector("#appInfo", "e=>e.hidden")
    txt = p.text_content("#appInfo")
    good = shown and "홈 화면에 추가" in txt and "따라오지 않으니" in txt
    ok = ok and good
    print("   막대를 닫아도 푸터는 남음:", shown, "| 경고 포함:", "따라오지 않으니" in txt,
          "| 막대는 다시 안 뜸:", bar(p) is None)
    ok = ok and bar(p) is None
    c.close()

    print("4. 이미 홈 화면에서 열렸으면 권하지 않는다")
    c, p = look(b, home=True)
    txt = p.text_content("#appInfo")
    quiet = bar(p) is None
    tells = "홈 화면 앱으로 열렸습니다" in txt
    ok = ok and quiet and tells
    print("   막대 없음:", quiet, "| 대신 어디에 담기는지 밝힘:", tells)
    print("  ", txt[:46], "…")
    c.close()

    print("5. 데스크톱에 설치한 웹 앱은 이 안내를 안 받는다")
    c, p = look(b, ua=MAC, touch=0, home=True)
    hidden = p.eval_on_selector("#appInfo", "e=>e.hidden")
    ok = ok and hidden
    print("   저장소가 갈리지 않는 곳이므로 조용함:", hidden)
    c.close()

    print("전체:", "통과" if ok else "실패")
    b.close()
