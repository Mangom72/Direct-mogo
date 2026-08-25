"""백업 — 내보낸 것이 돌아오는가, 합칠 때 이 기기 것을 안 지우는가.

<h3>왜 이것을 지키는가</h3>
계정도 서버도 없으므로 사람마다 다른 것은 전부 그 기기에만 있다. 이 기능이
조용히 망가지면 **되돌릴 방법이 없다** — 파일은 만들어졌는데 안이 비어 있거나,
가져오기가 이 기기에서 찍은 것을 지워 버리거나 하는 결말이 그렇다. 어느 쪽도
그 자리에서는 멀쩡해 보이고, 알아차릴 때는 이미 늦다.

세 가지를 본다.

1. **왕복.** 내보낸 것을 그대로 가져오면 처음과 같아지는가.
2. **합치기는 더하기다.** 다른 기기의 것을 가져올 때 여기서 찍은 것이 남는가.
   덮어쓰기를 기본으로 두면 그 순간 조용히 사라진다.
3. **아무것이나 받지 않는다.** 파일은 사람이 손으로 고칠 수 있고, 엉뚱한 파일을
   고를 수도 있다.
"""
import json, sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from harness import CHROME, SHOT, site
_srv, SITE = site()
from playwright.sync_api import sync_playwright

BAD = []
def ck(cond, msg):
    if not cond:
        BAD.append(msg)

def state(pg):
    return pg.evaluate("()=>[Object.keys(SOLVED).sort(), favs.map(f=>f.g+'/'+f.s).sort()]")

