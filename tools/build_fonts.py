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
import hashlib
import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "fonts"

# 홈 화면 위젯은 웹뷰가 아니라 안드로이드가 직접 그린다 — woff2 를 읽지 못하므로
# 같은 글자를 담은 ttf 를 res/font 에 함께 낸다. 위젯만 시스템 글꼴로 뜨면 홈
# 화면에서 다른 앱처럼 보인다. 굵기는 위젯이 쓰는 둘만 낸다.
ANDROID_OUT = ROOT / "android/app/src/main/res/font"
ANDROID_FACES = [("GijulSans-500.woff2", "gijul_500.ttf"),
                 ("GijulSans-700.woff2", "gijul_700.ttf")]

# 제목은 명조(신문 지면), 본문은 고딕. 굵기는 CSS가 쓰는 것만.
#
# 세 번째 칸이 우리가 쓰는 이름이다. IBM Plex 는 OFL에 Reserved Font Name "Plex"가
# 걸려 있고, 3항이 "수정본은 그 이름을 쓸 수 없다"고 못박는다. 글자를 잘라내는 것도
# 수정이므로 이름을 바꿔야 한다 — 원본을 그대로 쓰는 것이 아니라는 표시이기도 하다.
# Song Myung 에는 예약 이름이 없어 그대로 둔다.
FACES = [
    ("Song Myung",       "Song Myung", "400", "SongMyung-400.woff2"),
    ("IBM Plex Sans KR", "Gijul Sans", "400", "GijulSans-400.woff2"),
    ("IBM Plex Sans KR", "Gijul Sans", "500", "GijulSans-500.woff2"),
    ("IBM Plex Sans KR", "Gijul Sans", "600", "GijulSans-600.woff2"),
    ("IBM Plex Sans KR", "Gijul Sans", "700", "GijulSans-700.woff2"),
]

# OFL 2항 — 사본마다 저작권 표시와 라이선스 원문을 함께 실어야 한다
OFL_SOURCES = {
    "songmyung": "https://raw.githubusercontent.com/google/fonts/main/ofl/songmyung/OFL.txt",
    "ibmplexsanskr":
        "https://raw.githubusercontent.com/google/fonts/main/ofl/ibmplexsanskr/OFL.txt",
}

# 자료가 넓어질 수 있는 방향만 미리 넣어 둔다. 지금 화면에 없더라도 EBSi가 다른
# 교육청 시행분을 올리거나 과목이 늘면 바로 필요해지는 글자들이다.
MARGIN = (
    "서울부산대구인천광주대전울산세종경기강원충북충남전북전남경북경남제주"
    "서울시강원도충청북도충청남도전라북도전라남도경상북도경상남도제주도세종시"
    "독일어프랑스어스페인어중국어일본어러시아어아랍어베트남어한문"
    "직업탐구제이외국어상업경제농업기초수산해운공업일반인간발달"
    "예비평가전국연합학력평가대학수학능력시험모의고사교시영역가형나형"
    # 릴리스 노트의 기본 문구. 커밋에 'Notes:' 줄이 없을 때 android.yml 이
    # 이 말을 대신 넣는데, 그 글자가 여기 없으면 발행이 통째로 멈춘다.
    # 실제로 '쳤' 하나가 없어 4.9 배포가 거기서 걸렸다.
    "앱을새로고쳤습니다"
    # 그리고 판올림마다 같은 일이 되풀이됐다 — 노트 문구를 새로 쓸 때마다 처음
    # 보는 글자가 하나씩 걸려 발행이 멈춘다('쳤' 다음은 '꿨'이었다). 한 자씩
    # 쫓아다니는 대신, 노트가 실제로 쓰는 말투를 미리 담아 둔다. 자료에서 오는
    # 글자가 아니라 **우리가 쓰는 문장**에서 오는 글자라 이 자리가 맞다.
    "고쳤바꿨더했없앴줄였늘렸빨라졌옮겼맞췄되살렸눌렀열렸보였"
    # 다른 앱 위에 띄우는 창이 쓰는 말
    "띄워두기반투명통과조작겹쳐손잡이투명도자판떠셋움직입니다접었펼뜰떨섭알약뜨물러납맞춘바뀌어스크롤막대부드러워졌가벼메뉴단추눌러도눈힐오므라듭흔들리던튀럽시작던끄멈춥덜홈벌놓"
    # 그 창 안에서 문서를 고르는 목록
    "목록에서골라넘어갈넘어갑니다찾기회차전체"
)

