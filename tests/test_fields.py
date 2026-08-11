"""회차 이름표(id)·시험 종류(type)·유형(form)·과목 별칭(aliases) 점검."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from harness import ROOT      # 이 시험은 브라우저도 서버도 쓰지 않는다
import json, glob, pathlib, collections, re, sys

BAD = []
def ck(cond, msg):
    if not cond: BAD.append(msg)

papers = []
for f in sorted(glob.glob("data/D*/*.json")):
    papers += json.loads(pathlib.Path(f).read_text(encoding="utf-8"))["papers"]
print(f"회차 {len(papers):,}")

ids = [p["id"] for p in papers]
dup = [k for k, c in collections.Counter(ids).items() if c > 1]
ck(not dup, f"id 겹침 {len(dup)}건 — 예: {dup[:3]}")
print(f"  id 유일: {not dup}")

ck(all(re.fullmatch(r"D[123]00-\d+-\d{8,9}(-\S+)?", i) for i in ids), "id 꼴이 어긋난 것이 있습니다")

types = collections.Counter(p["type"] for p in papers)
ck(set(types) <= {"수능", "모평", "학평", "예비시행", "기타"}, f"모르는 type: {set(types)}")
ck(types.get("기타", 0) == 0, f"type을 못 가른 회차 {types.get('기타',0)}건")
print(f"  type: {dict(types)}")

# type 과 source 가 서로 어긋나면 안 된다
for p in papers:
    if p["type"] in ("수능", "모평"): ck(p["source"] == "평가원", f"{p['id']}: {p['type']}인데 {p['source']}")
    if p["type"] == "학평": ck(p["source"] == "교육청", f"{p['id']}: 학평인데 {p['source']}")

# form 은 제목에 유형이 적힌 회차에만 있어야 한다
FORM = re.compile(r"(가형|나형|A형|B형|홀수형|짝수형|(?<![A-Za-z])[AB](?![A-Za-z가-힣]))")
for p in papers:
    has = bool(FORM.search(p["title"]))
    ck(has == ("form" in p), f"{p['id']}: 제목 {p['title']!r} 과 form {p.get('form')!r} 이 어긋남")
print(f"  form 달린 회차: {sum(1 for p in papers if 'form' in p)}")

# schoolYear 는 평가원에만, 그리고 시행 연도 + 1
for p in papers:
    if p["source"] == "평가원": ck(p.get("schoolYear") == p["year"] + 1, f"{p['id']}: schoolYear 어긋남")
    else: ck("schoolYear" not in p, f"{p['id']}: 교육청인데 schoolYear가 있습니다")

idx = json.loads(pathlib.Path("data/index.json").read_text(encoding="utf-8"))
for g in idx["grades"]:
    seen = collections.defaultdict(set)
    for grp in g["groups"]:
        for s in grp["subjects"]:
            ck("aliases" in s, f"{s['name']}: aliases 없음")
            ck(s["name"] not in s["aliases"], f"{s['name']}: 정식 이름이 별칭에 들어 있습니다")
            for a in [s["name"]] + s["aliases"]: seen[a].add(s["name"])
    for a, who in seen.items():
        ck(len(who) == 1, f"{g['code']}에서 '{a}' 가 여럿을 가리킵니다: {sorted(who)}")

# 학생이 실제로 쓰는 말이 실제로 걸리는지
def find(grade, word):
    for g in idx["grades"]:
        if g["code"] != grade: continue
        for grp in g["groups"]:
            for s in grp["subjects"]:
                if word == s["name"] or word in s["aliases"]: return s["name"]
    return None
for word, want in [("생윤","생활과 윤리"), ("확통","확률과 통계"), ("생명과학1","생명과학Ⅰ"),
                   ("사문","사회·문화"), ("화작","화법과 작문"), ("지2","지구과학Ⅱ"),
                   ("한지","한국지리"), ("언매","언어와 매체")]:
    got = find("D300", word)
    ck(got == want, f"'{word}' → {got!r} (기대 {want!r})")
print(f"  줄임말 8개 전부 맞음: {not any('→' in b for b in BAD)}")

print("\n=== 문제:", "없음" if not BAD else "")
for b in BAD[:12]: print("  ★", b)
sys.exit(1 if BAD else 0)
