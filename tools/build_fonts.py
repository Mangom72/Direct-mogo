#!/usr/bin/env python3
"""화면에 실제로 나오는 글자만 담은 웹폰트를 만든다.

한글 글꼴은 통짜가 1~2.7MB라 그대로 실을 수 없다. 구글에 맡기면 조각으로 쪼개
필요한 것만 주지만, 이 사이트 기준으로 재보니 118개 요청에 1,699KB가 오갔다.
글자를 직접 골라 자르면 5개 요청에 420KB 남짓이다.

그렇게 자르면 새 글자가 나올 때 두부(□)가 된다는 것이 유일한 문제다. 그래서
목록을 손으로 적지 않고 **저장소 내용에서 뽑는다** — 회차 제목이 늘면 그 글자가
저절로 들어온다. 월간 자료 갱신 워크플로가 이 스크립트를 같이 돌리므로, 사람이
기억해서 해야 하는 단계가 없다.

    python3 tools/build_fonts.py            # 다시 만든다 (망 필요)
    python3 tools/build_fonts.py --check    # 지금 글꼴이 지금 내용을 덮는지만 (망 불필요)

--check 는 발행 직전에 쓴다. 릴리스 노트는 커밋 메시지가 그대로 들어가는 자리라
여기만 글자가 미리 정해지지 않는데, 그 상태로 나가면 알림 막대가 깨진다.
"""
import argparse
import base64
import gzip
import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "fonts"

# 제목은 명조(신문 지면), 본문은 고딕. 굵기는 CSS가 쓰는 것만.
FACES = [
    ("Song Myung", "400", "SongMyung-400.woff2", "serif"),
    ("IBM Plex Sans KR", "400", "PlexSansKR-400.woff2", "sans-serif"),
    ("IBM Plex Sans KR", "500", "PlexSansKR-500.woff2", "sans-serif"),
    ("IBM Plex Sans KR", "600", "PlexSansKR-600.woff2", "sans-serif"),
    ("IBM Plex Sans KR", "700", "PlexSansKR-700.woff2", "sans-serif"),
]

# 자료가 넓어질 수 있는 방향만 미리 넣어 둔다. 지금 화면에 없더라도 EBSi가 다른
# 교육청 시행분을 올리거나 과목이 늘면 바로 필요해지는 글자들이다.
MARGIN = (
    "서울부산대구인천광주대전울산세종경기강원충북충남전북전남경북경남제주"
    "서울시강원도충청북도충청남도전라북도전라남도경상북도경상남도제주도세종시"
    "독일어프랑스어스페인어중국어일본어러시아어아랍어베트남어한문"
    "직업탐구제이외국어상업경제농업기초수산해운공업일반인간발달"
    "예비평가전국연합학력평가대학수학능력시험모의고사교시영역가형나형"
)

# 라틴·숫자·이 화면이 쓰는 기호
EXTRA = set(chr(c) for c in range(0x20, 0x7F)) | set("·—…★◐●○→←ⅠⅡ×⋯″′")


def hangul(text):
    return {c for c in text if "가" <= c <= "힣"}


def wanted():
    """저장소에서 글자를 모은다. 여기 빠진 출처가 있으면 그게 곧 두부가 된다."""
    chars = set()

    index = (ROOT / "index.html").read_text(encoding="utf-8")
    chars |= hangul(index)                      # 정적 문구 · 과목명 · 학년명
    m = re.search(r'id="payload"[^>]*>([A-Za-z0-9+/=\s]+)<', index)
    if m:                                       # 회차 제목 — 매달 늘어나는 쪽
        db = json.loads(gzip.decompress(base64.b64decode(re.sub(r"\s", "", m.group(1)))))
        chars |= hangul("".join(row[0] for g in db.values() for s in g.values()
                                for y in s.values() for row in y))

    # 앱이 띄우는 문구도 이 글꼴로 그려진다 — 웹뷰 안이라 같은 페이지다
    src = ROOT / "android/app/src/main"
    for f in list(src.rglob("*.java")) + list(src.rglob("*.xml")):
        chars |= hangul(f.read_text(encoding="utf-8"))

    # 릴리스 노트 — 커밋 메시지가 그대로 들어와 알림 막대에 뜬다
    latest = ROOT / "app/latest.json"
    if latest.is_file():
        chars |= hangul(json.loads(latest.read_text(encoding="utf-8")).get("notes", ""))

    return chars | hangul(MARGIN) | EXTRA


