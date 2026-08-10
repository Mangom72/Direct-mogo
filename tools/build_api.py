#!/usr/bin/env python3
"""index.html의 페이로드를 AI·프로그램이 읽을 수 있는 정적 JSON으로 내보낸다.

앱은 자료를 gzip+base64로 HTML 안에 넣어 두는데, 그러면 JS를 돌리지 못하는
쪽에서는 압축 덩어리만 보인다. 같은 자료를 평범한 JSON으로도 함께 깔아
서버 없이 조회할 수 있게 한다.

과목 단위로 쪼개는 이유: 전체는 435KB라 한 번에 삼키기 부담스럽지만,
과목 하나는 중앙값 9KB라 필요한 것만 받아 가면 된다.

파일 경로 코드는 여기서 절대 URL로 풀어 둔다. 읽는 쪽이 디렉터리 규칙을
알 필요가 없어야 한다.

사용법:
    python3 tools/build_api.py [--index index.html] [--out data]
"""
import argparse
import base64
import gzip
import json
import re
import sys
from datetime import date
from pathlib import Path

BASE = "https://wdown.ebsi.co.kr/W61001/01exam"
DIRS = ["go3", "go2", "go1", "mobile"]
SITE = "https://mangom72.github.io/Direct-mogo/"
GRADE_LABEL = {"D300": "고3·N수", "D200": "고2", "D100": "고1"}


def url(code, date_str):
    if not code:
        return None
    if code[0] == "!":
        return BASE + code[1:]
    return f"{BASE}/{date_str}/{DIRS[int(code[0])]}/{code[1:]}"


def source_of(title):
    """앱의 kindOf()와 같은 규칙 — 제목으로 출제 기관을 가른다."""
    return "평가원" if (title.startswith("수능") or "평가원" in title) else "교육청"


def read_payload(text):
    m = re.search(r'id="payload"[^>]*>([^<]+)<', text)
    if not m:
        raise SystemExit("index.html에서 payload를 찾지 못했습니다")
    return json.loads(gzip.decompress(base64.b64decode(m.group(1).strip())))


def read_groups(text):
    """GROUPS 상수에서 (학년 → 과목군 → [(과목명, 코드)]) 를 그대로 읽어온다."""
    i = text.find("const GROUPS")
    block = text[i:text.find("\n};", i)]
    out, grade, group = {}, None, None
    token = re.compile(r'\b(D\d00)\s*:|\["([^"]+)",\[|\["([^"]+)","(\d+)"\]')
    for m in token.finditer(block):
        if m.group(1):
            grade = m.group(1)
            out[grade] = []
        elif m.group(2):
            group = {"name": m.group(2), "subjects": []}
            out[grade].append(group)
        elif group is not None:
            group["subjects"].append((m.group(3), m.group(4)))
    if not out or not any(g for g in out.values()):
        raise SystemExit("GROUPS를 읽지 못했습니다")
    return out


def paper(row, year):
    title, d = row[0], row[1]
    src = source_of(title)
    out = {
        "title": title,
        "date": f"{d[:4]}-{d[4:6]}-{d[6:8]}",
        "year": int(year),
        "source": src,
        "problem": url(row[2], d),
        "answer": url(row[3], d),
        "solution": url(row[4], d),
    }
    # 학년도는 평가원 시험에만 의미가 있다 (시행 연도 + 1)
    if src == "평가원":
        out["schoolYear"] = int(year) + 1
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", default="index.html")
    ap.add_argument("--out", default="data")
    args = ap.parse_args()

    text = Path(args.index).read_text(encoding="utf-8")
    db = read_payload(text)
    groups = read_groups(text)
    out = Path(args.out)

    total, grades = 0, []
    for grade, glist in groups.items():
        gnode = {"code": grade, "label": GRADE_LABEL.get(grade, grade), "groups": []}
        for group in glist:
            subs = []
            for name, sid in group["subjects"]:
                years = db.get(grade, {}).get(sid, {})
                papers = []
                for y in sorted(years, reverse=True):
                    papers += [paper(r, y) for r in years[y]]
                papers.sort(key=lambda p: p["date"], reverse=True)
                if not papers:
                    continue
                rel = f"{grade}/{sid}.json"
                (out / grade).mkdir(parents=True, exist_ok=True)
                (out / rel).write_text(json.dumps({
                    "grade": grade, "gradeLabel": gnode["label"],
                    "group": group["name"], "subject": name, "subjectId": sid,
                    "count": len(papers), "papers": papers,
                }, ensure_ascii=False, indent=1), encoding="utf-8")
                subs.append({
                    "id": sid, "name": name, "count": len(papers),
                    "years": sorted({p["year"] for p in papers}, reverse=True),
                    "data": f"data/{rel}",
                })
                total += len(papers)
            if subs:
                gnode["groups"].append({"name": group["name"], "subjects": subs})
        grades.append(gnode)

    index = {
        "name": "기출 직행",
        "site": SITE,
        "description": "수능·모의평가·전국연합학력평가 기출 문제지 원본 PDF 목록",
        "updated": date.today().isoformat(),
        "count": total,
        "note": ("연도(year)는 모두 시행 연도입니다. 평가원 시험(수능·6/9월 모의평가)의 "
                 "학년도는 시행 연도 + 1이며 schoolYear로 함께 넣었습니다. "
                 "교육청 학력평가는 관례상 시행 연도로만 부르므로 schoolYear가 없습니다."),
        "fields": {
            "problem": "문제지 PDF 주소 (없으면 null)",
            "answer": "정답 이미지 주소 (없으면 null)",
            "solution": "해설 PDF 주소 (없으면 null)",
            "source": "평가원 또는 교육청",
        },
        "grades": grades,
    }
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")

    nsub = sum(len(g["subjects"]) for gr in grades for g in gr["groups"])
    Path("llms.txt").write_text(llms_txt(index, nsub), encoding="utf-8")

    print(f"data/index.json + 과목 {nsub}개 ({total}회차), llms.txt", file=sys.stderr)
    return 0


