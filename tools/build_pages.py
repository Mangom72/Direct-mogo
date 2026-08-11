#!/usr/bin/env python3
"""검색엔진과 사람이 읽을 수 있는 과목별 정적 페이지를 만든다.

`index.html`은 자료를 gzip+base64로 품고 JS로 푼다. 사람에게는 그게 빠르지만
검색엔진에게는 빈 페이지 한 장이다 — 3,844회차가 통째로 안 보인다. 그래서
같은 자료를 **스크립트 없이 그냥 읽히는 HTML**로도 깔아 둔다.

    /s/                     과목 색인 (49과목)
    /s/D300/158.html        고3·N수 생명과학Ⅰ 전 회차
    /sitemap.xml            위 전부

회차별 페이지는 만들지 않는다. 3,844장이 되는데 한 장에 링크 세 개뿐이라
검색엔진이 '알맹이 없는 페이지'로 보고 오히려 깎는다. 과목 페이지 한 장이
그 과목의 링크를 전부 담으므로 잃는 것도 없다.

앱 화면과 이 페이지들은 같은 자료를 가리키므로, 어느 쪽이 검색에 잡히든
canonical로 자기 자신을 가리키고 서로 오갈 수 있게 해 둔다.

    python3 tools/build_pages.py      # data/ 를 읽어 s/ 와 sitemap.xml 을 다시 만든다

data/ 가 먼저 있어야 한다 — tools/build_api.py 를 먼저 돌린다.
"""
import argparse
import html
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = "https://mangom72.github.io/Direct-mogo/"
REPO = "https://github.com/Mangom72/Direct-mogo"

E = lambda s: html.escape(str(s), quote=True)


def head(title, desc, canon, depth, alt=""):
    """페이지 머리. depth는 사이트 뿌리까지 거슬러 올라갈 칸 수."""
    up = "../" * depth
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self'; img-src 'self' data:; style-src 'self'; font-src 'self'; object-src 'none'; base-uri 'none'; form-action 'none'">
<title>{E(title)}</title>
<meta name="description" content="{E(desc)}">
<link rel="canonical" href="{E(canon)}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="기출 직행">
<meta property="og:locale" content="ko_KR">
<meta property="og:title" content="{E(title)}">
<meta property="og:description" content="{E(desc)}">
<meta property="og:url" content="{E(canon)}">
<meta property="og:image" content="{SITE}icons/icon-512.png">
<meta name="twitter:card" content="summary">
<link rel="icon" href="{up}icons/favicon.ico" sizes="32x32">
<!-- 기계만 읽으면 되는 것은 화면이 아니라 여기 둔다. rel=alternate 는 '같은
     내용의 다른 표현'이라는 뜻이라 안내문과 JSON에 그대로 맞고, 사람 눈에는
     아무것도 늘지 않는다. 화면에 적어 두고 CSS로 감추는 길도 있지만 그건
     사람에게 감추고 검색엔진에만 보이는 짓이라 구글이 클로킹으로 다룬다. -->
<link rel="alternate" type="text/plain" href="{up}llms.txt" title="AI·프로그램용 안내">
<link rel="alternate" type="text/plain" href="{up}llms-full.txt" title="AI·프로그램용 자세한 안내">
<link rel="alternate" type="application/json" href="{up}data/index.json" title="과목 목록 (JSON)">{alt}
<!-- 글꼴은 font-display:optional 이라 제때 준비되지 않으면 그 방문에 안 쓰인다.
     스타일시트를 읽고 나서 받기 시작하면 그 창을 못 맞춰, 검색으로 들어온 첫
     페이지가 늘 시스템 글꼴로 열린다. preload로 파싱하는 자리에서 띄워 맞춘다.
     늦게 도착해도 갈아끼우지 않으니 이걸로 흔들릴 일은 없다. -->
