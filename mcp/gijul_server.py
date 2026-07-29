#!/usr/bin/env python3
"""기출 직행 MCP 서버 — Claude가 기출 문제지를 직접 찾아오게 한다.

배포된 정적 JSON을 읽으므로 이 저장소를 클론하지 않아도 되고, 월간 갱신도
그대로 따라온다. 받아온 목록은 메모리에 캐시한다.

설치:
    pip install "mcp[cli]" httpx

Claude Desktop — claude_desktop_config.json 의 mcpServers 에:
    "기출직행": { "command": "python3", "args": ["/절대/경로/gijul_server.py"] }

Claude Code:
    claude mcp add 기출직행 -- python3 /절대/경로/gijul_server.py
"""
import difflib
import logging
import os
import sys

import httpx

# stdio로 프로토콜을 주고받으므로 라이브러리 로그가 섞이면 안 된다
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

# mcp 2.x는 MCPServer, 1.x는 FastMCP — 이름만 다르고 tool()·run() 사용법은 같다
try:
    from mcp.server import MCPServer as _Server
except ImportError:  # pragma: no cover
    from mcp.server.fastmcp import FastMCP as _Server

SITE = os.environ.get("GIJUL_SITE", "https://mangom72.github.io/Direct-mogo/")

mcp = _Server("기출 직행")
_cache: dict[str, dict] = {}


def fetch(path: str) -> dict:
    if path not in _cache:
        r = httpx.get(SITE + path, timeout=30, follow_redirects=True)
        r.raise_for_status()
        _cache[path] = r.json()
    return _cache[path]


def catalog() -> list[dict]:
    """(학년, 과목군, 과목) 을 납작하게 편 목록."""
    out = []
    for g in fetch("data/index.json")["grades"]:
        for group in g["groups"]:
            for s in group["subjects"]:
                out.append({**s, "grade": g["code"], "gradeLabel": g["label"],
                            "group": group["name"]})
    return out


# 과목명의 Ⅰ·Ⅱ는 키보드로 치기 어려워 '생명과학1'처럼 들어온다.
# 그대로 비교하면 '생명과학1'이 생명과학Ⅱ로 잡히므로 양쪽을 아라비아 숫자로 눕힌다.
_ROMAN = str.maketrans({"Ⅰ": "1", "Ⅱ": "2", "Ⅲ": "3", "Ⅳ": "4",
                        "ⅰ": "1", "ⅱ": "2", "ⅲ": "3", "ⅳ": "4"})


def norm(s: str) -> str:
    return s.translate(_ROMAN).replace(" ", "").replace("·", "").lower()


def resolve(subject: str, grade: str | None) -> dict | None:
    """과목명을 찾는다. 정확히 → 부분일치 → 비슷한 이름 순으로 눅여 간다."""
    items = [s for s in catalog() if not grade or s["grade"] == grade]
    q = norm(subject)
    for s in items:
        if norm(s["name"]) == q or s["id"] == subject.strip():
            return s
    hit = [s for s in items if q in norm(s["name"])]
    if hit:
        return hit[0]
    near = difflib.get_close_matches(q, [norm(s["name"]) for s in items], 1, 0.6)
    return next((s for s in items if norm(s["name"]) == near[0]), None) if near else None


@mcp.tool()
def list_subjects(grade: str = "") -> str:
    """과목 목록을 준다. grade 는 D300(고3·N수)·D200(고2)·D100(고1), 비우면 전체."""
    items = [s for s in catalog() if not grade or s["grade"] == grade]
    if not items:
        return f"'{grade}' 에 해당하는 과목이 없습니다. D300·D200·D100 중 하나를 쓰세요."
    lines, seen = [], None
    for s in items:
        key = (s["gradeLabel"], s["group"])
        if key != seen:
            lines.append(f"\n[{s['gradeLabel']} · {s['group']}]")
            seen = key
        yrs = s["years"]
        lines.append(f"  {s['name']} (id={s['id']}) — {s['count']}회차, "
                     f"{min(yrs)}~{max(yrs)}년 시행")
    return "\n".join(lines).strip()


@mcp.tool()
def find_papers(subject: str, year: int = 0, source: str = "", grade: str = "",
                limit: int = 20) -> str:
    """기출 회차와 문제·정답·해설 주소를 찾는다.

    subject: 과목명 또는 과목 id (예: '생명과학Ⅰ', '미적분', '158')
    year:    시행 연도. 학년도가 아니다 — 2026학년도 수능은 year=2025
    source:  '평가원'(수능·모평) 또는 '교육청'(학력평가). 비우면 전체
    grade:   D300·D200·D100. 같은 과목명이 여러 학년에 있을 때만 필요
    """
    s = resolve(subject, grade or None)
    if not s:
        return (f"'{subject}' 과목을 찾지 못했습니다. list_subjects 로 목록을 확인하세요.")
    papers = fetch(s["data"])["papers"]
    if year:
        papers = [p for p in papers if p["year"] == year]
    if source:
        papers = [p for p in papers if p["source"] == source]
    if not papers:
        return (f"{s['gradeLabel']} {s['name']}: 조건에 맞는 회차가 없습니다 "
                f"(수록 연도 {min(s['years'])}~{max(s['years'])}년 시행)")

    head = f"{s['gradeLabel']} · {s['name']} — {len(papers)}회차"
    if len(papers) > limit:
        head += f" (최근 {limit}개만 표시)"
    out = [head]
    for p in papers[:limit]:
        y = f"{p['year']}년 시행"
        if p.get("schoolYear"):
            y += f"({p['schoolYear']}학년도)"
        out.append(f"\n■ {y} {p['title']} · {p['source']} · {p['date']}")
        for label, key in (("문제", "problem"), ("정답", "answer"), ("해설", "solution")):
            out.append(f"   {label}: {p[key] or '없음'}")
    return "\n".join(out)


@mcp.tool()
def site_info() -> str:
    """수록 범위와 연도 표기 규칙을 알려준다."""
    i = fetch("data/index.json")
    return (f"{i['name']} — {i['description']}\n"
            f"수록 {i['count']:,}회차, 갱신 {i['updated']}\n화면: {i['site']}\n\n{i['note']}")


if __name__ == "__main__":
    try:
        mcp.run()
    except KeyboardInterrupt:
        sys.exit(0)