def llms_txt(index, nsub):
    """AI가 이 사이트를 어떻게 읽으면 되는지 알려주는 안내문 (llms.txt 관례)."""
    def pick(grade, sid):
        for gr in index["grades"]:
            if gr["code"] != grade:
                continue
            for g in gr["groups"]:
                for s in g["subjects"]:
                    if s["id"] == sid:
                        return f"- [{gr['label']} {s['name']}]({SITE}{s['data']}) — {s['count']}회차"
        return ""
    return f"""# 기출 직행

> 수능·모의평가·전국연합학력평가 **기출 문제지 원본 PDF** 목록입니다.
> 2006년 시행분부터 {index['count']:,}회차 · {nsub}과목. 사람이 쓰는 화면은 {SITE} 입니다.

자료는 **정적 JSON**으로 함께 제공됩니다. 서버도 인증도 API 키도 필요 없습니다.
아래 주소를 그대로 가져가면 됩니다. (화면용 HTML은 자료가 압축돼 있어 읽어도 소용없습니다)

## 시작점

- [{SITE}data/index.json]({SITE}data/index.json) — 학년·과목군·과목 목록과 과목별 JSON 주소

## 쓰는 법

1. `data/index.json`에서 원하는 과목을 찾습니다. 각 과목에 `data` 경로가 들어 있습니다
2. 그 파일을 받으면 해당 과목의 **전 회차**가 나옵니다
3. 각 회차의 `problem`·`answer`·`solution`이 **바로 열리는 절대 주소**입니다. 로그인 불필요

```
{SITE}data/<학년코드>/<과목ID>.json
학년코드: D300(고3·N수) / D200(고2) / D100(고1)
```

## 회차 하나의 생김새

```json
{{
  "title": "6월 모평(평가원)",
  "date": "2026-06-04",
  "year": 2026,
  "schoolYear": 2027,
  "source": "평가원",
  "problem": "https://wdown.ebsi.co.kr/.../g_bio1_mun_....pdf",
  "answer": "https://wdown.ebsi.co.kr/.../h3_m_g_bio1_ans_....png",
  "solution": "https://wdown.ebsi.co.kr/.../g_bio1_hsj_....pdf"
}}
```

## 연도를 다룰 때 (중요)

- `year`는 **시행 연도**입니다
- 평가원 시험(수능·6·9월 모의평가)은 `schoolYear`가 함께 있습니다. **학년도 = 시행 연도 + 1**
- 교육청 학력평가는 관례상 시행 연도로만 부르므로 `schoolYear`가 없습니다
- 사용자에게 답할 때는 **"2025년 시행(2026학년도) 수능"처럼 어느 쪽인지 밝혀 주세요**

## 예시

{pick('D300','158')}
{pick('D300','140117')}
{pick('D300','80003')}

## 출처 및 이용 조건

모든 주소는 EBSi가 공개하여 별도의 인증 없이 접근 가능한 파일로 직접 연결됩니다.
본 사이트는 문제 자료를 저장하거나 재배포하지 아니하며, 회차 명칭·시행일·파일 주소 등
목록 정보만을 보유합니다. 문제 자료에 대한 저작권은 한국교육과정평가원 및 각
시·도교육청에 귀속됩니다.

여기 배포되는 목록 정보(JSON)와 이를 만드는 코드는 MIT 라이선스에 따라 자유로이
이용할 수 있습니다. 이용 조건의 전문은 다음에 따릅니다.

https://github.com/Mangom72/Direct-mogo/blob/main/NOTICE.md
"""


if __name__ == "__main__":
    sys.exit(main())