<link rel="preload" as="font" type="font/woff2" crossorigin href="{up}fonts/SongMyung-400.woff2">
<link rel="preload" as="font" type="font/woff2" crossorigin href="{up}fonts/GijulSans-400.woff2">
<link rel="preload" as="font" type="font/woff2" crossorigin href="{up}fonts/GijulSans-600.woff2">
<link rel="preload" as="font" type="font/woff2" crossorigin href="{up}fonts/GijulSans-700.woff2">
<link rel="stylesheet" href="{up}fonts/fonts.css">
<link rel="stylesheet" href="{up}s/paper.css">
<meta name="theme-color" content="#191713">
<script src="{up}s/site.js"></script>
</head>
<body>
<main>
"""


def foot(depth, extra=""):
    up = "../" * depth
    return f"""
</main>
<footer>
  {extra}
  <p>모든 링크는 EBSi가 공개하여 별도의 인증 없이 접근 가능한 파일 주소로 직접
  연결되며, 이 사이트는 어떤 파일도 저장·재배포하지 않습니다. 문제 자료의 저작권은
  <b>한국교육과정평가원</b> 및 <b>각 시·도교육청</b>에 있습니다.
  권리자 또는 정당한 대리인의 게시중단 요청은 확인 즉시 이행합니다 —
  <a href="mailto:direct.mogo.dev@gmail.com">direct.mogo.dev@gmail.com</a> 또는
  <a href="{REPO}/issues">GitHub 이슈</a>.
  자세한 것은 <a href="{REPO}/blob/main/NOTICE.md">이용 안내</a>에 있습니다.</p>
  <p>연도는 <b>시행 연도</b>입니다. 평가원 시험의 학년도는 시행 연도 + 1이므로
  (2025년 11월 시행 = 2026학년도 수능) 각 회차에 학년도를 함께 적었습니다.
  교육청 학력평가는 관례상 시행 연도로만 부릅니다.</p>
  <p class="ln"><a href="{up}">기출 직행</a> ·
     <a href="{up}s/">전체 과목</a> ·
     <a href="{REPO}">GitHub</a></p>
