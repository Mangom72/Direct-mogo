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
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = "https://mangom72.github.io/Direct-mogo/"
REPO = "https://github.com/Mangom72/Direct-mogo"

E = lambda s: html.escape(str(s), quote=True)


def head(title, desc, canon, depth):
    """페이지 머리. depth는 사이트 뿌리까지 거슬러 올라갈 칸 수."""
    up = "../" * depth
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; img-src 'self' data:; style-src 'self'; font-src 'self'; object-src 'none'; base-uri 'none'; form-action 'none'">
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
<link rel="stylesheet" href="{up}fonts/fonts.css">
<link rel="stylesheet" href="{up}s/paper.css">
<meta name="theme-color" content="#191713">
</head>
<body>
"""


def foot(depth, extra=""):
    up = "../" * depth
    return f"""
<footer>
  {extra}
  <p>모든 링크는 EBSi가 공개하여 별도의 인증 없이 접근 가능한 파일 주소로 직접
  연결되며, 이 사이트는 어떤 파일도 저장·재배포하지 않습니다. 문제 자료의 저작권은
  <b>한국교육과정평가원</b> 및 <b>각 시·도교육청</b>에 있습니다.
  권리자께서 요청하시면 지체 없이 내립니다 —
  <a href="{REPO}/blob/main/NOTICE.md">이용 안내</a>.</p>
  <p>연도는 <b>시행 연도</b>입니다. 평가원 시험의 학년도는 시행 연도 + 1이므로
  (2025년 11월 시행 = 2026학년도 수능) 각 회차에 학년도를 함께 적었습니다.
  교육청 학력평가는 관례상 시행 연도로만 부릅니다.</p>
  <p class="ln"><a href="{up}">기출 직행</a> ·
     <a href="{up}s/">전체 과목</a> ·
     <a href="{up}llms.txt">llms.txt</a> ·
     <a href="{REPO}">GitHub</a></p>
</footer>
</body>
</html>
"""


def crumbs(depth, here):
    up = "../" * depth
    return (f'<nav class="crumb" aria-label="위치"><a href="{up}">기출 직행</a>'
            f' <span aria-hidden="true">›</span> <a href="{up}s/">전체 과목</a>'
            f' <span aria-hidden="true">›</span> <b>{E(here)}</b></nav>')


def subject_page(meta, sub):
    """과목 한 개 — 전 회차를 연도별로 묶어 표로."""
    g, gl = meta["grade"], meta["gradeLabel"]
    name, sid, n = meta["subject"], meta["subjectId"], meta["count"]
    canon = f"{SITE}s/{g}/{sid}.html"
    years = sorted({p["year"] for p in meta["papers"]}, reverse=True)
    span = f"{years[-1]}~{years[0]}년" if len(years) > 1 else f"{years[0]}년"
    title = f"{gl} {name} 기출문제 {n}회차 — 기출 직행"
    desc = (f"{gl} {name} 수능·모의평가·전국연합학력평가 기출 문제지 {n}회차 "
            f"({span}). 문제·정답·해설 원본 PDF로 바로 이동합니다.")

    out = [head(title, desc, canon, 2), crumbs(2, f"{gl} {name}")]
    out.append(f"""<header class="pg">
  <p class="kicker">{E(meta['group'])} · {E(gl)}</p>
  <h1>{E(name)} 기출문제</h1>
  <p class="lead">{E(gl)} <b>{E(name)}</b> 전 회차 <b>{n}개</b> ({E(span)}).
  아래 표의 문제·정답·해설은 EBSi 원본 파일로 바로 갑니다.</p>
  <p class="go"><a class="app" href="../../#/{g}/{sid}/all/all">앱 화면에서 보기</a>
     <a href="../../data/{g}/{sid}.json">JSON으로 받기</a></p>
