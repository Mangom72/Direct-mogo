#!/usr/bin/env python3
"""index.html의 페이로드를 AI·프로그램이 읽을 수 있는 정적 JSON으로 내보낸다.

앱은 자료를 gzip+base64로 HTML 안에 넣어 두는데, 그러면 JS를 돌리지 못하는
쪽에서는 압축 덩어리만 보인다. 같은 자료를 평범한 JSON으로도 함께 깔아
서버 없이 조회할 수 있게 한다.

과목 단위로 쪼개는 이유: 전체를 한 번에 삼키기는 부담스럽지만 과목 하나는 가볍다.
정확한 크기는 weigh()가 매번 재서 llms.txt에 적는다 — 손으로 적어 둔 숫자는 회차가
늘면서 실제와 세 배까지 벌어져 있었다.

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

    total, latest, grades = 0, "", []
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
                latest = max(latest, papers[0]["date"])   # 이미 내림차순
            if subs:
                gnode["groups"].append({"name": group["name"], "subjects": subs})
        grades.append(gnode)

    index = {
        "name": "기출 직행",
        "site": SITE,
        "description": "수능·모의평가·전국연합학력평가 기출 문제지 원본 PDF 목록",
        # 돌린 날이 아니라 **자료가 닿아 있는 날** — 수록된 가장 최근 시행일이다.
        # 전에는 date.today()였는데, 새 회차가 하나도 없어도 매번 오늘 날짜로 바뀌었다.
        # 읽는 쪽에는 자료가 갱신된 것처럼 보이고, 갱신 워크플로의 '변경 없으면
        # 커밋하지 않는다'는 판정도 늘 참이 되어 무의미했다.
        "updated": latest,
        "count": total,
        "note": ("연도(year)는 모두 시행 연도입니다. 평가원 시험(수능·6/9월 모의평가)의 "
                 "학년도는 시행 연도 + 1이며 schoolYear로 함께 넣었습니다. "
                 "교육청 학력평가는 관례상 시행 연도로만 부르므로 schoolYear가 없습니다."),
        "fields": {
            "problem": "문제지 PDF 주소 (없으면 null)",
            "answer": "정답 이미지 주소 (없으면 null)",
            "solution": "해설 PDF 주소 (없으면 null)",
            "source": "평가원 또는 교육청",
            "updated": "수록된 가장 최근 시행일. 이 스크립트를 돌린 날이 아니라 자료가 닿아 있는 날입니다",
        },
        "grades": grades,
    }
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")

    nsub = sum(len(g["subjects"]) for gr in grades for g in gr["groups"])
    Path("llms.txt").write_text(llms_txt(index, nsub, weigh(out)), encoding="utf-8")

    print(f"data/index.json + 과목 {nsub}개 ({total}회차), llms.txt", file=sys.stderr)
    return 0


def weigh(out):
    """안내문에 적을 숫자를 자료에서 직접 잰다.

    예전에는 '과목 하나가 9KB, 전부 435KB'처럼 손으로 적어 뒀는데, 회차가 늘면서
    실제와 세 배 가까이 벌어져 있었다. 읽는 쪽이 기계인 문서에서 이런 숫자가
    틀리면 그대로 잘못된 판단이 된다. 잴 수 있는 것은 재서 쓴다.
    """
    sizes, gap, total = [], {"problem": 0, "answer": 0, "solution": 0}, 0
    for f in sorted(out.glob("D*/*.json")):
        sizes.append(f.stat().st_size / 1024)
        for p in json.loads(f.read_text(encoding="utf-8"))["papers"]:
            total += 1
            for k in gap:
                if not p.get(k):
                    gap[k] += 1
    sizes.sort()
    worst = max(gap, key=gap.get)
    return {
        "median": sizes[len(sizes) // 2],
        "all": sum(sizes),
        "gap": gap,
        "worst": worst,
        "worst_pct": round(gap[worst] * 100 / total) if total else 0,
    }


def llms_txt(index, nsub, w):
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
    return f"""# 기출 직행 (Gijul Jikhaeng)