</footer>
</body>
</html>
"""


def crumbs(depth, here):
    """화면에 보이는 빵부스러기와, 그것을 그대로 옮긴 구조화 데이터.

    구글은 BreadcrumbList를 리치 결과로 지원해서, 검색 결과에 주소 대신 이
    길이 뜬다. 주소가 /s/D300/158.html 처럼 번호로 된 우리에게는 이게 곧
    '주소에 낱말을 넣는' 일을 대신한다 — 구글 문서도 주소 속 낱말은
    '빵부스러기에 뜨는 것 말고는 거의 효과가 없다'고 못박는다.

    구조화 데이터 지침이 요구하는 두 가지를 지킨다 — 보이지 않는 것을
    적지 말 것(아래 nav와 글자가 같다), 주소 구조가 아니라 사람이 실제로
    지나온 길을 적을 것(홈 → 전체 과목 → 이 과목).
    """
    up = "../" * depth
    trail = [("기출 직행", SITE), ("전체 과목", SITE + "s/"), (here, None)]
    items = []
    for i, (nm, href) in enumerate(trail, 1):
        one = {"@type": "ListItem", "position": i, "name": nm}
        if href:
            one["item"] = href
        items.append(one)
    ld = json.dumps({"@context": "https://schema.org", "@type": "BreadcrumbList",
                     "itemListElement": items}, ensure_ascii=False)
    return (f'<script type="application/ld+json">{ld}</script>\n'
            f'<nav class="crumb" aria-label="위치"><a href="{up}">기출 직행</a>'
            f' <span aria-hidden="true">›</span> <a href="{up}s/">전체 과목</a>'
            f' <span aria-hidden="true">›</span> <b>{E(here)}</b></nav>')


def crumbs_top():
    """색인 페이지 — 두 칸짜리 (구조화 데이터는 두 칸 이상이라야 한다)"""
    ld = json.dumps({"@context": "https://schema.org", "@type": "BreadcrumbList",
                     "itemListElement": [
                         {"@type": "ListItem", "position": 1, "name": "기출 직행",
                          "item": SITE},
                         {"@type": "ListItem", "position": 2, "name": "전체 과목"}]},
                    ensure_ascii=False)
    return (f'<script type="application/ld+json">{ld}</script>\n'
            f'<nav class="crumb" aria-label="위치"><a href="../">기출 직행</a>'
            f' <span aria-hidden="true">›</span> <b>전체 과목</b></nav>')


def facts(meta):
    """이 과목에서만 참인 사실 몇 줄.

    49장이 같은 틀에서 나오다 보니 본문이 이름과 숫자만 바뀐 같은 글이었다.
    구글이 '값을 더하지 않고 찍어낸 페이지'로 보는 자리가 정확히 거기다.
    그래서 자료에서 이 과목에만 해당하는 것을 뽑아 적는다 — 사람에게도
    표를 세어 보지 않으면 알 수 없는 것들이다.
    """
    ps = meta["papers"]
    gov = sum(1 for p in ps if p["source"] == "평가원")
    suneung = sum(1 for p in ps if p["title"].startswith("수능"))
    no_sol = sum(1 for p in ps if not p.get("solution"))
    no_ans = sum(1 for p in ps if not p.get("answer"))
    years = sorted({p["year"] for p in ps})
    out = []
    if gov:
        out.append(f"평가원 <b>{gov}회</b>(수능 {suneung}회 포함) · "
                   f"교육청 <b>{len(ps) - gov}회</b>")
    else:
        out.append(f"전부 교육청 전국연합학력평가 <b>{len(ps)}회</b> — "
                   "평가원 시험에는 없는 과목입니다")
    # 연도가 끊긴 적이 있으면 그것도 사실이다 (교육과정이 바뀐 자리)
    gaps = [y for y in range(years[0], years[-1]) if y not in years]
    if gaps:
        out.append("자료가 없는 해: <b>" + ", ".join(f"{y}년" for y in gaps[:6])
                   + ("…" if len(gaps) > 6 else "") + "</b>")
    if no_sol or no_ans:
        miss = []
        if no_sol:
            miss.append(f"해설 {no_sol}회")
        if no_ans:
            miss.append(f"정답 {no_ans}회")
        out.append("자료가 빠진 회차: <b>" + " · ".join(miss) + "</b>")
    out.append(f"가장 최근 회차: <b>{E(ps[0]['title'])}</b> ({E(ps[0]['date'])} 시행)")
    return "".join(f"<li>{x}</li>" for x in out)


def subject_page(meta, sub):
    """과목 한 개 — 전 회차를 연도별로 묶어 표로."""
    g, gl = meta["grade"], meta["gradeLabel"]
    name, sid, n = meta["subject"], meta["subjectId"], meta["count"]
    canon = f"{SITE}s/{g}/{sid}.html"
    years = sorted({p["year"] for p in meta["papers"]}, reverse=True)
    span = f"{years[-1]}~{years[0]}년" if len(years) > 1 else f"{years[0]}년"
    # 제목은 좁은 화면에서 픽셀 너비로 잘린다. 한글은 폭이 넓어 20자쯤에서
    # 끊기므로 짧게 간다. 회차 수는 설명과 본문에 있으니 제목에서 뺐다 —
    # 매달 바뀌는 값이라 두면 제목이 달마다 요동치기도 한다.
    title = f"{gl} {name} 기출문제 — 기출 직행"
    desc = (f"{gl} {name} 수능·모의평가·전국연합학력평가 기출 문제지 {n}회차 "
            f"({span}). 문제·정답·해설 원본 PDF로 바로 이동합니다.")

    mine = (f'\n<link rel="alternate" type="application/json" '
            f'href="../../data/{g}/{sid}.json" title="{E(name)} 전 회차 (JSON)">')
    out = [head(title, desc, canon, 2, mine), crumbs(2, f"{gl} {name}")]
    out.append(f"""<header class="pg">
  <p class="kicker">{E(meta['group'])}</p>
  <h1>{E(gl)} {E(name)} 기출문제</h1>
  <p class="lead">{E(gl)} <b>{E(name)}</b> 전 회차 <b>{n}개</b> ({E(span)}).
  아래 표의 문제·정답·해설은 EBSi 원본 파일로 바로 갑니다.</p>
  <p class="yrnote"><b>연도는 시행 연도입니다.</b> 평가원 시험(수능·6·9월 모평)은
  학년도가 한 해 뒤라 함께 적었습니다 — <b>2025년 11월 시행 = 2026학년도 수능</b>.
  교육청 전국연합학력평가는 학년도를 쓰지 않습니다.</p>
  <ul class="facts">{facts(meta)}</ul>
  <p class="go"><a class="app" href="../../#/{g}/{sid}/all/all">앱 화면에서 보기</a>
     <a href="../../data/{g}/{sid}.json">JSON으로 받기</a></p>
