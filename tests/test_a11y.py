"""접근성 — 알림이 소리로도 전해지는가, 표에 이름이 있는가."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from harness import CHROME, ROOT, SHOT, site, Serve
_srv, SITE = site()
import asyncio
from playwright.async_api import async_playwright
CH = CHROME
B = SITE.rstrip("/")
async def main():
    bad=[]
    async with async_playwright() as p:
        b=await p.chromium.launch(executable_path=CH)
        c=await b.new_context(viewport={"width":412,"height":900})
        pg=await c.new_page()
        await pg.goto(B+"/#/D300/158/all/all", wait_until="load"); await pg.wait_for_timeout(1200)

        a=await pg.evaluate("""()=>{const n=document.getElementById("notice");
          return {role:n.getAttribute("role"),live:n.getAttribute("aria-live"),
                  atomic:n.getAttribute("aria-atomic")};}""")
        print("1. 알림 막대:", a)
        if a["role"]!="status" or a["live"]!="polite": bad.append("막대에 알림 속성이 없습니다")

        # 숨김이 먼저 풀리고 글이 나중에 들어가는가 (그래야 읽어 준다)
        order=await pg.evaluate("""async()=>{
          const n=document.getElementById("notice"), t=document.getElementById("noticeText");
          const log=[];
          new MutationObserver(ms=>ms.forEach(m=>{
            if(m.type==="attributes"&&m.attributeName==="hidden") log.push("보임:"+!n.hidden);
            else log.push("글:"+(t.textContent||"(빔)").slice(0,10));
          })).observe(n,{attributes:true,subtree:true,childList:true,characterData:true});
          showNotice("시험용 알림입니다","확인",()=>{},null,{key:"t"});
          await new Promise(r=>setTimeout(r,50));   // 관찰자는 나중에 불린다
          return log;}""")
        print("   변화 순서:", order)
        vis=[i for i,x in enumerate(order) if x=="보임:true"]
        txt=[i for i,x in enumerate(order) if x.startswith("글:시험용")]
        if not vis or not txt or vis[0]>txt[0]:
            bad.append("숨김이 풀리기 전에 글자가 들어갑니다 — 읽어 주지 않습니다")
        else: print("   숨김 해제 → 글자 순서 맞음")

        print("2. main 랜드마크:", await pg.evaluate("()=>!!document.querySelector('main')"))
        if not await pg.evaluate("()=>!!document.querySelector('main')"): bad.append("앱 화면에 main 없음")

        small=await pg.evaluate("""()=>[...document.querySelectorAll("footer a")]
          .filter(e=>e.getBoundingClientRect().height<24)
          .map(e=>[e.textContent.trim().slice(0,8),Math.round(e.getBoundingClientRect().height)])""")
        print("3. 24px 미만 각주 링크:", small or "없음")
        if small: bad.append(f"앱 각주 링크가 아직 작습니다: {small}")

        # 과목 페이지
        await pg.goto(B+"/s/D300/158.html", wait_until="load"); await pg.wait_for_timeout(400)
        s=await pg.evaluate("""()=>({
          main:!!document.querySelector("main"),
          tables:document.querySelectorAll("table").length,
          named:document.querySelectorAll("table[aria-labelledby]").length,
          이름확인:(()=>{const t=document.querySelector("table[aria-labelledby]");
            return document.getElementById(t.getAttribute("aria-labelledby")).textContent.trim();})(),
          scope:document.querySelectorAll("thead th[scope=col]").length,
          noscope:document.querySelectorAll("thead th:not([scope])").length,
          작은링크:[...document.querySelectorAll(".crumb a, footer .ln a")]
            .filter(e=>e.getBoundingClientRect().height<24).length})""")
        print("4. 과목 페이지:", s)
        if not s["main"]: bad.append("과목 페이지에 main 없음")
        if s["named"]!=s["tables"]: bad.append("이름 없는 표가 남았습니다")
        if s["noscope"]: bad.append("scope 없는 th가 남았습니다")
        if s["작은링크"]: bad.append("과목 페이지 링크가 아직 작습니다")

        # 대비 재확인
        for mode in ("light","dark"):
            c2=await b.new_context(viewport={"width":412,"height":900}, color_scheme=mode)
            pg2=await c2.new_page()
            await pg2.goto(B+"/s/D300/158.html", wait_until="load"); await pg2.wait_for_timeout(400)
            off=await pg2.evaluate("""()=>{const e=document.querySelector(".dl .off");
              if(!e) return null; const s=getComputedStyle(e);
              let bg="rgba(0, 0, 0, 0)",p=e;
              while(p&&bg==="rgba(0, 0, 0, 0)"){bg=getComputedStyle(p).backgroundColor;p=p.parentElement;}
              const L=c=>{const [r,g,b]=c.slice(c.indexOf("(")+1).split(",").map(x=>parseFloat(x)/255);
                const f=v=>v<=.03928?v/12.92:Math.pow((v+.055)/1.055,2.4);
                return .2126*f(r)+.7152*f(g)+.0722*f(b);};
              const a=L(s.color),b2=L(bg);
              return +(((Math.max(a,b2)+.05)/(Math.min(a,b2)+.05)).toFixed(2));}""")
            print(f"5. [{mode}] '자료 없음' 대비: {off}")
            if off and off<4.5: bad.append(f"[{mode}] .off 대비 {off} < 4.5")
            await c2.close()
        # ---- 6. 손가락이 닿을 만한가 (WCAG 2.5.8 은 24×24 CSS px 를 최소로 본다)
        #
        # ✓ 와 도장은 글자 크기가 10.5~11px 이라 그대로 두면 21×17 · 52×17 이다.
        # 여백으로 닿는 자리만 넓혀 두었는데, 그 여백은 화면에 안 보이므로
        # 누군가 '쓸데없는 여백'으로 보고 지우기 쉽다. 지우면 아무 데도 안
        # 깨지고 손가락만 빗나간다 — 그래서 여기서 잰다.
        c3=await b.new_context(viewport={"width":412,"height":900})
        pg3=await c3.new_page()
        await pg3.goto(B+"/#/D300/158/all/all", wait_until="load")
        await pg3.wait_for_selector(".item .chk", timeout=25000)
        await pg3.evaluate("""()=>{const ks=[];document.querySelectorAll('.item .chk').forEach(c=>ks.push(c.dataset.k));
          SOLVED={}; ks.slice(0,3).forEach(k=>SOLVED[k]='20260824'); saveSolved(); render();}""")
        await pg3.wait_for_timeout(250)
        sizes=await pg3.evaluate("""()=>{
          const it=document.querySelector('.item'), out={};
          for(const sel of ['.chk','.stamp','.nm a.ext']){
            const e=it.querySelector(sel);
            if(!e) continue;
            const r=e.getBoundingClientRect();
            out[sel]=[Math.round(r.width), Math.round(r.height)];
          }
          return out;}""")
        print("6. 누르는 자리:", sizes)
        for sel,(w,h) in sizes.items():
            if w<24 or h<24: bad.append(f"{sel} 이 {w}×{h} — 24×24 보다 작습니다")

        # 서로 겹치면 엉뚱한 것이 눌린다
        who=await pg3.evaluate("""()=>{
          const it=document.querySelector('.item');
          it.scrollIntoView({block:'center'});
          const name=e=>{ if(!e) return 'null';
            for(const c of ['chk','stamp','ext']) if(e.closest('.'+c)) return c;
            return e.tagName; };
          const at=(x,y)=>name(document.elementFromPoint(x,y));
          const c=it.querySelector('.chk').getBoundingClientRect();
          const s=it.querySelector('.stamp').getBoundingClientRect();
          return { chk: at(c.left+c.width/2, c.top+c.height/2),
                   stamp: at(s.left+s.width/2, s.top+s.height/2),
                   gap: Math.round(s.top - c.bottom) };}""")
        print("   가운데를 누르면:", who)
        if who["chk"]!="chk" or who["stamp"]!="stamp":
            bad.append(f"누르는 자리가 서로 겹칩니다: {who}")
        if who["gap"] < 0: bad.append(f"✓ 와 도장이 {-who['gap']}px 겹칩니다")
        await c3.close()

        print("\n=== 남은 문제:", bad or "없음")
        await b.close()
asyncio.run(main())
