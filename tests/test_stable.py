"""같은 자료면 같은 파일이 나오는가 — 매일 도는 갱신이 헛커밋을 내지 않으려면 필요하다."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from harness import CHROME, ROOT, SHOT, site, Serve
_srv, SITE = site()
import sys, hashlib, subprocess, pathlib, json
sys.path.insert(0, str(ROOT / "tools"))
R = ROOT
def sha(p): return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()[:16]
bad = []

print("1. 페이로드 눌러 담기")
import refresh_data as RD
raw = json.dumps({"D300": {"158": {"2026": [["수능", "20251113", "a", "b", "c"]]}}},
                 ensure_ascii=False, separators=(",", ":")).encode()
import time
a = RD.squeeze(raw); time.sleep(1.1); b = RD.squeeze(raw)
print(f"   1초 간격 두 번 → 같음: {a == b}")
if a != b: bad.append("페이로드 바이트가 매번 달라집니다")

print("\n2. 글꼴 다시 만들기 (원본은 fonts/.src 재사용, 망 불필요)")
before = {f.name: sha(f) for f in sorted((R/"fonts").glob("*.woff2"))}
subprocess.run(["python3", "tools/build_fonts.py"], cwd=R, capture_output=True)
mid = {f.name: sha(f) for f in sorted((R/"fonts").glob("*.woff2"))}
subprocess.run(["python3", "tools/build_fonts.py"], cwd=R, capture_output=True)
after = {f.name: sha(f) for f in sorted((R/"fonts").glob("*.woff2"))}
for n in mid:
    same = mid[n] == after[n]
    print(f"   {n:22} 두 번 만들어 같음: {same}")
    if not same: bad.append(f"{n} 이 만들 때마다 달라집니다")

print("\n3. 정적 산출물")
for cmd in (["python3","tools/build_api.py"], ["python3","tools/build_pages.py"]):
    subprocess.run(cmd, cwd=R, capture_output=True)
h1 = {str(f): sha(f) for f in sorted(R.glob("data/**/*.json"))} | \
     {str(f): sha(f) for f in sorted(R.glob("s/**/*"))if f.is_file()} | \
     {"llms": sha(R/"llms.txt"), "full": sha(R/"llms-full.txt"), "sm": sha(R/"sitemap.xml")}
for cmd in (["python3","tools/build_api.py"], ["python3","tools/build_pages.py"]):
    subprocess.run(cmd, cwd=R, capture_output=True)
h2 = {str(f): sha(f) for f in sorted(R.glob("data/**/*.json"))} | \
     {str(f): sha(f) for f in sorted(R.glob("s/**/*")) if f.is_file()} | \
     {"llms": sha(R/"llms.txt"), "full": sha(R/"llms-full.txt"), "sm": sha(R/"sitemap.xml")}
diff = [k for k in h1 if h1[k] != h2[k]]
print(f"   파일 {len(h1)}개 두 번 만들어 달라진 것: {len(diff)}")
if diff: bad.append(f"정적 산출물이 달라집니다: {diff[:3]}")

print("\n=== 문제:", bad or "없음")
sys.exit(1 if bad else 0)