</header>
""")

    for y in years:
        rows = [p for p in meta["papers"] if p["year"] == y]
        hak = next((p.get("schoolYear") for p in rows if p.get("schoolYear")), None)
        # 한 장에 연도별 표가 스무 개씩 있는데 이름이 없으면, 소리로 읽는 사람은
        # 지금 어느 해의 표를 지나는지 알 수 없다. 바로 위 연도 제목을 가리킨다.
        out.append(f'<section class="yr"><h2 id="y{y}">{y}년'
                   + (f' <span class="hak">{hak}학년도</span>' if hak else "")
                   + f'</h2>\n<table aria-labelledby="y{y}">\n'
                   '<thead><tr><th scope="col">회차</th><th scope="col">시행일</th>'
                   '<th scope="col">출제</th><th scope="col">자료</th></tr></thead>\n<tbody>\n')
        for p in rows:
            links = []
            for key, label in (("problem", "문제"), ("answer", "정답"), ("solution", "해설")):
                links.append(f'<a href="{E(p[key])}">{label}</a>' if p.get(key)
                             else f'<span class="off">{label}</span>')
            # 학년도는 날짜 옆에만. 회차 이름 뒤에 붙이면 이름의 일부처럼 읽힌다
            hy = f' · {p["schoolYear"]}학년도' if p.get("schoolYear") else ""
            # 뷰어 제목에 쓸 이름의 앞부분. 뒤(문제/정답/해설 + 확장자)는 링크마다
            # 다르지만 링크 글자와 주소에서 그대로 읽어낼 수 있어 site.js에 맡긴다 —
            # 링크마다 온이름을 적으면 이 나무가 600KB 두꺼워진다.
            out.append(f'<tr data-nm="{E(name_prefix(p["year"], p["title"], name))}">'
                       f'<th scope="row">{E(p["title"])}</th>'
                       f'<td>{E(p["date"])}{hy}</td>'
                       f'<td><span class="src s-{"gov" if p["source"]=="평가원" else "edu"}">'
                       f'{E(p["source"])}</span></td>'
                       f'<td class="dl">{" ".join(links)}</td></tr>\n')
        out.append("</tbody>\n</table>\n</section>\n")

    out.append(f"""<section class="also">
  <h2>같은 {E(meta['group'])} 과목</h2>
  <p class="chips">{{SIBLINGS}}</p>