> 한국 수능·모의평가·전국연합학력평가 **기출 문제지 원본 PDF** 목록입니다.
> Korean college-entrance mock/past exam papers — an index of publicly hosted PDFs.
> 2006년 시행분부터 {index['count']:,}회차 · {nsub}과목 · 자료 기준 {index['updated']}.

## 30초 요약 / Quick start

이 파일 말고 **이 주소 하나만** 가져가면 됩니다. 인증도 API 키도 서버도 없습니다.

    {SITE}data/index.json

거기 각 과목의 `data` 경로가 있습니다. 그 파일을 받으면 그 과목의 전 회차가 나오고,
회차마다 `problem`(문제지 PDF) · `answer`(정답 이미지) · `solution`(해설 PDF)이
**로그인 없이 바로 열리는 절대 주소**로 들어 있습니다. 그게 전부입니다.

```
curl -s {SITE}data/D300/158.json | head -40     # 고3 생명과학Ⅰ 143회차
```

One JSON index at the URL above lists every subject and its data file. Each paper
carries three absolute, public PDF/PNG links — `problem`, `answer`, `solution`.
No auth, no rate limit, CORS open. Everything below is detail.

사람이 읽는 화면: {SITE} · 과목별 목록: {SITE}s/

## 자료 상태 / Freshness

| | |
|---|---|
| 총 회차 | {index['count']:,} |
| 과목 수 | {nsub} (고3·N수 / 고2 / 고1) |
| 수록 범위 | 2006년 시행분 ~ {index['updated']} |
| 자료 기준일 | {index['updated']} — 수록된 **가장 최근 시행일**입니다. 파일을 만든 날이 아닙니다 |
| 갱신 주기 | 매일 23시(KST) 자동. 시험 당일 저녁이면 대개 그날 회차가 실립니다 |

갱신은 **덧붙이기만** 합니다 — 이미 있는 회차는 고치지 않고 새 시행일만 채웁니다.
따라서 한번 받아 둔 회차의 주소는 계속 유효합니다.

## 경로 규칙

```
{SITE}data/index.json                    과목 목록 (여기서 시작)
{SITE}data/<학년코드>/<과목ID>.json       그 과목의 전 회차
{SITE}s/<학년코드>/<과목ID>.html          같은 내용을 사람이 읽는 페이지

학년코드  D300 = 고3·N수 | D200 = 고2 | D100 = 고1
과목ID    index.json 안의 문자열 그대로. 규칙을 추측하지 마세요 —
          같은 과목이라도 학년마다 다른 번호를 씁니다
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

| 칸 | 뜻 | 비고 |
|---|---|---|
| `title` | 회차 이름 | `수능` / `6월 모평(평가원)` / `7월 학평(인천)` 꼴 |
| `date` | 시행일 `YYYY-MM-DD` | 정렬은 이것으로 하세요 |
| `year` | **시행 연도** | 아래 「연도」 절을 꼭 보세요 |
| `schoolYear` | **학년도** | 평가원 시험에만 있습니다 |
| `source` | `평가원` 또는 `교육청` | 제목으로 가릅니다 |
| `problem` | **문제지** PDF | 시험지 원본. 없으면 `null` |
| `answer` | **정답표** PNG 이미지 | PDF가 아니라 그림입니다. 없으면 `null` |
| `solution` | **해설지** PDF | 풀이. 없으면 `null` |

셋 다 `null`인 회차는 없습니다. 다만 **하나씩 빠진 회차는 흔합니다** — 지금 자료에서
`answer` {w['gap']['answer']:,}건, `solution` {w['gap']['solution']:,}건, `problem` {w['gap']['problem']:,}건이 비어 있습니다.
가장 자주 빠지는 것은 `{w['worst']}` — 전체의 {w['worst_pct']}%입니다. **쓰기 전에 `null`을 확인하세요.**

## 연도 — 여기서 가장 많이 틀립니다

한국 시험은 **시행 연도**와 **학년도**가 다릅니다. 이 자료는 전부 시행 연도 기준입니다.

- `year` = 시험을 **본 해**. 2025년 11월에 본 수능은 `year: 2025`
- `schoolYear` = 그 시험의 **학년도** = 시행 연도 + 1. 위 수능은 `schoolYear: 2026`
- 흔히 "2026 수능"이라고 부르는 것은 **2025년 11월에 시행된** 시험입니다
- 교육청 학력평가는 관례상 시행 연도로만 부르므로 `schoolYear`가 **없습니다**

사용자가 "2026 수능"이라고 하면 학년도를 말하는 것일 가능성이 높습니다.
답할 때는 **"2025년 11월 시행(2026학년도) 수능"처럼 어느 쪽인지 밝혀 주세요.**

## 자주 하는 일

**특정 시험 하나 찾기 — 2026학년도 수능 생명과학Ⅰ**

```python
import json, urllib.request
def get(u): return json.load(urllib.request.urlopen(u))