# 라틴·숫자·이 화면이 쓰는 기호
EXTRA = set(chr(c) for c in range(0x20, 0x7F)) | set("·—…★◐●○→←ⅠⅡ×⋯″′")


def hangul(text):
    return {c for c in text if "가" <= c <= "힣"}


# 주석은 화면에 나오지 않는다. 그런데 이 저장소는 주석이 길고 한글이라, 재 보니
# 담고 있던 799자 중 309자가 오직 주석에서만 오는 글자였다 — 39%가 헛짐이다.
# 글꼴은 이 사이트가 내려보내는 바이트의 4분의 3을 차지하므로 그냥 둘 수 없다.
#
# 여는 태그 안의 글(예: alt="…")은 주석이 아니므로 그대로 남는다. 문자열 안에
# '/*'가 들어가면 잘못 잘릴 수 있는데, base64에는 '*'가 없고 이 저장소의 문자열에도
# 없다 — 그래도 확실히 하려고 test_glyphs 가 실제로 그려진 글자를 훑어 확인한다.
COMMENT = re.compile(r"<!--.*?-->|/\*.*?\*/", re.S)
# 자바 문자열 리터럴. 줄바꿈은 들어갈 수 없고, \" 로 이스케이프된 따옴표는 넘긴다.
JAVA_STRING = re.compile(r'"(?:\\.|[^"\\\n])*"')


def visible(text):
    """주석을 걷어낸 글. 여기서 지나치게 걷으면 그 글자가 화면에서 네모가 된다."""
    return COMMENT.sub(" ", text)


def java_visible(text):
    """자바에서 **화면에 뜨는 글**만 골라낸다 — 곧 문자열 리터럴이다.

    주석만 걷어내는 것으로는 모자랐다. COMMENT 가 /* */ 만 걷고 // 줄 주석은
    그대로 두어서, 화면에 나올 일이 없는 주석 글자가 글꼴에 실렸다. 실제로
    `// 상한에 붙은 채로 계속 끌 때가 대부분이다` 한 줄 때문에 '속' 하나가
    새로 필요해져 발행이 멈췄다.

    // 를 마저 걷는 방법도 있지만 그건 위험하다 — 문자열 안의 `https://` 를
    주석으로 잘못 보고 그 뒤를 통째로 버리면, 같은 줄에 있던 한글이 조용히
    사라져 화면에서 네모가 된다. 반대로 **문자열만 줍는 것**은 놓칠 것이 없다:
    자바가 화면에 글을 내보내는 통로가 리터럴뿐이고, 리소스에 있는 글은
    strings.xml 쪽에서 따로 걷힌다.

    주석을 먼저 걷고 나서 줍는다. 주석 안에 예시로 적어 둔 따옴표까지 담을
    이유는 없다.
    """
    return " ".join(JAVA_STRING.findall(COMMENT.sub(" ", text)))


