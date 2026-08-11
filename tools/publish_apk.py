#!/usr/bin/env python3
"""빌드된 릴리스 APK를 사이트에 올린다.

앱은 스토어를 거치지 않으므로 새 버전을 알려줄 주체가 없다. 그래서 APK와 그
명세(app/latest.json)를 Pages에 같이 올려두고, 앱이 그 명세를 직접 읽는다.

APK 자체를 저장소에 두는 것은 취향이 갈리는 선택이다. GitHub 릴리스에 붙이면
저장소가 커지지 않지만 토큰과 태그 규율이 필요하다. 여기서는 "정적 파일만
Pages에 올린다"는 이 저장소의 방식을 그대로 따랐다 — 받는 쪽에 인증이 필요
없고, 사이트가 살아 있으면 업데이트도 살아 있다. 파일 이름은 늘 같으므로
작업 트리에는 APK가 한 개만 남는다(기록에는 판본마다 쌓인다).

    python3 tools/publish_apk.py                 # 빌드된 APK를 app/ 으로
    python3 tools/publish_apk.py --notes "..."   # 알림 막대에 함께 띄울 한 줄
"""

import argparse
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
APK_SRC = ROOT / "android/app/build/outputs/apk/release/app-release.apk"
APP_DIR = ROOT / "app"
MANIFEST = APP_DIR / "latest.json"

# 내려받는 자리는 릴리스 자산이다. 저장소에 APK를 커밋해 두면 판본마다 1.8MB가
# 히스토리에 영구히 남고 받는 사람 전부가 그 비용을 낸다.
#
# 판본을 **못박아** 적는다. latest.json 자체가 한 판본을 가리키는 문서인데 주소만
# 'latest'로 두면, 다음 판이 올라간 순간 이 문서가 말하는 크기·sha256과 실제로
# 내려오는 파일이 어긋난다. 앱은 그 둘을 대조하므로 그대로 설치를 거부한다.
RELEASE = "https://github.com/Mangom72/Direct-mogo/releases/download/v{name}/gijul-direct.apk"


def sdk_tool(name):
    """build-tools는 판본별 폴더에 들어 있고 PATH에 없다. 가장 최신 것을 쓴다."""
    for home in (os.environ.get("ANDROID_HOME"), os.environ.get("ANDROID_SDK_ROOT"),
                 "/opt/android-sdk", "/usr/local/lib/android/sdk"):
        if not home:
            continue
        found = sorted(pathlib.Path(home).glob(f"build-tools/*/{name}"))
        if found:
            return str(found[-1])
    return shutil.which(name)


def badging(apk):
    """versionCode·versionName은 gradle 파일이 아니라 APK 자체에서 읽는다 —
    두 값이 어긋나면 기기에서만 드러나는 종류의 사고가 난다."""
    exe = sdk_tool("aapt2")
    if not exe:
        sys.exit("aapt2를 찾지 못했습니다 — Android SDK build-tools가 필요합니다")
    out = subprocess.run([exe, "dump", "badging", str(apk)],
                         capture_output=True, text=True, check=True).stdout
    m = re.search(r"versionCode='(\d+)' versionName='([^']+)'", out)
    if not m:
        sys.exit("APK에서 버전을 읽지 못했습니다")
    return int(m.group(1)), m.group(2)


def signer(apk):
    """서명 지문. 앱은 설치 전에 이 인증서가 자기 것과 같은지 확인하므로,
    키가 바뀌면 사용자 기기에서 업데이트가 조용히 거부된다. 여기서 먼저 보여준다."""
    exe = sdk_tool("apksigner")
    if not exe:
        return None
    out = subprocess.run([exe, "verify", "--print-certs", str(apk)],
                         capture_output=True, text=True).stdout
    m = re.search(r"certificate SHA-256 digest: (\w+)", out)
    return m.group(1) if m else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--notes", default="", help="알림 막대에 함께 띄울 한 줄")
    ap.add_argument("--apk", default=str(APK_SRC))
    args = ap.parse_args()

    apk = pathlib.Path(args.apk)
    if not apk.is_file():
        sys.exit(f"APK가 없습니다: {apk}\n먼저 android/에서 gradle assembleRelease")

    code, name = badging(apk)

    old = {}
    if MANIFEST.is_file():
        old = json.loads(MANIFEST.read_text(encoding="utf-8"))
    # 종료 코드 3은 '올릴 것이 없다'는 뜻으로만 쓴다. 부르는 쪽(워크플로)이
    # 이것만 조용히 넘기고 나머지 실패는 빨갛게 띄운다 — 전에는 어떤 이유로
    # 멈추든 '새 판본 없음'으로 뭉뚱그려, 진짜 고장이 초록불로 지나갔다.
    if code <= old.get("versionCode", 0):
        print(f"versionCode가 늘지 않았습니다 ({old.get('versionCode')} → {code}). "
              "build.gradle을 먼저 올리세요.", file=sys.stderr)
        raise SystemExit(3)

    # APK 자체는 저장소에 두지 않는다 — 판본마다 1.8MB가 히스토리에 영구히 쌓인다.
    # 여기서는 명세만 쓰고, 파일은 부르는 쪽(워크플로)이 릴리스 자산으로 올린다.
    APP_DIR.mkdir(exist_ok=True)
    data = apk.read_bytes()

    MANIFEST.write_text(json.dumps({
        "versionCode": code,
        "versionName": name,
        "url": RELEASE.format(name=name),
        "size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "notes": args.notes,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"{name} (versionCode {code}) · {len(data)/1048576:.2f}MB")
    print(f"  {MANIFEST.relative_to(ROOT)}")
    print(f"  자산으로 올릴 파일: {apk}")
    fp = signer(apk)
    if fp:
        print(f"  서명 SHA-256 {fp}")
        print("  ※ 이 지문이 이전 판본과 다르면 사용자 기기가 업데이트를 거부합니다")

    # 노트는 커밋 메시지가 그대로 들어오는 자리라, 글자가 미리 정해지지 않은 유일한
    # 통로다. 글꼴에 없는 글자가 섞이면 알림 막대가 네모(□)로 뜬다.
    check = subprocess.run([sys.executable, str(ROOT / "tools" / "build_fonts.py"), "--check"],
                           capture_output=True, text=True)
    if check.returncode != 0:
        print()
        print(check.stdout.strip())
        raise SystemExit("발행을 멈춥니다 — 알림 막대에 네모가 뜹니다")


if __name__ == "__main__":
    main()