</section>""")
    out.append(foot(2))
    return "".join(out)


def index_page(index):
    canon = f"{SITE}s/"
    n = sum(len(g["subjects"]) for gr in index["grades"] for g in gr["groups"])
    title = f"과목별 기출문제 {n}과목 — 기출 직행"
    desc = (f"고1·고2·고3 {n}개 과목의 수능·모의평가·전국연합학력평가 기출 문제지 "
            f"{index['count']:,}회차. 과목을 고르면 전 회차의 문제·정답·해설 원본 "
            "PDF 주소가 나옵니다.")
    out = [head(title, desc, canon, 1), crumbs_top(),
           f"""<header class="pg">
  <p class="kicker">문 제 지 원 본 직 행</p>
  <h1>과목별 기출문제</h1>
  <p class="lead">2006년 시행분부터 <b>{index['count']:,}회차 · {n}과목</b>.
  과목을 고르면 그 과목의 전 회차가 연도별로 나오고, 문제·정답·해설은 EBSi 원본
  파일로 바로 갑니다. 수록된 가장 최근 시행일은 {E(index['updated'])}입니다.</p>
  <p class="yrnote"><b>연도는 시행 연도입니다.</b> 평가원 시험(수능·6·9월 모평)은
  학년도가 한 해 뒤라 함께 적었습니다 — <b>2025년 11월 시행 = 2026학년도 수능</b>.
  교육청 전국연합학력평가는 학년도를 쓰지 않습니다.</p>
  <p class="go"><a class="app" href="../">앱 화면에서 보기</a>
     <a href="../data/index.json">전 과목 JSON</a>
     <a href="../llms.txt">llms.txt</a></p>
</header>
"""]
    for gr in index["grades"]:
        out.append(f'<section class="yr"><h2>{E(gr["label"])}</h2>\n')
        for g in gr["groups"]:
            out.append(f'<h3>{E(g["name"])}</h3>\n<ul class="subs">\n')
            for s in g["subjects"]:
                out.append(f'<li><a href="{gr["code"]}/{s["id"]}.html">{E(s["name"])}</a>'
                           f'<span class="cnt">{s["count"]}회차</span></li>\n')
            out.append("</ul>\n")
        out.append("</section>\n")
    out.append(foot(1))
    return "".join(out)


def sitemap(pages):
    """주소마다 그 페이지가 실제로 마지막으로 바뀐 날을 적는다.

    구글은 <priority>와 <changefreq>를 아예 무시한다고 문서에 적어 두었으므로
    넣지 않는다. <lastmod>는 '한결같이 정확할 때만' 쓴다고 했는데, 예전에는
    51개 주소에 전부 같은 날짜(사이트 전체의 최신 시행일)를 박아 두어서
    바뀌지 않은 과목까지 매달 새 날짜를 달고 있었다. 그건 부정확한 신호라
    쓰이지 않느니만 못하다. 이제 과목 페이지는 그 과목의 최신 시행일을 단다.
    """
    body = "".join(f"  <url><loc>{E(u)}</loc><lastmod>{d}</lastmod></url>\n"
                   for u, d in pages)
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            + body + "</urlset>\n")


CSS = """/* tools/build_pages.py 가 쓰는 과목 페이지용 스타일.
   앱 화면(index.html)과 같은 규칙 — 명조는 지면(제호·표제·연도·회차 이름),
   고딕은 조작과 설명.

   테마는 세 갈래다. 아무것도 고르지 않았으면 기기 설정을 따르고(가운데 블록),
   앱 화면에서 밝게·어둡게를 골라 뒀으면 그것을 따른다(data-theme, site.js가 건다).
   기기가 어둡더라도 사람이 밝게를 골랐으면 밝아야 하므로, 가운데 블록은
   :not([data-theme="light"])로 막아 둔다. */
:root{
  --paper:#F5F1E6; --card:#FBF9F3; --ink:#191713; --ink2:#5C5747; --rule:#CFC6AC;
  --mark:#B4342A; --gov:#1F4E79; --edu:#2E6B3E; --btn:#FFFDF7; --off:#6E6754;
}
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]){
    --paper:#161A22; --card:#1F2531; --ink:#ECE7DA; --ink2:#AEB5C2; --rule:#3A4353;
    --mark:#F08379; --gov:#8AC6EA; --edu:#A6D48D; --btn:#262E3B; --off:#9AA5B6;
  }
}
:root[data-theme="dark"]{
  --paper:#161A22; --card:#1F2531; --ink:#ECE7DA; --ink2:#AEB5C2; --rule:#3A4353;
  --mark:#F08379; --gov:#8AC6EA; --edu:#A6D48D; --btn:#262E3B; --off:#9AA5B6;
}
*{box-sizing:border-box}
body{
  margin:0 auto;max-width:900px;padding:20px 16px 40px;
  background:var(--paper);color:var(--ink);
  font-family:"Gijul Sans",sans-serif;font-size:14px;line-height:1.7;
  -webkit-text-size-adjust:100%;
}
a{color:var(--ink)}
a:focus-visible,.dl a:focus-visible{outline:2.5px solid var(--mark);outline-offset:2px}