with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path=CHROME)
    ctx = b.new_context(viewport={"width": 412, "height": 900},
                        service_workers="block", accept_downloads=True)
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)[:180]))
    pg.goto(SITE, wait_until="load")
    pg.wait_for_selector(".item .chk", timeout=25000)

    # 표시 다섯, 내 과목 하나
    pg.evaluate("""()=>{
      const ks=[]; document.querySelectorAll('.item .chk').forEach(c=>ks.push(c.dataset.k));
      SOLVED={}; ks.slice(0,5).forEach((k,i)=>SOLVED[k]='2026082'+(i%9)); saveSolved();
      favs.length=0; favs.push({g:sel.grade, s:sel.sub}); saveFavs(); syncFav(); render();}""")
    before = state(pg)
    print("1. 처음:", len(before[0]), "회차 ·", len(before[1]), "과목")

    # ---- 내보내기 ----
    pg.click("#bakBtn")
    pg.wait_for_selector("#sheet:not([hidden])", timeout=5000)
    pg.wait_for_timeout(150)
    with pg.expect_download() as dl:
        pg.click(".sfile .go")
    d = dl.value
    path = pathlib.Path(SHOT) / "backup.json"
    d.save_as(str(path))
    obj = json.loads(path.read_text(encoding="utf-8"))
    print("2. 내보낸 파일:", d.suggested_filename, "·", len(json.dumps(obj)), "바이트")
    ck(d.suggested_filename.startswith("기출직행-백업-"), f"파일 이름이 이상합니다: {d.suggested_filename}")
    ck(obj.get("v") == 1, "판 번호가 없습니다")
    ck(len(obj.get("solved", {})) == len(before[0]), "푼 회차가 파일에 다 안 담겼습니다")
    ck(len(obj.get("subs", [])) == len(before[1]), "내 과목이 파일에 다 안 담겼습니다")

    # ---- 전부 지우고 가져오기 ----
    pg.evaluate("()=>{ SOLVED={}; favs.length=0; saveSolved(); saveFavs(); syncFav(); render(); }")
    pg.evaluate("t=>takeBackup(t)", path.read_text(encoding="utf-8"))
    pg.wait_for_timeout(200)
    print("3. 미리보기:", pg.eval_on_selector(".sfile .k", "e=>e.textContent"))
    pg.eval_on_selector_all(".sfile .go", "e=>e[0].click()")     # 합치기
    pg.wait_for_timeout(300)
    after = state(pg)
    print("   되살린 뒤:", len(after[0]), "회차 ·", len(after[1]), "과목")
    ck(after == before, f"왕복이 어긋납니다: {before} → {after}")

    # ---- 합치기는 여기 것을 지우지 않는다 ----
    mine = pg.evaluate("""()=>{
      const ks=[]; document.querySelectorAll('.item .chk').forEach(c=>ks.push(c.dataset.k));
      SOLVED={}; SOLVED[ks[9]]='20260101'; saveSolved(); render(); return ks[9];}""")
    pg.evaluate("t=>takeBackup(t)", path.read_text(encoding="utf-8"))
    pg.wait_for_timeout(150)
    pg.eval_on_selector_all(".sfile .go", "e=>e[0].click()")     # 합치기
    pg.wait_for_timeout(300)
    kept = pg.evaluate("k=>SOLVED[k]", mine)
    n = pg.evaluate("()=>Object.keys(SOLVED).length")
    print(f"4. 합치기 — 여기서 찍은 것 남음: {kept} · 전체 {n}개")
    ck(kept == "20260101", "합쳤더니 이 기기에서 찍은 것이 사라졌습니다")
    ck(n == len(before[0]) + 1, f"합친 개수가 맞지 않습니다: {n}")

    # ---- 덮어쓰기는 실제로 바꾼다 ----
    pg.evaluate("t=>takeBackup(t)", path.read_text(encoding="utf-8"))
    pg.wait_for_timeout(150)
    pg.eval_on_selector_all(".sfile .go", "e=>e[1].click()")     # 덮어쓰기
    pg.wait_for_timeout(300)
    n2 = pg.evaluate("()=>Object.keys(SOLVED).length")
    gone = pg.evaluate("k=>!(k in SOLVED)", mine)
    print(f"5. 덮어쓰기 — 전체 {n2}개 · 여기 것 사라짐: {gone}")
    ck(n2 == len(before[0]) and gone, "덮어쓰기가 파일의 것으로 바꾸지 않았습니다")

    # ---- 아무것이나 받지 않는다 ----
    cases = [
        ("판이 다른 파일", json.dumps({"v": 99, "solved": {}, "subs": []})),
        ("JSON 이 아닌 것", "이건 그냥 글입니다"),
        ("내용이 빈 것", "null"),
    ]
    for name, text in cases:
        pg.evaluate("t=>takeBackup(t)", text)
        pg.wait_for_timeout(120)
        note = pg.text_content("#sheetNote")
        ok = "읽지 못했습니다" in note
        print(f"6. {name}: {'거절' if ok else '받아들임 — ' + note[:40]}")
        ck(ok, f"{name} 을 거절하지 않았습니다")

    # 이상한 값이 섞여 있으면 그것만 버리고 나머지는 살린다
    dirty = json.loads(path.read_text(encoding="utf-8"))
    dirty["solved"]["없는/과목/20250101/수능"] = "20260101"
    dirty["solved"]["망가진열쇠"] = "20260101"
    dirty["solved"]["D300/158/20250101/수능"] = "날짜아님"
    dirty["subs"].append({"g": "ZZZ", "s": "9999"})
    pg.evaluate("()=>{ SOLVED={}; favs.length=0; saveSolved(); saveFavs(); render(); }")
    pg.evaluate("t=>takeBackup(t)", json.dumps(dirty))
    pg.wait_for_timeout(150)
    pg.eval_on_selector_all(".sfile .go", "e=>e[0].click()")
    pg.wait_for_timeout(300)
    got = state(pg)
    print("7. 이상한 값이 섞인 파일 →", len(got[0]), "회차 ·", len(got[1]), "과목")
    ck("망가진열쇠" not in got[0], "열쇠 꼴이 아닌 것이 들어왔습니다")
    ck(not any(x.startswith("ZZZ") for x in got[1]), "없는 과목이 들어왔습니다")
    # 모르는 과목의 표시는 <b>일부러 남긴다</b>. 과목 코드는 교육과정이 바뀔 때
    # 실제로 바뀌는데, 못 알아본다고 지우면 그 한 번에 그동안 찍은 것이 날아간다.
    # 알약과 달리 표시는 그 과목을 열지 않는 한 화면에 나타나지도 않는다.
    ck(len(got[0]) == len(before[0]) + 1,
       f"성한 것까지 버렸거나 모르는 과목 표시를 지웠습니다: {len(got[0])}")

    pg.screenshot(path=str(pathlib.Path(SHOT) / "backup.png"))
    print("   오류:", errs or "없음")
    ck(not errs, f"스크립트 오류: {errs}")
    ctx.close()

    # ---- 8. 앱 사본에서 되살리기 ----
    #
    # 앱은 페이지가 건넨 표시를 사본으로 들고 있다(위젯이 읽는 그것이다).
    # 웹뷰의 자료가 날아가도 이쪽은 남으므로, 화면이 비었는데 사본에 있으면
    # 되살릴지 묻는다. 백업을 안 해 둔 사람에게 남는 마지막 줄이다.
    ctx2 = b.new_context(viewport={"width": 412, "height": 900}, service_workers="block")
    ctx2.add_init_script("""
      window.GijulNative = {
        systemDark: () => false,
        savedSolved: () => JSON.stringify({ v:1, at:"2026-08-20T00:00:00Z", subs:[],
          solved:{ "D300/140117/20211118/수능":"20260801",
                   "D300/140117/20211012/10월 학평(서울)":"20260802" } }),
      };""")
    pg2 = ctx2.new_page()
    e2 = []
    pg2.on("pageerror", lambda e: e2.append(str(e)[:180]))
    pg2.goto(SITE, wait_until="load")
    pg2.wait_for_selector(".item", timeout=25000)
    pg2.wait_for_timeout(900)
    asked = pg2.eval_on_selector("#notice", "e=>!e.hidden")
    print("8. 앱 사본이 남아 있을 때 되살릴지 묻는가:", asked)
    ck(asked, "앱에 표시가 있는데 되살리자고 묻지 않습니다")
    if asked:
        ck("2개" in pg2.text_content("#noticeText"), "몇 개인지 말하지 않습니다")
        pg2.click("#noticeYes")
        pg2.wait_for_timeout(400)
        n8 = pg2.evaluate("()=>Object.keys(SOLVED).length")
        print("   되살린 뒤:", n8, "개")
        ck(n8 == 2, f"되살아난 것이 {n8}개입니다")
    ck(not e2, f"스크립트 오류: {e2}")

    # ---- 9b. 어디 있는지 알아야 쓴다 ----
    #
    # 처음에는 푸터에 두었다. 7.8화면을 내려야 닿았고, 그래서 있는 줄 모르는
    # 기능이 되었다. 표제 옆으로 올렸지만 올리는 것만으로는 모자라다 — 눌러 볼
    # 까닭이 없으면 그냥 지나친다. 값이 쌓인 뒤에 한 번만 말을 건다.
    ctx5 = b.new_context(viewport={"width": 412, "height": 900}, service_workers="block")
    pg5 = ctx5.new_page()
    e5 = []
    pg5.on("pageerror", lambda e: e5.append(str(e)[:180]))
    pg5.goto(SITE, wait_until="load")
    pg5.wait_for_selector(".item .chk", timeout=25000)

    where = pg5.evaluate("""()=>{const e=document.getElementById('bakBtn');
      if(!e) return null; const b=e.getBoundingClientRect();
      return { 첫화면: b.bottom <= innerHeight && b.top >= 0,
               크기: [Math.round(b.width), Math.round(b.height)] };}""")
    print("9b. 백업 단추:", where)
    ck(where, "백업 단추가 없습니다")
    ck(where and where["첫화면"], "백업 단추가 첫 화면에 없습니다 — 내려야 닿으면 못 찾습니다")
    ck(where and min(where["크기"]) >= 24, f"백업 단추가 작습니다: {where}")

    # 글꼴에 없는 글자를 아이콘으로 쓰면 기기에 따라 두부가 된다(✓ 때의 그것)
    ico = pg5.evaluate("()=>!!document.querySelector('#bakBtn svg')")
    print("    아이콘이 그림인가:", ico)
    ck(ico, "백업 아이콘이 글자입니다 — 글꼴에 없으면 두부가 됩니다")

    pg5.evaluate("""()=>{const ks=[];document.querySelectorAll('.item .chk').forEach(c=>ks.push(c.dataset.k));
      SOLVED={}; ks.slice(0,19).forEach(k=>SOLVED[k]='20260824'); saveSolved(); offerBackup();}""")
    pg5.wait_for_timeout(250)
    early = pg5.eval_on_selector("#notice", "e=>!e.hidden")
    print("    19개일 때 권하는가:", early)
    ck(not early, "얼마 안 찍었는데 벌써 백업하라고 합니다")

    pg5.evaluate("""()=>{const ks=[];document.querySelectorAll('.item .chk').forEach(c=>ks.push(c.dataset.k));
      ks.slice(0,25).forEach(k=>SOLVED[k]='20260824'); saveSolved(); offerBackup();}""")
    pg5.wait_for_timeout(300)
    asked5 = pg5.eval_on_selector("#notice", "e=>!e.hidden")
    print("    쌓인 뒤:", asked5, "|", pg5.text_content("#noticeText") if asked5 else "")
    ck(asked5, "많이 찍었는데도 백업하라는 말이 없습니다")

    # 물어본 것을 또 묻는 것이 가장 성가시다
    pg5.click("#noticeNo")
    pg5.wait_for_timeout(200)
    pg5.evaluate("()=>offerBackup()")
    pg5.wait_for_timeout(250)
    again5 = pg5.eval_on_selector("#notice", "e=>!e.hidden")
    print("    아니오 뒤 또 묻는가:", again5)
    ck(not again5, "'아니오'라고 했는데 또 묻습니다")
    ck(not e5, f"스크립트 오류: {e5}")
    ctx5.close()

    # ---- 10. 자동 백업 (앱에만 있는 줄) ----
    #
    # 사람이 기억해서 눌러야 하는 백업은 결국 안 하게 되고, 안 한 것을 알아차리는
    # 때는 이미 늦은 뒤다. 자리를 한 번 고르면 그 뒤로는 앱이 조용히 덮어쓴다.
    #
    # **막힌 것을 말하는지**가 특히 중요하다. 조용히 멈춘 자동 백업은 없는 것보다
    # 나쁘다 — 되고 있다고 믿게 만들기 때문이다.
    ctx3 = b.new_context(viewport={"width": 412, "height": 900}, service_workers="block")
    ctx3.add_init_script("""
      window.__auto = { on:false, name:"", error:"" };
      window.GijulNative = {
        systemDark: () => false,
        setSolved: () => {},
        autoBackup: () => JSON.stringify(window.__auto),
        pickAutoBackup: () => { window.__auto = {on:true, name:"기출직행-백업.json", error:""};
                                window.gijulAutoBackup(window.__auto); },
        stopAutoBackup: () => { window.__auto = {on:false, name:"", error:""};
                                window.gijulAutoBackup(window.__auto); },
      };""")
    pg3 = ctx3.new_page()
    e3 = []
    pg3.on("pageerror", lambda e: e3.append(str(e)[:180]))
    pg3.goto(SITE, wait_until="load")
    pg3.wait_for_selector(".item .chk", timeout=25000)

    # 앱에 건네는 꾸러미에 favs·theme 이 실려야 자동 백업 파일이 반쪽이 안 된다.
    # marks·subs·next 는 옛 앱의 위젯이 읽는 이름이라 그대로 있어야 한다.
    keys = pg3.evaluate("""()=>{ let seen=null;
      const old = GijulNative.setSolved;
      GijulNative.setSolved = j => { seen = JSON.parse(j); };
      tellSolved();
      GijulNative.setSolved = old;
      return seen ? Object.keys(seen).sort() : []; }""")
    print("10. 앱에 건네는 열쇠:", keys)
    for want in ("marks", "subs", "next", "favs", "theme"):
        ck(want in keys, f"꾸러미에 {want} 가 없습니다 — {keys}")

    pg3.click("#bakBtn")
    pg3.wait_for_selector("#sheet:not([hidden])", timeout=5000)
    pg3.wait_for_timeout(250)
    rows3 = pg3.eval_on_selector_all(".sfile .k", "e=>e.map(x=>x.textContent)")
    print("    시트 줄:", rows3)
    ck(rows3 and rows3[0] == "자동 백업", f"자동 백업 줄이 맨 위에 없습니다: {rows3}")

    pg3.eval_on_selector_all(".sfile .go", "e=>e[0].click()")     # 자리 고르기
    pg3.wait_for_timeout(300)
    on = pg3.eval_on_selector_all(".sfile .x", "e=>e.map(x=>x.textContent)")[0]
    btn = pg3.eval_on_selector_all(".sfile .go", "e=>e[0].textContent")
    print("    고른 뒤:", on, "·", btn)
    ck("저절로" in on and "기출직행-백업.json" in on, f"어디에 쓰는지 안 보입니다: {on}")
    ck(btn == "그만두기", f"단추가 그만두기로 안 바뀝니다: {btn}")

    # 막혔을 때 — 조용히 넘어가면 안 된다
    pg3.evaluate("""()=>{ window.__auto = {on:true, name:"기출직행-백업.json",
      error:"열지 못했습니다"}; window.gijulAutoBackup(window.__auto); }""")
    pg3.wait_for_timeout(250)
    bad3 = pg3.eval_on_selector_all(".sfile .x", "e=>e.map(x=>x.textContent)")[0]
    mark = pg3.eval_on_selector_all(".sfile .go", "e=>e[0].dataset.state")
    print("    막혔을 때:", bad3, "· 눈에 띄게:", mark)
    ck("막혔습니다" in bad3, f"막힌 것을 말하지 않습니다: {bad3}")
    ck(mark == "confirm", "막혔는데 단추가 예사롭게 보입니다")

    pg3.evaluate("()=>{ window.__auto = {on:true, name:'기출직행-백업.json', error:''};"
                 " window.gijulAutoBackup(window.__auto); }")
    pg3.wait_for_timeout(200)
    pg3.eval_on_selector_all(".sfile .go", "e=>e[0].click()")     # 그만두기
    pg3.wait_for_timeout(300)
    off = pg3.eval_on_selector_all(".sfile .x", "e=>e.map(x=>x.textContent)")[0]
    print("    그만둔 뒤:", off)
    ck("한 번 고르면" in off, f"그만둔 뒤 안내가 돌아오지 않습니다: {off}")
    ck(not e3, f"스크립트 오류: {e3}")
    ctx3.close()

    # ---- 11. 바뀌면 앱이 안다 ----
    #
    # 예전에는 표시를 찍을 때만 알렸다. 그래서 과목을 ★로 저장해 놓고 아무것도
    # 안 찍으면 '다음에 풀 것' 위젯은 옛 과목을 계속 짚고 있었고, 자동 백업
    # 파일에도 그 과목이 들어가지 않았다. 어느 쪽도 화면에서는 티가 안 난다.
    ctx4 = b.new_context(viewport={"width": 412, "height": 900}, service_workers="block")
    ctx4.add_init_script("""
      window.__sent = [];
      window.GijulNative = { systemDark: () => false,
        setSolved: j => window.__sent.push(JSON.parse(j)) };""")
    pg4 = ctx4.new_page()
    e4 = []
    pg4.on("pageerror", lambda e: e4.append(str(e)[:180]))
    pg4.goto(SITE, wait_until="load")
    pg4.wait_for_selector(".item", timeout=25000)
    pg4.wait_for_timeout(500)

    # 자료가 오기 전에 부르면 nextUp() 이 빈손이라 위젯을 지웠다 채우게 된다
    boot = pg4.evaluate("()=>window.__sent.length")
    print("11. 부팅 중 앱에 알린 횟수:", boot)
    ck(boot == 1, f"부팅에 {boot}번 알렸습니다 — 자료가 온 뒤 한 번이어야 합니다")

    pg4.evaluate("()=>{ window.__sent.length = 0; }")
    pg4.click("#favToggle")
    pg4.wait_for_timeout(300)
    favs4 = pg4.evaluate("()=>window.__sent.map(x=>x.favs.length)")
    # ★ 를 출력에 쓰지 않는다 — run.py 가 출력의 ★ 를 실패 표시로 읽는다.
    # 검사는 다 통과했는데 장식 글자 하나에 시험이 진 적이 있다.
    print("    내 과목 단추를 눌렀을 때:", favs4)
    ck(favs4 and favs4[-1] == 1, f"내 과목을 바꿨는데 앱이 모릅니다: {favs4}")

    pg4.evaluate("()=>{ window.__sent.length = 0; }")
    pg4.click("#thBtn")
    pg4.wait_for_timeout(300)
    th4 = pg4.evaluate("()=>window.__sent.map(x=>x.theme)")
    print("    테마 바꿨을 때:", th4)
    ck(th4 and th4[-1] != "auto", f"테마를 바꿨는데 앱이 모릅니다: {th4}")
    ck(not e4, f"스크립트 오류: {e4}")
    ctx4.close()

    # 화면에 이미 있으면 묻지 않는다 — 있는 것을 두고 또 물으면 성가시기만 하다
    pg2.reload(wait_until="load")
    pg2.wait_for_selector(".item", timeout=25000)
    pg2.wait_for_timeout(900)
    again = pg2.eval_on_selector("#notice", "e=>!e.hidden")
    print("9. 화면에 이미 있을 때 또 묻는가:", again)
    ck(not again, "화면에 표시가 있는데도 되살리자고 묻습니다")
    ctx2.close()
    b.close()

print("\n=== 문제:", "없음" if not BAD else "")
for x in BAD:
    print("  ★", x)
sys.exit(1 if BAD else 0)
