"""같은 자료면 같은 파일이 나오는가 — 자동 생성물이 소스와 어긋나지 않는가."""
import hashlib
import json
import pathlib
import subprocess
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from harness import ROOT      # 이 시험은 브라우저도 서버도 쓰지 않는다

sys.path.insert(0, str(ROOT / "tools"))
import refresh_data as RD

R = ROOT
bad = []


def sha(path):
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()


def run(*args):
    """생성기가 실패했는데 옛 파일끼리 비교해 통과하는 일을 막는다."""
    subprocess.run([sys.executable, *args], cwd=R, check=True)


def outputs():
    files = (sorted((R / "fonts").glob("*.woff2"))
             + [R / "fonts/fonts.css", R / "fonts/version.json"]
             + sorted((R / "android/app/src/main/res/font").glob("gijul_*.ttf"))
             + sorted(R.glob("data/**/*.json"))
             + sorted(f for f in R.glob("s/**/*") if f.is_file())
             + [R / "llms.txt", R / "llms-full.txt", R / "sitemap.xml"])
    return {str(f.relative_to(R)): sha(f) for f in files}


print("1. 페이로드 눌러 담기")
raw = json.dumps({"D300": {"158": {"2026": [["수능", "20251113", "a", "b", "c"]]}}},
                 ensure_ascii=False, separators=(",", ":")).encode()
a = RD.squeeze(raw)
time.sleep(1.1)
b = RD.squeeze(raw)
print(f"   1초 간격 두 번 → 같음: {a == b}")
if a != b:
    bad.append("페이로드 바이트가 매번 달라집니다")

print("\n2. 생성 결과가 커밋과 같은가")
before = outputs()
run("tools/build_api.py")
run("tools/build_pages.py")
run("tools/build_fonts.py")
mid = outputs()
drift = sorted(k for k in set(before) | set(mid) if before.get(k) != mid.get(k))
print(f"   생성물 {len(mid)}개 · 어긋난 것 {len(drift)}개")
if drift:
    bad.append(f"생성물이 소스와 어긋납니다: {drift[:3]}")

print("\n3. 같은 자료를 두 번 만들면 같은가")
run("tools/build_api.py")
run("tools/build_pages.py")
run("tools/build_fonts.py")
after = outputs()
diff = sorted(k for k in set(mid) | set(after) if mid.get(k) != after.get(k))
print(f"   파일 {len(mid)}개 두 번 만들어 달라진 것: {len(diff)}")
if diff:
    bad.append(f"정적 산출물이 달라집니다: {diff[:3]}")

print("\n=== 문제:", bad or "없음")
raise SystemExit(1 if bad else 0)