.crumb{font-size:11.5px;color:var(--ink2);margin:0 0 8px}
.crumb b{color:var(--ink)}
/* 글줄 안이라 높이가 17px였다. 줄 간격은 그대로 두고 닿는 넓이만 넓힌다. */
.crumb a,footer .ln a{display:inline-block;padding:4px 0;min-height:24px}

.pg{border:1.5px solid var(--ink);background:var(--card);padding:18px 20px;margin-bottom:22px}
.pg .kicker{font-family:"Song Myung",serif;font-size:11px;letter-spacing:3.5px;
  color:var(--mark);font-weight:700;margin:0 0 7px}
.pg h1{font-family:"Song Myung",serif;font-size:27px;font-weight:700;margin:0;
  letter-spacing:-.5px;line-height:1.2}
.pg .lead{margin:9px 0 0;font-size:12.5px;color:var(--ink2);line-height:1.65}
/* 연도 안내. 이 자료를 잘못 읽는 자리가 여기 하나뿐이라 표보다 먼저 읽혀야 한다 —
   각주에만 두었더니 회차가 170개인 과목에서는 표를 다 지나야 닿았다. */
.pg .yrnote{margin:11px 0 0;padding:8px 11px;font-size:12px;line-height:1.7;
  color:var(--ink2);background:var(--paper);border-left:3px solid var(--mark)}
.pg .yrnote b{color:var(--ink);font-weight:700}
.pg .facts{margin:11px 0 0;padding:0 0 0 17px;font-size:12px;color:var(--ink2);line-height:1.75}
.pg .facts li{margin:0}
.pg .facts b{color:var(--ink);font-weight:700}
.pg .go{margin:13px 0 0;display:flex;gap:7px;flex-wrap:wrap}
.pg .go a{font-size:12.5px;font-weight:600;text-decoration:none;padding:8px 13px;
  border:1.2px solid var(--ink);background:var(--btn)}
.pg .go a.app{background:var(--ink);color:var(--card)}

.yr{margin:0 0 26px}
.yr h2{font-family:"Song Myung",serif;font-size:19px;font-weight:700;margin:0 0 9px;
  padding-bottom:6px;border-bottom:2px solid var(--ink)}
.yr h3{font-size:12px;font-weight:700;color:var(--ink2);margin:16px 0 6px;
  letter-spacing:1px}
.hak{font-family:"Gijul Sans",sans-serif;font-size:11px;font-weight:400;color:var(--ink2)}

table{width:100%;border-collapse:collapse;font-size:12.5px}
thead th{text-align:left;font-size:10.5px;letter-spacing:.5px;color:var(--ink2);
  font-weight:700;padding:0 8px 6px;border-bottom:1px solid var(--rule)}
tbody th{font-family:"Song Myung",serif;font-size:15px;font-weight:700;text-align:left}
tbody th,tbody td{padding:9px 8px;border-bottom:1px solid var(--rule);vertical-align:middle}
tbody tr:hover{background:var(--card)}
td:nth-child(2){white-space:nowrap;color:var(--ink2);font-size:11.5px}
.src{font-size:10px;font-weight:600;letter-spacing:.5px;padding:1px 7px;
  border:1px solid currentColor;white-space:nowrap}
.s-gov{color:var(--gov)} .s-edu{color:var(--edu)}
.dl{text-align:right;white-space:nowrap}
.dl a{display:inline-block;text-decoration:none;font-weight:600;font-size:11.5px;
  padding:5px 10px;margin-left:4px;border:1.2px solid var(--ink);background:var(--btn)}