def source_ttf(family, weight, into):
    """원본 글꼴을 받아 온다.

    저장소에 두지 않는 이유는 다섯 벌이 13MB라서다. 결과물(woff2)만 싣는다.
    구글 폰트는 요청한 UA가 감당하는 형식으로 돌려주는데, 옛 안드로이드로 물으면
    쪼개지 않은 통짜 TTF를 준다 — 조각 88개를 도로 붙이는 것보다 이 편이 낫다.
    """
    css = subprocess.run(
        ["curl", "-fsS", "-m", "60", "-A", "Mozilla/5.0 (Linux; U; Android 2.2; en-us)",
         f"https://fonts.googleapis.com/css2"
         f"?family={family.replace(' ', '+')}:wght@{weight}&display=swap"],
        capture_output=True, text=True, check=True).stdout
    url = re.search(r"url\((https://fonts\.gstatic\.com/[^)]+)\)", css)
    if not url:
        raise SystemExit(f"{family} {weight}: 통짜 글꼴 주소를 찾지 못했습니다")
    subprocess.run(["curl", "-fsS", "-m", "120", url.group(1), "-o", str(into)], check=True)


def build(chars):
    OUT.mkdir(exist_ok=True)
    tmp = OUT / ".src"
    tmp.mkdir(exist_ok=True)
    chars_file = tmp / "chars.txt"
    chars_file.write_text("".join(sorted(chars)), encoding="utf-8")

    total = 0
    for family, weight, name, _ in FACES:
        ttf = tmp / f"{family.replace(' ', '')}-{weight}.ttf"
        if not ttf.is_file():
            source_ttf(family, weight, ttf)
        subprocess.run(
            ["pyftsubset", str(ttf), f"--text-file={chars_file}", "--flavor=woff2",
             "--layout-features=*", f"--output-file={OUT / name}"], check=True)
        kb = (OUT / name).stat().st_size / 1024
        total += kb
        print(f"  {family} {weight:<4} {kb:7.1f}KB  {name}")

    (OUT / "fonts.css").write_text(css_text(), encoding="utf-8")
    print(f"  {'합계':<22}{total:7.1f}KB · 글자 {len(chars)}자")


def css_text():
    """@font-face 만. 어느 글꼴을 어디에 쓸지는 index.html이 정한다."""
    out = ["/* tools/build_fonts.py 가 만든다. 손으로 고치지 말 것. */"]
    for family, weight, name, fallback in FACES:
        out.append(
            f"@font-face{{font-family:'{family}';font-style:normal;font-weight:{weight};"
            f"font-display:swap;src:url('{name}') format('woff2')}}")
    return "\n".join(out) + "\n"


def check(chars):
    """망 없이, 지금 글꼴이 지금 내용을 덮는지 본다."""
    from fontTools.ttLib import TTFont

    bad = False
    for family, weight, name, _ in FACES:
        path = OUT / name
        if not path.is_file():
            print(f"★ {name} 이 없습니다 — build_fonts.py 를 먼저 돌리세요")
            bad = True
            continue
        have = set()
        for table in TTFont(path).getBestCmap():
            have.add(chr(table))
        miss = {c for c in chars if c not in have and "가" <= c <= "힣"}
        if miss:
            bad = True
            print(f"★ {family} {weight}: {len(miss)}자 빠짐 — {''.join(sorted(miss))[:40]}")
        else:
            print(f"  {family} {weight:<4} 덮음 ({len(have)}자 수록)")
    if bad:
        print("\n글꼴에 없는 글자가 화면에 뜨면 네모(□)로 보입니다.")
        print("python3 tools/build_fonts.py 로 다시 만드세요.")
    return 0 if not bad else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="다시 만들지 않고 확인만")
    a = ap.parse_args()
    chars = wanted()
    if a.check:
        return check(chars)
    build(chars)
    return 0


if __name__ == "__main__":
    sys.exit(main())
