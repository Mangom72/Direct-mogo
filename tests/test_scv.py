"""회차 이름에 건 EBSi 링크 — 열리는 자리에만 걸리는가, 바깥으로 나가는 것이 보이는가.

EBSi 풀서비스에 등급컷과 문항별 정답률이 있다. 우리는 그 숫자를 담지 않고
주소만 건넨다. 주소는 `irecord`(시행일 여덟 자리 + 학년 숫자 한 자)와 `targetCd`
두 값으로 정해진다.

**아무 회차나 열리지 않는다.** 손으로 찔러 본 결과 고3의 2022-03-24 회차부터만
뜨고 그 앞은 EBSi 첫 화면으로 넘어간다. 고2·고1은 풀서비스 화면 자체가 없다.
넘어갈 때 404가 아니라 말없이 첫 화면으로 보내기 때문에, 링크를 잘못 걸면
화면에서는 멀쩡해 보이고 누른 사람만 엉뚱한 데서 돌아온다.

경계는 이 자료에 한해 정확하다 — 2021년 마지막 고3 회차가 11-18, 2022년 첫
회차가 03-24이라 확인하지 못한 구간에는 회차가 하나도 없다.
"""
import sys, pathlib, re
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from harness import CHROME, ROOT, site

_srv, SITE = site()
from playwright.sync_api import sync_playwright                    # noqa: E402

B = SITE.rstrip("/")
BAD, ERR = [], []


def ck(cond, msg):
    if not cond:
        BAD.append(msg)


# 손으로 EBSi에 물어서 확인한 경계다. **화면이 이 값을 벗어나면 여기서 실패한다** —
# 경계를 넓히는 것은 마음대로 할 일이 아니라 EBSi에 다시 물어볼 일이다. 넓힌 쪽이
# 틀리면 링크는 멀쩡해 보이면서 사람만 엉뚱한 데로 보낸다.
VERIFIED = "20220324"

src = (ROOT / "index.html").read_text(encoding="utf-8")
m = re.search(r'const SCV_FROM = "(\d{8})"', src)
if not m:
    print("★ index.html 에서 SCV_FROM 을 찾지 못했습니다")
    sys.exit(1)
FROM = m.group(1)
ck(FROM == VERIFIED,
   f"경계가 {FROM} 로 바뀌었습니다 (확인된 값은 {VERIFIED}). EBSi에서 그 회차가 "
   "실제로 열리는지 확인하고 이 시험의 VERIFIED 도 함께 고치십시오")
print(f"1. 화면이 쓰는 경계: {FROM} 부터 (확인된 값 {VERIFIED})")


def rows(pg):
    """회차마다 (날짜, 이름에 걸린 링크 주소 또는 None)."""
    return pg.evaluate("""()=>[...document.querySelectorAll('.item')].map(it=>{
        const d = it.querySelector('.meta span:nth-child(2)').textContent.trim().slice(0,10);
        const a = it.querySelector('.nm a.ext');
        return [d.replace(/\\./g,''), a ? a.href : null];})""")