.dl .off{display:inline-block;font-size:11.5px;padding:5px 10px;margin-left:4px;
  border:1.2px dashed var(--rule);color:var(--off)}

.subs{list-style:none;margin:0 0 4px;padding:0;display:flex;flex-wrap:wrap;gap:6px}
.subs li{flex:0 0 auto}
.subs a{display:inline-block;text-decoration:none;font-size:13px;padding:7px 13px;
  border:1.2px solid var(--rule);background:var(--card)}
.subs a:hover{border-color:var(--ink)}
.subs .cnt{font-size:10.5px;color:var(--ink2);margin-left:5px}

.also h2{font-family:"Song Myung",serif;font-size:15px;margin:0 0 8px;
  padding-bottom:5px;border-bottom:1px solid var(--rule)}
.chips{margin:0;display:flex;flex-wrap:wrap;gap:6px}
.chips a{text-decoration:none;font-size:12px;padding:5px 11px;
  border:1.2px solid var(--rule);background:var(--card)}
.chips a:hover{border-color:var(--ink)}

footer{margin-top:28px;padding-top:14px;border-top:1.5px solid var(--ink);
  font-size:11px;color:var(--ink2);line-height:1.8}
footer p{margin:0 0 7px}
footer b{color:var(--ink)}
footer .ln{font-weight:600}

/* 좁은 화면에서는 표를 카드처럼 편다 — 가로로 흐르면 링크를 누르기 어렵다 */
@media (max-width:560px){
  thead{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)}
  tbody tr{display:block;border-bottom:1px solid var(--rule);padding:9px 0}
  tbody th,tbody td{display:inline-block;border:0;padding:2px 6px}
  tbody th{display:block;font-size:16px}
  .dl{display:block;text-align:left;margin-top:5px}
  .dl a,.dl .off{margin:0 4px 0 0}
}
"""


JS = """/* tools/build_pages.py 가 쓴다. 손으로 고치지 말 것.
   과목 페이지에 붙는 유일한 스크립트다. 두 가지만 한다.

   1) 앱 화면에서 골라 둔 테마를 여기서도 따른다. 같은 출처라 저장소를 그대로
      읽을 수 있다. 기기가 어두워도 사람이 '밝게'를 골라 뒀으면 밝아야 한다.
   2) 앱 안에서 열렸으면 문제·정답·해설을 창구로 넘긴다. 그냥 두면 앱이 주소만
      보고 뷰어를 여는데, 그때 제목이 EBSi 원본 파일명(g_bio1_mun_3WDW7H97.pdf)이
      된다. 사람이 읽는 이름은 data-nm에 실어 두었다.

   CSP가 인라인 스크립트를 막으므로 파일로 따로 둔다. <head>에서 그냥(defer 없이)
   불러야 첫 그림 전에 테마가 걸려 화면이 번쩍이지 않는다. */