def wanted():
    """저장소에서 글자를 모은다. 여기 빠진 출처가 있으면 그게 곧 두부가 된다."""
    chars = set()

    index = (ROOT / "index.html").read_text(encoding="utf-8")
    chars |= hangul(visible(index))             # 정적 문구 · 과목명 · 학년명
    m = re.search(r'id="payload"[^>]*>([A-Za-z0-9+/=\s]+)<', index)
    if m:                                       # 회차 제목 — 매달 늘어나는 쪽
        db = json.loads(gzip.decompress(base64.b64decode(re.sub(r"\s", "", m.group(1)))))
        chars |= hangul("".join(row[0] for g in db.values() for s in g.values()
                                for y in s.values() for row in y))

    # 앱이 띄우는 문구도 이 글꼴로 그려진다 — 웹뷰 안이라 같은 페이지다
    src = ROOT / "android/app/src/main"
    for f in src.rglob("*.java"):
        chars |= hangul(java_visible(f.read_text(encoding="utf-8")))
    for f in src.rglob("*.xml"):
        chars |= hangul(visible(f.read_text(encoding="utf-8")))

    # 과목 페이지(s/)도 같은 글꼴을 쓴다. 만들어진 HTML을 그대로 읽는다 — 틀에 적힌
    # 글과 자료에서 온 글이 섞여 있어, 만드는 쪽 소스만 봐서는 놓치는 것이 생긴다.
    # 그래서 워크플로에서 build_pages.py 를 먼저 돌리고 이 스크립트를 나중에 돌린다.
    pages = list((ROOT / "s").rglob("*.html")) or [ROOT / "tools/build_pages.py"]
    for f in pages:
        chars |= hangul(visible(f.read_text(encoding="utf-8")))

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
    for source, family, weight, name in FACES:
        ttf = tmp / f"{source.replace(' ', '')}-{weight}.ttf"
        if not ttf.is_file():
            source_ttf(source, weight, ttf)
        subprocess.run(
            ["pyftsubset", str(ttf), f"--text-file={chars_file}", "--flavor=woff2",
             "--layout-features=*", f"--output-file={OUT / name}"], check=True)
        finalize(OUT / name, family, weight, family != source)
        kb = (OUT / name).stat().st_size / 1024
        total += kb
        print(f"  {family} {weight:<4} {kb:7.1f}KB  {name}"
              + (f"  ← {source}" if family != source else ""))

    for slug, url in OFL_SOURCES.items():
        subprocess.run(["curl", "-fsS", "-m", "60", url,
                        "-o", str(OUT / f"OFL-{slug}.txt")], check=True)
    (OUT / "fonts.css").write_text(css_text(), encoding="utf-8")
    write_version()
    android_fonts()
    print(f"  {'합계':<22}{total:7.1f}KB · 글자 {len(chars)}자")


def android_fonts():
    """방금 만든 woff2 를 위젯이 읽을 수 있는 ttf 로 함께 낸다.

    같은 글자, 같은 이름표다 — 압축만 벗긴다. 원본을 따로 자르지 않는 것은 두
    벌이 서로 어긋날 자리를 만들지 않기 위해서다. 웹에 없는 글자는 위젯에도
    없어야 맞다.

    날짜 도장은 여기서도 지운다. 그러지 않으면 글자가 그대로여도 파일 바이트가
    달라져 매일 도는 갱신이 날마다 ttf 두 개를 새로 커밋한다.
    """
    from fontTools.ttLib import TTFont

    ANDROID_OUT.mkdir(parents=True, exist_ok=True)
    for src, name in ANDROID_FACES:
        font = TTFont(OUT / src)
        font.recalcTimestamp = False
        font["head"].modified = font["head"].created
        font.flavor = None
        font.save(ANDROID_OUT / name)
        kb = (ANDROID_OUT / name).stat().st_size / 1024
        print(f"  {'위젯 ' + name:<22}{kb:7.1f}KB")