with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path=CHROME)
    ctx = b.new_context(viewport={"width": 412, "height": 900}, service_workers="block")
    pg = ctx.new_page()
    pg.on("console", lambda msg: msg.type == "error" and ERR.append(msg.text))
    pg.on("pageerror", lambda e: ERR.append(str(e)))

    # ── 고3: 경계를 사이에 둔 과목 하나를 통째로 ────────────────────────
    pg.goto(f"{B}/#/D300/140117/all/all", wait_until="load")
    pg.wait_for_selector(".item")
    r = rows(pg)
    have = [d for d, u in r if u]
    lack = [d for d, u in r if not u]
    ck(all(d >= FROM for d in have),
       f"경계 앞인데 링크가 걸린 회차: {[d for d in have if d < FROM]}")
    ck(all(d < FROM for d in lack),
       f"경계 뒤인데 링크가 없는 회차: {[d for d in lack if d >= FROM]}")
    # 이 과목은 경계를 사이에 두고 있어 양쪽이 다 나와야 한다. 한쪽이 비면
    # 경계가 자료 밖으로 밀려난 것이라 위의 두 확인이 공짜로 통과한다.
    ck(have and lack, "경계 양쪽에 회차가 있어야 하는데 한쪽이 비었습니다 "
                      f"(링크 {len(have)}개 · 없음 {len(lack)}개)")
    print(f"2. 고3 {len(r)}회차 — 링크 {len(have)}개(가장 옛 {min(have, default='—')}) · "
          f"없음 {len(lack)}개(가장 최근 {max(lack, default='—')})")

    # ── 주소가 맞는가 ────────────────────────────────────────────────
    d0, u0 = next(((d, u) for d, u in r if u), (None, None))
    if u0 is None:
        BAD.append("링크가 하나도 걸리지 않아 주소를 확인할 수 없습니다")
        print("\n=== 문제:")
        for x in BAD:
            print("  ★", x)
        sys.exit(1)
    want = ("https://www.ebsi.co.kr/ebs/xip/xipa/retrieveSCVMainInfo.ebs"
            f"?irecord={d0}3&targetCd=D300")
    ck(u0 == want, f"주소가 다릅니다\n      나온것 {u0}\n      기대   {want}")
    print(f"3. 주소: {u0}")

    # irecord 끝자리는 학년이다. 날짜만 붙이고 학년을 빠뜨리면 EBSi가 조용히
    # 첫 화면으로 보내므로 화면에서는 티가 나지 않는다.
    ck(all(u.endswith("&targetCd=D300") and f"irecord={d}3" in u for d, u in r if u),
       "irecord 가 '시행일+학년숫자' 꼴이 아닌 회차가 있습니다")
    print("4. irecord = 시행일 + 학년숫자 — 전부 맞음")

    # ── 바깥으로 나간다는 것이 보이는가 ────────────────────────────────
    look = pg.evaluate("""()=>{
        const a = document.querySelector('.nm a.ext'), s = getComputedStyle(a);
        const svg = a.querySelector('svg');
        const rc = svg && svg.getBoundingClientRect();
        return {밑줄: s.textDecorationLine, 밑줄꼴: s.textDecorationStyle,
                화살표: !!svg, 화살표폭: rc ? Math.round(rc.width) : 0,
                숨김처리: svg ? svg.getAttribute('aria-hidden') : null,
                target: a.target, rel: a.rel,
                설명: (a.getAttribute('aria-label') || ''),
                글자색: s.color};}""")
    print("5. 겉모습:", {k: v for k, v in look.items() if k != "설명"})
    print("   읽어 줄 이름:", look["설명"])
    ck(look["밑줄"] == "underline" and look["밑줄꼴"] == "dotted",
       f"점선 밑줄이 아닙니다 ({look['밑줄']} / {look['밑줄꼴']})")
    ck(look["화살표"] and look["화살표폭"] > 4,
       f"대각선 화살표가 그려지지 않았습니다 (폭 {look['화살표폭']}px)")
    # 화살표는 그림이라 읽어 줄 것이 없다. 감춰 두지 않으면 '이미지'라고 읽힌다.
    ck(look["숨김처리"] == "true", "화살표가 낭독기에 감춰져 있지 않습니다")
    ck(look["target"] == "_blank" and "noopener" in look["rel"], "새 창으로 열지 않습니다")
    # 눈으로는 밑줄과 화살표로 알지만, 귀로 듣는 사람에게는 그 둘이 없다.
    ck("EBSi" in look["설명"] and "새 창" in look["설명"],
       f"어디로 가는 링크인지 읽어 주지 않습니다: {look['설명']!r}")

    # 손을 올리면 색이 옮아가고 밑줄이 실선이 되는가
    pg.hover(".nm a.ext")
    pg.wait_for_timeout(400)
    hov = pg.evaluate("""()=>{const s=getComputedStyle(document.querySelector('.nm a.ext'));
        return {밑줄꼴:s.textDecorationStyle, 글자색:s.color};}""")
    print("6. 손 올렸을 때:", hov)
    ck(hov["밑줄꼴"] == "solid", "손을 올려도 밑줄이 실선이 되지 않습니다")
    ck(hov["글자색"] != look["글자색"], "손을 올려도 글자색이 변하지 않습니다")

    # ── 파일 단추 자리를 건드리지 않았는가 ─────────────────────────────
    acts = pg.evaluate("""()=>{const it=document.querySelector('.item');
        return {파일링크: it.querySelectorAll('.acts a[data-nm]').length,
                단추수: it.querySelector('.acts').children.length,
                바깥링크가섞임: !!it.querySelector('.acts a.ext')};}""")
    print("7. 단추 줄:", acts)
    # 문제·정답·해설은 data-nm 을 달고 앱 뷰어로 넘어간다. 이 링크가 그 흐름에
    # 걸리면 뷰어가 남의 사이트 HTML을 PDF로 열려 든다.
    ck(acts["파일링크"] <= 3, f"파일로 세는 링크가 {acts['파일링크']}개입니다")
    ck(not acts["바깥링크가섞임"], "바깥 링크가 파일 단추 줄에 섞여 있습니다")
    ck(acts["단추수"] <= 4, f"단추 줄이 {acts['단추수']}칸으로 늘었습니다 — 본론이 좁아집니다")

    # ── 고2·고1에는 아예 없다 ────────────────────────────────────────
    for grade, sid in (("D200", "17022"), ("D100", "17012")):
        pg.goto(f"{B}/#/{grade}/{sid}/all/all", wait_until="load")
        pg.wait_for_selector(".item")
        cnt = pg.evaluate("()=>document.querySelectorAll('.nm a.ext').length")
        tot = pg.evaluate("()=>document.querySelectorAll('.item').length")
        ck(cnt == 0, f"{grade} 에 링크가 {cnt}개 걸렸습니다 — 풀서비스가 없는 학년입니다")
        print(f"8. {grade} {tot}회차 — 링크 {cnt}개 (없어야 맞음)")

    # ── 자리 ────────────────────────────────────────────────────────
    pg.goto(f"{B}/#/D300/140117/all/all", wait_until="load")
    pg.wait_for_selector(".nm a.ext")
    box = pg.evaluate("""()=>{
        const it=document.querySelector('.item'), a=it.querySelector('.nm a.ext');
        const q=it.querySelector('.acts a.q');
        return {넘침: document.documentElement.scrollWidth - innerWidth,
                이름줄안: a.getBoundingClientRect().bottom
                          <= it.querySelector('.meta').getBoundingClientRect().top + 1,
                문제단추폭: Math.round(q.getBoundingClientRect().width)};}""")
    print("9. 자리(412px):", box)
    ck(box["넘침"] == 0, f"가로로 {box['넘침']}px 넘칩니다")
    ck(box["이름줄안"], "링크가 이름 줄을 벗어나 아래 줄과 겹칩니다")
    ck(box["문제단추폭"] >= 60, f"'문제' 단추가 {box['문제단추폭']}px 로 눌렸습니다")

    # ── 푸터의 원본 단추 ──────────────────────────────────────────────
    # GitHub 단추가 '이 화면의 소스'라면 그 짝은 '자료의 원본'이다. 회차마다
    # 거는 링크와 달리 이건 늘 있어야 하는 자리다.
    foot = pg.evaluate("""()=>{
        const as=[...document.querySelectorAll('.src a')];
        const e=as.find(a=>a.href.includes('ebsi.co.kr'));
        if(!e) return null;
        const r=e.getBoundingClientRect(), g=as.find(a=>a.href.includes('github.com'));
        return {글자:e.textContent.trim(), 주소:e.href, 아이콘:!!e.querySelector('svg'),
                설명:e.getAttribute('aria-label')||'', target:e.target, rel:e.rel,
                깃허브오른쪽:!!g && r.left >= g.getBoundingClientRect().left,
                높이같음:!!g && Math.abs(r.height-g.getBoundingClientRect().height) < 2};}""")
    print("10. 푸터 원본 단추:", foot)
    ck(foot, "푸터에 EBSi 단추가 없습니다")
    if foot:
        ck(foot["아이콘"], "GitHub 단추와 달리 아이콘이 없습니다")
        ck(foot["target"] == "_blank" and "noopener" in foot["rel"], "새 창으로 열지 않습니다")
        ck("EBSi" in foot["설명"] and "새 창" in foot["설명"],
           f"어디로 가는지 읽어 주지 않습니다: {foot['설명']!r}")
        ck(foot["깃허브오른쪽"], "GitHub 단추 왼쪽에 있습니다")
        ck(foot["높이같음"], "GitHub 단추와 높이가 다릅니다 — 같은 꼴이어야 합니다")

    b.close()

print("ERRORS:", ERR or "없음")
print("\n=== 문제:", "없음" if not BAD and not ERR else "")
for x in BAD:
    print("  ★", x)
sys.exit(1 if BAD or ERR else 0)
