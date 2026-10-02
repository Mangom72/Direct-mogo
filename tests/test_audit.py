"""권한 수신 ACK, 비동기 시트, 달력 경계와 좁은 창의 회귀 시험."""
import pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from harness import CHROME, site
from playwright.sync_api import sync_playwright
_srv, SITE = site()

with sync_playwright() as pw:
    browser = pw.chromium.launch(executable_path=CHROME)
    context = browser.new_context(viewport={"width": 300, "height": 700}, service_workers="block")
    context.add_init_script("""
      window.__pending=[]; window.__acks=[];
      window.GijulNative={systemDark:()=>false,setSolved:()=>{},
        peekTimings:()=>JSON.stringify(window.__pending),
        ackTimings:s=>{window.__acks.push(JSON.parse(s)); if(!window.__failAck) window.__pending=[];}};
    """)
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(SITE + "#%bad%", wait_until="load")
    page.wait_for_selector(".item .chk")
    assert not errors, errors
    key = page.eval_on_selector(".item .chk", "e=>e.dataset.k")
    page.evaluate("""k=>{
      __pending=[{id:'a',k,spent:600,limit:1200}];
      window.__setItem=Storage.prototype.setItem;
      Storage.prototype.setItem=function(k,v){if(k==='gijul.times.v1')throw new Error('full'); return __setItem.call(this,k,v);};
      takeTimings();
    }""", key)
    assert page.evaluate("__acks.length") == 0, "저장 실패 전에 ACK했습니다"
    page.evaluate("Storage.prototype.setItem=__setItem; __failAck=true; takeTimings();")
    assert page.evaluate("__acks.length") == 1
    page.evaluate("k=>{TIMES[k].spent=777; saveTimes(); __failAck=false; takeTimings();}", key)
    assert page.evaluate("k=>TIMES[k].spent", key) == 777, "재전송이 수동 수정 시간을 덮었습니다"
    assert page.evaluate("__pending.length") == 0
    page.evaluate("()=>{openCal(null);calCur=new Date(2026,2,1);calSel='20260331';drawCal();}")
    page.locator('#calGrid .cell[data-k="20260331"]').focus()
    page.keyboard.press("PageUp")
    assert page.evaluate("calSel") == "20260228", "31일에서 이전 달을 건너뛰었습니다"
    page.keyboard.press("PageDown")
    assert page.evaluate("calSel") == "20260328"
    page.evaluate("closeCal()")
    # 늦게 도착한 네트워크 응답은 새 시트에 쓸 수 없어야 한다.
    page.evaluate("""()=>{
      window.__oldFetch=window.fetch;
      window.fetch=()=>new Promise(resolve=>{(window.__fetchWaiters ||= []).push(resolve)});
      openLog(null); closeSheet(); openBackup(null);
      for(const resolve of __fetchWaiters)resolve({ok:true,json:async()=>[]});
      window.fetch=__oldFetch;
    }""")
    page.wait_for_timeout(300)
    assert page.locator("#sheetNm").text_content() == "백업"
    assert page.locator("#sheetList").get_by_text("내보내기", exact=True).count() == 1
    assert page.evaluate("document.body.style.overflow") == "hidden"
    assert page.evaluate("!!document.querySelector('main').closest('[inert]')")
    page.evaluate("closeSheet()")
    assert page.evaluate("document.body.style.overflow") == ""
    page.locator(".record").first.click()
    # 새 입력 필드도 modal의 Tab 순환에 들어가야 한다.
    page.locator("#sheetList input").first.focus()
    page.keyboard.press("Tab")
    assert page.evaluate("document.activeElement.tagName") == "INPUT"
    page.evaluate("closeSheet()")
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), "300px 창을 넘칩니다"
    assert not errors, errors
    recovery_context = browser.new_context(service_workers="block")
    recovery_context.add_init_script("""
      window.__sent=[];
      window.GijulNative={systemDark:()=>false,setSolved:s=>__sent.push(JSON.parse(s)),
        savedSolved:()=>JSON.stringify({v:1,subs:[{g:'D300',s:'158'}],theme:'dark',
          solved:{'unknown/sub/20250101/exam':'20250102'},
          times:{'unknown/sub/20250101/exam':{spent:6330,limit:6000}},
          records:{'unknown/sub/20250101/exam':{score:0,wrong:[3,7]}}})};
    """)
    restored = recovery_context.new_page()
    restored.goto(SITE, wait_until="load")
    restored.wait_for_selector('#noticeYes:text("되살리기")')
    assert restored.evaluate("__sent.length") == 0, "복구 선택 전에 빈 웹 기록이 네이티브 사본을 지웠습니다"
    assert restored.evaluate("gijulBack()") is False
    assert restored.locator("#notice").is_visible(), "뒤로가기가 복구 결정을 숨겼습니다"
    restored.locator('#noticeYes').click()
    assert restored.evaluate("TIMES['unknown/sub/20250101/exam'].spent") == 6330
    assert restored.evaluate("RECORDS['unknown/sub/20250101/exam'].score") == 0
    assert restored.evaluate("themePref") == "dark"
    assert restored.evaluate("favs.length") == 1
    assert restored.evaluate("__sent.every(x=>Object.keys(x.marks).length>0)")
    recovery_context.close()
    browser.close()
print("ACK 저장 실패/재전송, 잘못된 fragment, 늦은 응답, 300px 창과 모달 포커스: 통과")
