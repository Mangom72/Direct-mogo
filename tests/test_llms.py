"""llms.txt — 규격에 맞는가, 그리고 적힌 대로 따라가면 실제로 파일이 나오는가."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from harness import CHROME, ROOT, SHOT, site, Serve
_srv, SITE = site()
import re, json, pathlib, urllib.request, sys
R = ROOT
LOCAL = SITE
SITE = "https://mangom72.github.io/Direct-mogo/"
def local(u): return u.replace(SITE, LOCAL)
def get(u): return urllib.request.urlopen(local(u), timeout=20)

bad = []
t = (R/"llms.txt").read_text()
lines = t.splitlines()

# ── 규격 (llmstxt.org) ─────────────────────────────────────────
print("1. 규격")
print(f"   H1: {lines[0]}")
if not re.match(r"^# [^#]", lines[0]): bad.append("첫 줄이 H1이 아님")
if sum(1 for l in lines if re.match(r"^# [^#]", l)) != 1: bad.append("H1이 하나가 아님")
i = next(j for j,l in enumerate(lines[1:],1) if l.strip())
if not lines[i].startswith(">"): bad.append("H1 다음이 인용문이 아님")
print(f"   인용문 요약: {'있음' if lines[i].startswith('>') else '없음'}")

sec, cur = {}, None
for l in lines:
    if l.startswith("## "): cur=l[3:].strip(); sec[cur]=[]
    elif cur and l.strip(): sec[cur].append(l)
print(f"   H2 절: {list(sec)}")
for name, body in sec.items():
    for l in body:
        if not re.match(r"^- \[[^\]]+\]\([^)]+\)(: .+)?$", l):
            bad.append(f"'{name}' 절에 파일 목록이 아닌 줄: {l[:40]}")
if "Optional" not in sec: bad.append("Optional 절 없음")
print(f"   크기: {len(t.encode())/1024:.1f}KB (자세한 안내는 따로)")

# ── 링크가 다 살아 있는가 ─────────────────────────────────────
print("\n2. 링크")
links = re.findall(r"- \[([^\]]+)\]\(([^)]+)\)", t)
for name, u in links:
    if u.startswith("mailto:"): print(f"   {name:22} {u}"); continue
    if not u.startswith(SITE): print(f"   {name:22} (바깥) {u[:50]}"); continue
    try:
        r = get(u); print(f"   {name:22} HTTP {r.status}  {r.headers.get('Content-Type','')}")
    except Exception as e:
        bad.append(f"{name} 링크 실패: {e}")

# ── 적힌 대로 따라가면 파일이 나오는가 ───────────────────────
print("\n3. llms.txt만 읽고 시키는 대로 해 보기")
idx = json.load(get(SITE+"data/index.json"))
sid = next(s for g in idx["grades"] if g["code"]=="D300"
           for gr in g["groups"] for s in gr["subjects"] if s["name"]=="생명과학Ⅰ")
sub = json.load(get(SITE + sid["data"]))
p = next(p for p in sub["papers"]
         if p["source"]=="평가원" and p.get("schoolYear")==2026 and p["title"].startswith("수능"))
print(f"   2026학년도 수능 생명과학Ⅰ → {p['date']} 시행")
for k in ("problem","answer","solution"):
    u = p[k]
    if not u: print(f"   {k:9} 없음"); continue
    try:
        import subprocess
        h = subprocess.run(["curl","-sI","-m","20",u],capture_output=True,text=True).stdout
        code = h.splitlines()[0].split()[1] if h else "?"
        ct = next((l.split(': ',1)[1].strip() for l in h.splitlines()
                   if l.lower().startswith("content-type")), "")
        print(f"   {k:9} HTTP {code}  {ct}")
        if code != "200": bad.append(f"{k} 파일이 200이 아님")
    except Exception as e: bad.append(f"{k}: {e}")

# ── 자세한 안내도 살아 있는가 ─────────────────────────────────
full = get(SITE+"llms-full.txt").read().decode()
print(f"\n4. llms-full.txt {len(full.encode())/1024:.1f}KB · llms.txt에서 가리킴: "
      f"{'llms-full.txt' in t}")
if "llms-full.txt" not in t: bad.append("llms.txt가 자세한 안내를 가리키지 않음")

print("\n=== 문제:", bad or "없음")
sys.exit(1 if bad else 0)