idx = get("{SITE}data/index.json")
sid = next(s for g in idx["grades"] if g["code"] == "D300"
             for gr in g["groups"] for s in gr["subjects"]
             if s["name"] == "생명과학Ⅰ")
sub = get("{SITE}" + sid["data"])
p = next(p for p in sub["papers"]
         if p["source"] == "평가원" and p.get("schoolYear") == 2026
         and p["title"].startswith("수능"))
print(p["title"], p["date"], p["problem"])
```

**한 과목의 수능만 모으기** — `papers`에서 `title.startswith("수능")`

**최근 3년치만** — `papers`는 이미 시행일 내림차순입니다. 앞에서부터 자르세요

**과목 이름으로 찾기** — `index.json`의 `grades[].groups[].subjects[].name`을 훑습니다.
과목명은 `생명과학Ⅰ`처럼 **로마 숫자(U+2160)** 를 씁니다. `생명과학1`(아라비아 1)이나
`생명과학 I`(라틴 대문자 I)로는 맞지 않습니다

**전 과목을 다 받기** — 하지 마세요. 과목 하나가 중앙값 {w['median']:.0f}KB인데 전부는 {w['all']:,.0f}KB입니다.
필요한 과목만 받는 편이 언제나 빠릅니다

## 안 될 때

| 증상 | 볼 곳 |
|---|---|
| 과목 JSON이 404 | 과목ID를 지어내지 않았는지. `index.json`에 있는 값만 존재합니다 |
| 학년 경로가 404 | `D300`/`D200`/`D100` 셋뿐입니다. `go3`·`3`·`high3` 아닙니다 |
| 과목을 못 찾겠음 | 과목명의 로마 숫자(Ⅰ Ⅱ)를 확인하세요. 학년이 다르면 ID도 다릅니다 |
| PDF 주소가 404 | 원본이 EBSi에서 내려간 것입니다. 이쪽에서는 알 수 없습니다 |
| 연도가 한 해씩 어긋남 | `year`(시행)와 `schoolYear`(학년도)를 섞어 쓴 것입니다 |
| 회차가 기대보다 적음 | 그 과목이 그 해에 시행되지 않았거나 EBSi에 자료가 없는 것입니다 |

이 파일과 `index.json`이 다르면 **`index.json`이 맞습니다** — 자료가 먼저 만들어지고
이 안내문은 그 결과를 옮겨 적습니다.

## 예시 과목

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

권리자 또는 정당한 대리인의 게시중단 요청은 확인 즉시 이행합니다. direct.mogo.dev@gmail.com 또는
https://github.com/Mangom72/Direct-mogo/issues 로 연락 주세요.
"""


if __name__ == "__main__":
    sys.exit(main())