(function(){
  var KEY = "gijul.theme.v1";
  var BAR = { light:"#191713", dark:"#161A22" };
  var media = matchMedia("(prefers-color-scheme: dark)");

  function systemDark(){
    try{
      if(typeof GijulNative !== "undefined" && GijulNative && GijulNative.systemDark)
        return !!GijulNative.systemDark();
    }catch(e){}
    return media.matches;
  }

  function apply(){
    var pref = "auto";
    try{ pref = localStorage.getItem(KEY) || "auto"; }catch(e){}
    if(pref !== "light" && pref !== "dark") pref = "auto";
    var t = pref === "auto" ? (systemDark() ? "dark" : "light") : pref;
    document.documentElement.setAttribute("data-theme", t);
    var bar = document.querySelector('meta[name="theme-color"]');
    if(bar) bar.setAttribute("content", BAR[t]);
  }

  apply();
  media.addEventListener("change", apply);
  /* 앱은 액티비티를 다시 만들지 않으므로 테마가 바뀌면 이렇게 알려온다 */
  window.gijulThemeChanged = apply;
  /* 다른 탭에서 앱 화면의 테마를 바꿨을 때 */
  addEventListener("storage", function(e){ if(e.key === KEY) apply(); });

  /* 앱 안에서만 — 브라우저에서는 평범한 링크가 맞다 */
  try{
    if(typeof GijulNative === "undefined" || !GijulNative || !GijulNative.openPaper) return;
  }catch(e){ return; }
  addEventListener("click", function(e){
    var a = e.target.closest && e.target.closest(".dl a[href]");
    if(!a || e.defaultPrevented || e.button) return;
    var row = a.closest("tr");
    if(!row || !row.dataset.nm) return;
    /* 앱 화면의 fileName()과 같은 이름을 여기서 맞춘다:
       "<연도> <회차> <과목>" + " " + "문제|정답|해설" + "." + 확장자 */
    var nm = row.dataset.nm + " " + a.textContent.trim()
           + "." + a.href.split("?")[0].split(".").pop().toLowerCase();
    e.preventDefault();
    try{ GijulNative.openPaper(a.href, nm); }
    catch(err){ location.href = a.href; }
  });
})();
"""


def name_prefix(year, title, subject):
    """뷰어 제목에 쓸 이름의 앞부분. 앱 화면의 fileName()과 같은 규칙이라야 한다 —
    받아둔 자료에서 열 때와 목록에서 열 때와 여기서 열 때가 다르면 안 된다.
    뒤에 ' 문제.pdf' 꼴이 붙는 것은 site.js가 한다."""
    base = re.sub(r'[/\\:*?"<>|\x00-\x1f]', "", f"{year} {title} {subject}")
    return re.sub(r"\s+", " ", base).strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data")
    ap.add_argument("--out", default="s")
    a = ap.parse_args()

    data = ROOT / a.data
    index = json.loads((data / "index.json").read_text(encoding="utf-8"))
    out = ROOT / a.out
    if out.exists():
        shutil.rmtree(out)            # 과목이 사라지면 낡은 페이지도 사라져야 한다
    out.mkdir(parents=True)
    (out / "paper.css").write_text(CSS, encoding="utf-8")
    (out / "site.js").write_text(JS, encoding="utf-8")

    n, pages = 0, []
    for gr in index["grades"]:
        (out / gr["code"]).mkdir(exist_ok=True)
        for g in gr["groups"]:
            # 같은 과목군끼리 서로 이어 준다 — 검색엔진도 사람도 옆 과목으로 넘어간다
            sibs = {s["id"]: " ".join(
                f'<a href="{o["id"]}.html">{E(o["name"])}</a>'
                for o in g["subjects"] if o["id"] != s["id"]) or "<span>없습니다</span>"
                for s in g["subjects"]}
            for s in g["subjects"]:
                meta = json.loads((data / gr["code"] / f'{s["id"]}.json')
                                  .read_text(encoding="utf-8"))
                page = subject_page(meta, s).replace("{SIBLINGS}", sibs[s["id"]])
                (out / gr["code"] / f'{s["id"]}.html').write_text(page, encoding="utf-8")
                # 이 페이지가 실제로 바뀌는 날은 이 과목에 새 회차가 붙는 날이다
                pages.append((f'{SITE}s/{gr["code"]}/{s["id"]}.html',
                              meta["papers"][0]["date"]))
                n += 1

    (out / "index.html").write_text(index_page(index), encoding="utf-8")
    pages.insert(0, (SITE, index["updated"]))
    pages.insert(1, (f"{SITE}s/", index["updated"]))
    (ROOT / "sitemap.xml").write_text(sitemap(pages), encoding="utf-8")

    kb = sum(f.stat().st_size for f in out.rglob("*")) / 1024
    print(f"s/ 과목 페이지 {n}장 + 색인 ({kb:,.0f}KB), sitemap.xml", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