</header>
""")

    for y in years:
        rows = [p for p in meta["papers"] if p["year"] == y]
        hak = next((p.get("schoolYear") for p in rows if p.get("schoolYear")), None)
        out.append(f'<section class="yr"><h2>{y}년'
                   + (f' <span class="hak">{hak}학년도</span>' if hak else "")
                   + "</h2>\n<table>\n<thead><tr><th>회차</th><th>시행일</th>"
                   "<th>출제</th><th>자료</th></tr></thead>\n<tbody>\n")
        for p in rows:
            links = []
            for key, label in (("problem", "문제"), ("answer", "정답"), ("solution", "해설")):
                links.append(f'<a href="{E(p[key])}">{label}</a>' if p.get(key)
                             else f'<span class="off">{label}</span>')
            # 학년도는 날짜 옆에만. 회차 이름 뒤에 붙이면 이름의 일부처럼 읽힌다
            hy = f' · {p["schoolYear"]}학년도' if p.get("schoolYear") else ""
            out.append(f'<tr><th scope="row">{E(p["title"])}</th>'
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
    title = f"과목별 기출문제 목록 ({n}과목 · {index['count']:,}회차) — 기출 직행"
    desc = (f"고1·고2·고3 {n}개 과목의 수능·모의평가·전국연합학력평가 기출 문제지 "
            f"{index['count']:,}회차. 과목을 고르면 전 회차의 문제·정답·해설 원본 "
            "PDF 주소가 나옵니다.")
    out = [head(title, desc, canon, 1),
           f'<nav class="crumb" aria-label="위치"><a href="../">기출 직행</a>'
           f' <span aria-hidden="true">›</span> <b>전체 과목</b></nav>',
           f"""<header class="pg">
  <p class="kicker">문 제 지 원 본 직 행</p>
  <h1>과목별 기출문제</h1>
  <p class="lead">2006년 시행분부터 <b>{index['count']:,}회차 · {n}과목</b>.
  과목을 고르면 그 과목의 전 회차가 연도별로 나오고, 문제·정답·해설은 EBSi 원본
  파일로 바로 갑니다. 수록된 가장 최근 시행일은 {E(index['updated'])}입니다.</p>
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
    out.append(foot(1, '<p>기계로 읽으실 분은 <a href="../llms.txt">llms.txt</a>와 '
                       '<a href="../data/index.json">data/index.json</a>을 보세요.</p>'))
    return "".join(out)


def sitemap(index, updated):
    urls = [(SITE, "1.0"), (f"{SITE}s/", "0.9")]
    for gr in index["grades"]:
        for g in gr["groups"]:
            for s in g["subjects"]:
                urls.append((f"{SITE}s/{gr['code']}/{s['id']}.html", "0.8"))
    body = "".join(
        f"  <url><loc>{E(u)}</loc><lastmod>{updated}</lastmod>"
        f"<changefreq>monthly</changefreq><priority>{pr}</priority></url>\n"
        for u, pr in urls)
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            + body + "</urlset>\n")


CSS = """/* tools/build_pages.py 가 쓰는 과목 페이지용 스타일.
   앱 화면(index.html)과 같은 규칙 — 명조는 지면(제호·표제·연도·회차 이름),
   고딕은 조작과 설명. 스크립트가 없으므로 테마는 기기 설정을 그대로 따른다. */
:root{
  --paper:#F5F1E6; --card:#FBF9F3; --ink:#191713; --ink2:#5C5747; --rule:#CFC6AC;
  --mark:#B4342A; --gov:#1F4E79; --edu:#2E6B3E; --btn:#FFFDF7; --off:#7A725F;
}
@media (prefers-color-scheme: dark){
  :root{
    --paper:#161A22; --card:#1F2531; --ink:#ECE7DA; --ink2:#AEB5C2; --rule:#3A4353;
    --mark:#F08379; --gov:#8AC6EA; --edu:#A6D48D; --btn:#262E3B; --off:#9AA5B6;
  }
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

.crumb{font-size:11.5px;color:var(--ink2);margin:0 0 14px}
.crumb b{color:var(--ink)}

.pg{border:1.5px solid var(--ink);background:var(--card);padding:18px 20px;margin-bottom:22px}
.pg .kicker{font-family:"Song Myung",serif;font-size:11px;letter-spacing:3.5px;
  color:var(--mark);font-weight:700;margin:0 0 7px}
.pg h1{font-family:"Song Myung",serif;font-size:27px;font-weight:700;margin:0;
  letter-spacing:-.5px;line-height:1.2}
.pg .lead{margin:9px 0 0;font-size:12.5px;color:var(--ink2);line-height:1.65}
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

    n = 0
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
                n += 1

    (out / "index.html").write_text(index_page(index), encoding="utf-8")
    (ROOT / "sitemap.xml").write_text(sitemap(index, index["updated"]), encoding="utf-8")

    kb = sum(f.stat().st_size for f in out.rglob("*")) / 1024
    print(f"s/ 과목 페이지 {n}장 + 색인 ({kb:,.0f}KB), sitemap.xml", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