def finalize(path, family, weight, rename):
    """만들어진 글꼴을 마무리한다 — 이름표를 갈고, 날짜 도장을 지운다.

    이름을 바꾸는 이유: CSS에서만 다른 이름을 쓰고 파일 속은 그대로 두면 이름을
    바꿨다고 할 수 없다. OFL이 막는 것은 '사용자에게 보이는 주된 이름'이다.

    날짜를 박아 두는 이유: 글꼴의 head 표에는 '고친 시각'이 들어가는데 저장할
    때마다 지금 시각으로 갱신된다. 그러면 글자가 하나도 안 바뀌어도 파일
    바이트가 달라져, 매일 도는 갱신이 날마다 글꼴 다섯 개를 새로 커밋한다.
    만든 시각(created)으로 맞춰 두면 같은 글자에서 같은 파일이 나온다.
    값을 넣는 것만으로는 부족하다 — save() 가 저장 직전에 다시 계산하므로
    recalcTimestamp 를 꺼야 넣은 값이 남는다.
    """
    from fontTools.ttLib import TTFont

    style = "Regular" if weight == "400" else weight
    full = f"{family} {style}"
    ps = f"{family.replace(' ', '')}-{style}"
    font = TTFont(path)
    font.recalcTimestamp = False        # 이게 없으면 save()가 modified 를 '지금'으로 되돌린다
    if rename:
        for rec in font["name"].names:
            if rec.nameID in (1, 16):       # 가족 이름
                rec.string = family
            elif rec.nameID == 4:           # 전체 이름
                rec.string = full
            elif rec.nameID == 6:           # PostScript 이름
                rec.string = ps
    font["head"].modified = font["head"].created
    font.flavor = "woff2"
    font.save(path)


def css_text():
    """@font-face 만. 어느 글꼴을 어디에 쓸지는 index.html이 정한다.

    optional 인 이유: swap 은 늦게 도착한 글꼴로 글자를 갈아끼우는데, 그때 줄바꿈이
    다시 잡히면서 아래 내용이 통째로 밀린다. 과목 색인에서 재 보니 폭 412px에서
    41px가 밀려 CLS 0.25가 나왔다 — 나쁨 구간이다. 대체 글꼴의 폭을 맞춰 두는
    길(size-adjust)도 있지만 그 값이 기기마다 달라 한 숫자로는 못 맞춘다.

    optional 은 글꼴이 제때 준비되지 않으면 그 방문에는 아예 갈아끼우지 않는다.
    갈아끼우지 않으니 밀릴 것도 없다. 대신 느린 회선의 첫 방문은 시스템 글꼴로
    보인다 — 두 번째부터는 캐시에서 즉시 나오므로 제 글꼴이 쓰인다.
    """
    out = ["/* tools/build_fonts.py 가 만든다. 손으로 고치지 말 것.",
           "   글꼴 라이선스는 같은 폴더의 OFL-*.txt 를 보라. */"]
    for _, family, weight, name in FACES:
        out.append(
            f"@font-face{{font-family:'{family}';font-style:normal;font-weight:{weight};"
            f"font-display:optional;src:url('{name}') format('woff2')}}")
    return "\n".join(out) + "\n"


def write_version():
    """같은 이름으로 교체되는 웹 글꼴 묶음의 내용 지문.

    서비스 워커는 index.html과 무관하게 이 작은 파일만 조건부 확인한다. 글꼴
    파일을 모두 쓴 뒤 지문을 만들고, 서비스 워커도 실제 글꼴을 모두 받은 뒤에만
    이 파일을 캐시에 넣으므로 반쪽짜리 묶음을 새 판으로 오인하지 않는다.
    """
    digest = hashlib.sha256()
    for path in [OUT / "fonts.css", *(OUT / face[3] for face in FACES)]:
        digest.update(path.name.encode("utf-8") + b"\0")
        digest.update(path.read_bytes())
    (OUT / "version.json").write_text(
        json.dumps({"sha256": digest.hexdigest()}, separators=(",", ":")) + "\n",
        encoding="utf-8")


def check(chars):
    """망 없이, 지금 글꼴이 지금 내용을 덮는지 본다."""
    from fontTools.ttLib import TTFont

    bad = False
    for _, family, weight, name in FACES:
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
