#!/usr/bin/env python3
"""EBSi 기출문제 목록을 긁어 index.html의 페이로드를 갱신한다.

자료가 index.html 안에 구워져 있어 새 회차가 나와도 자동으로 반영되지 않는다.
이 스크립트가 그 간극을 메운다. 매일 23시(KST) GitHub Actions에서 돌린다.

갱신은 덧붙이기만 한다 — 기존 기록의 **있는 값**은 고치지도 지우지도 않는다.
새 시행일을 담고, 이미 있는 회차는 비어 있는 칸만 뒤늦게 채운다(top_up 참고).
EBSi가 한 회차를 며칠에 걸쳐 올리기 때문에 필요한 일이다.
안전장치: 수집량이 기존 페이로드의 80%에 못 미치면 아무것도 쓰지 않고 실패한다.
EBSi가 마크업을 바꾸면 파서가 조용히 빈손이 되어 "변경 없음"으로 넘어갈 수 있기 때문이다.

사용법:
    python3 tools/refresh_data.py [--index index.html] [--dry-run]
"""
import argparse
import base64
import gzip
import io
import json
import re
import sys
import time
from html import unescape
from pathlib import Path

import requests

BASE = "https://www.ebsi.co.kr"
LIST = BASE + "/ebs/xip/xipc/previousPaperList.ebs"
AJAX = BASE + "/ebs/xip/xipc/previousPaperListAjax.ajax"
GRADES = ["D300", "D200", "D100"]
DIRS = ["go3", "go2", "go1", "mobile"]
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

PAYLOAD_RE = re.compile(
    r'(<script id="payload" type="application/octet-stream">)([^<]+)(</script>)')


def form_defaults(html):
    """폼의 히든/체크 값을 그대로 읽어온다.

    year·monthAll·영역별 *ArOrd 가운데 하나라도 빠지면 서버가 0건을 돌려준다.
    값을 하드코딩하면 EBSi가 영역 번호를 바꾸는 날 조용히 빈손이 되므로 매번 파싱한다.
    """
    i = html.find('name="paperListFrm"')
    seg = html[i:html.find("</form>", i)]
    data, years, months = {}, [], []
    for tag in re.finditer(r"<input[^>]*>", seg):
        t = tag.group(0)
        name = re.search(r'name="([^"]+)"', t)
        if not name:
            continue
        name = name.group(1)
        value = (re.search(r'value="([^"]*)"', t) or [None, ""])[1]
        typ = (re.search(r'type="([^"]+)"', t) or [None, "text"])[1]
        if name == "year":
            years.append(value)
        elif name == "month":
            months.append(value)
        if typ == "checkbox" and "checked" not in t:
            continue
        data[name] = value
    if not years or not months:
        raise SystemExit("폼에서 연도·월 목록을 찾지 못했습니다 — 페이지 구조가 바뀐 듯합니다")
    return data, years, months


ROW_RE = re.compile(r'<div class="qus_box.*?(?=<div class="qus_box|\Z)', re.S)
TITLE_RE = re.compile(r'<div class="qus_tit">(.*?)</div>', re.S)
FLAG_RE = re.compile(r'<span class="flag_subject_col[^"]*">([^<]*)</span>')
# goDownLoadP('/20260708/go3/korB_mun_XX.pdf', …, '301', '2', '140118', …)
CALL_RE = re.compile(r"goDownLoad([PJH])\s*\((.*?)\)\s*;", re.S)
ARG_RE = re.compile(r"'([^']*)'")


def encode(path):
    """'/20260708/go3/a.pdf' -> '0a.pdf'  (날짜·디렉터리를 페이지가 쓰는 코드로 압축)"""
    if not path:
        return ""
    p = path.split("wdown.ebsi.co.kr/W61001/01exam")[-1]
    m = re.match(r"^/(\d{8})/([a-z0-9]+)/(.+)$", p)
    if m and m.group(2) in DIRS:
        return str(DIRS.index(m.group(2))) + m.group(3)
    return "!" + p          # 옛 자료는 날짜/디렉터리 규칙을 따르지 않는다


def parse_rows(html):
    """(과목ID, 연도, 제목, 날짜, 문제, 정답, 해설) 튜플을 뽑는다.

    주의: 파일 이름은 과목을 나타내지 않는다. 2015년 수능이 대표적으로,
    한국사 문제지가 s_hanji(한국지리), 한국지리가 s_saeji(세계지리) 이름을 달고 있다.
    PDF를 열어 확인한 결과 내용은 EBSi가 붙인 행과 일치했다 — 이름만 어긋난 것이다.
    그러니 이름이 과목과 다르다고 자료를 고치거나 버리면 안 된다.
    """
    out = []
    for block in ROW_RE.findall(html):
        title = TITLE_RE.search(block)
        if not title:
            continue
        # '고3 7월 학평(인천)&nbsp;언어와 매체&nbsp;' → 회차명만 남긴다.
        # 구분자가 &nbsp;이므로 공백으로 바꾸기 전에 쪼개야 한다.
        # 순서가 중요하다. 태그를 먼저 지우고 엔티티를 되돌리면 &lt;img&gt; 같은 값이
        # 되돌려지면서 진짜 태그가 되어 그대로 페이로드에 들어간다.
        raw = re.sub(r"<[^>]+>", "", unescape(title.group(1)))
        head, _, tail = raw.partition("\xa0")
        # '2013 고3 7월 학평(인천)'처럼 연도·학년이 앞에 붙어 오기도 한다
        label = re.sub(r"^\s*(\d{4}\s+)?고[123]\s+", "", head).strip()
        # kindOf()가 제목으로 출제 기관을 가른다. '2014학년도 대학수학능력시험'은
        # "수능"으로 시작하지도 "평가원"을 품지도 않아 그대로 두면 수능이 교육청이 된다.
        label = re.sub(r"^\d{4}학년도\s*대학수학능력시험[_\s]*", "수능 ", label).strip()
        # 국어A형·영어 짝수형처럼 형이 과목명 쪽에 붙어 오는데, 회차를 가르는 정보라
        # 제목으로 옮겨야 같은 날 같은 과목의 두 회차가 구별된다.
        form = re.search(r"([A-Z]형|[홀짝]수형)\s*$", tail.replace("\xa0", " ").strip())
        if form:
            label = f"{label} {form.group(1)}"
        flags = [unescape(f).strip() for f in FLAG_RE.findall(block)]
        year = next((f for f in flags if re.fullmatch(r"\d{4}", f)), None)
        if not year:
            continue
        files, subj, date = {}, None, None
        for kind, args in CALL_RE.findall(block):
            a = ARG_RE.findall(args)
            if not a:
                continue
            code = encode(a[0])
            # 옛 자료는 날짜 뒤에 일련번호가 붙어 9자리다(/201211142/). 8자리만 받으면
            # 그 회차 전체가 조용히 버려진다.
            d = re.search(r"/(\d{8,9})/", a[0])
            if d:
                date = d.group(1)
            # (경로, fullserv, irecord, 영역코드, arCnt, 과목ID, …) — 과목ID는 6번째다.
            # 영역코드(301·302…)도 숫자라 훑어서 고르면 수학 과목이 전부 302로 뭉개진다.
            if len(a) > 5 and re.fullmatch(r"\d{2,7}", a[5]):
                subj = subj or a[5]
            files[kind] = code
        if not (subj and date and label):
            continue
        out.append((subj, year, label, date,
                    files.get("P", ""), files.get("J", ""), files.get("H", "")))
    return out


def scrape(session, grade, pause):
    page = session.get(LIST, params={"targetCd": grade}, timeout=30)
    page.raise_for_status()
    base, years, months = form_defaults(page.text)
    rows = []
    for year in years:
        form = dict(base)
        form.update({"targetCd": grade, "yearList": year, "monthList": ",".join(months),
                     "arOrd": "1,2,3,4,5,,6,7,8", "subjIdList": "firstEnter",
                     "sort": "recent", "year": year})
        for page_no in range(1, 40):
            form["currentPage"] = str(page_no)
            r = session.post(AJAX, data=form, timeout=30,
                             headers={"X-Requested-With": "XMLHttpRequest",
                                      "Referer": f"{LIST}?targetCd={grade}"})
            r.raise_for_status()
            got = parse_rows(r.text)
            if not got:
                break
            rows += got
            total = re.search(r'<em class="tot">(\d+)', r.text)
            if total and page_no * len(got) >= int(total.group(1)):
                break
            time.sleep(pause)
        print(f"  {grade} {year}: 누적 {len(rows)}건", file=sys.stderr)
    return rows


def build(session, pause):
    db = {}
    for grade in GRADES:
        seen = set()
        for subj, year, label, date, p, a, h in scrape(session, grade, pause):
            key = (subj, year, date, label)
            if key in seen:
                continue
            seen.add(key)
            db.setdefault(grade, {}).setdefault(subj, {}).setdefault(year, []).append(
                [label, date, p, a, h])
    for grade in db:
        for subj in db[grade]:
            for year in db[grade][subj]:
                db[grade][subj][year].sort(key=lambda r: r[1], reverse=True)
    return db


def squeeze(raw):
    """같은 자료면 같은 바이트가 나오게 눌러 담는다.

    gzip은 머리에 '압축한 시각'을 적는다. gzip.compress()를 그냥 쓰면 자료가
    한 글자도 안 바뀌어도 결과 바이트가 매번 달라진다. 한 달에 한 번 돌 때는
    티가 안 났는데, 매일 돌게 되자 **새 회차가 없는 날에도 index.html이
    바뀐 것으로 잡혀** 커밋과 배포가 날마다 나갔다. 시각을 0으로 박아 둔다.
    """
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb", compresslevel=9, mtime=0) as f:
        f.write(raw)
    return buf.getvalue()


def merge(current, scraped, known):
    """기존 기록은 손대지 않고, 아직 없는 시행일의 회차만 덧붙인다.

    제목을 새로 만들어 덮어쓰지 않는 이유: 기존 표기가 바뀌고, 무엇보다 kindOf()가
    제목으로 평가원·교육청을 가르므로 분류가 뒤집힐 수 있다.

    한 과목의 한 시행일을 통째로 단위로 삼는 이유: 같은 날 같은 과목의 A/B형·홀짝형은
    기존 페이로드가 이미 변형별로 나눠 담고 있는데, 목록에서 뽑은 제목은 그 변형을
    같은 형태로 재현하지 못한다. 파일 경로를 열쇠로 삼으면 이미 있는 회차가 다른
    이름을 달고 한 번 더 들어간다. 새 시행일만 받는 편이 안전하다.
    """
    added, filled, skipped = 0, 0, set()
    for g in scraped:
        for s in scraped[g]:
            if s not in known.get(g, ()):
                skipped.add(f"{g}/{s}")
                continue
            for y in scraped[g][s]:
                bucket = current.setdefault(g, {}).setdefault(s, {}).setdefault(y, [])
                dates = {r[1] for r in bucket}
                late = {}
                for row in scraped[g][s][y]:
                    if not any(row[2:5]):
                        continue
                    if row[1] in dates:
                        late.setdefault(row[1], []).append(row)
                        continue
                    dates.add(row[1])
                    bucket.append(row)
                    added += 1
                filled += top_up(bucket, late)
                bucket.sort(key=lambda r: r[1], reverse=True)
    return added, filled, sorted(skipped)


def top_up(bucket, late):
    """이미 있는 회차의 **빈 칸만** 채운다. 있는 값은 절대 건드리지 않는다.

    EBSi는 한 회차를 한 번에 올리지 않는다. 재보니 정답은 시행 당일 낮,
    문제는 당일 저녁이 보통인데 해설은 평가원 시험의 경우 다음 날 오후,
    늦으면 나흘 뒤에 올라온다. 문제조차 엿새 늦은 회차가 있었다.

    갱신이 한 달에 한 번일 때는 다 올라온 뒤에 보므로 상관없었다. 매일 보게
    되면 반드시 반쪽만 잡히는 날이 생기는데, 예전처럼 '이미 있는 시행일은
    통째로 건너뛰기'만 하면 그 빈칸이 영영 빈칸으로 남는다.

    있는 값을 덮어쓰지 않는 원칙은 그대로다 — 파일 이름이 과목과 어긋난
    회차들(2015년 시행 수능 등)을 지켜 주는 것이 그 원칙이라, 빈 칸을 메우는
    일과는 상관이 없다.

    같은 날 같은 과목에 홀·짝형이 따로 있을 수 있어 어느 줄에 넣을지가
    문제인데, 이미 들어 있는 코드가 하나라도 같은 줄을 짝으로 본다. 그렇게
    가려지지 않으면 양쪽이 한 줄씩일 때만 채우고, 아니면 손대지 않는다.
    """
    n = 0
    for row in bucket:
        rows = late.get(row[1])
        if not rows or all(row[2:5]):
            continue
        same = [r for r in rows
                if any(r[i] and row[i] and r[i] == row[i] for i in (2, 3, 4))]
        if len(same) != 1:
            if len(rows) != 1 or sum(1 for r in bucket if r[1] == row[1]) != 1:
                continue                      # 어느 줄의 것인지 가릴 수 없다
            same = rows
        for i in (2, 3, 4):
            if not row[i] and same[0][i]:
                row[i] = same[0][i]
                n += 1
    return n


def count(db):
    return sum(len(v) for g in db.values() for s in g.values() for v in s.values())


def known_subjects(text):
    """index.html의 GROUPS가 아는 과목 코드 — 화면 드롭다운이 이 목록으로 만들어진다.

    화면이 모르는 과목을 담아 봐야 드롭다운에 나오지 않으니 페이로드만 무거워진다.
    그래서 담지 않고 경고만 남긴다 — **그 경고가 곧 "여기 더 담을 게 있다"는 목록이다.**
    직업탐구와 제2외국어·한문이 실제로 그렇게 오래 빠져 있었다. 수집은 진작부터
    되고 있었고(EBSi 요청의 arOrd 에 7·8이 들어 있다) 여기서만 버려지고 있었다.
    GROUPS 에 넣자 21년치 1,215회차가 한 번에 들어왔다.

    그러니 이 경고가 길어지면 한 번씩 들여다볼 것. 다만 아무거나 넣지는 않는다 —
    화면에 이름을 지어 줄 수 있는 과목만 넣는다.
    """
    i = text.find("const GROUPS")
    block = text[i:text.find("\n};", i)]
    out, cur = {}, None
    for m in re.finditer(r'\b(D\d00)\s*:|\["[^"]*","(\d+)"\]', block):
        if m.group(1):
            cur = m.group(1)
            out[cur] = set()
        elif cur:
            out[cur].add(m.group(2))
    if not out or not all(out.values()):
        raise SystemExit("GROUPS에서 과목 코드를 읽지 못했습니다")
    return out


def load_current(text):
    m = PAYLOAD_RE.search(text)
    if not m:
        raise SystemExit("index.html에서 payload 블록을 찾지 못했습니다")
    return json.loads(gzip.decompress(base64.b64decode(m.group(2).strip())))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", default="index.html")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--pause", type=float, default=0.4, help="요청 간 간격(초)")
    # 무엇이 늘었는지 한 줄로 적어 둔다. 워크플로가 이것을 커밋 메시지에 넣고,
    # 화면의 '자료 갱신 내역'이 그 메시지를 읽어 그날 무슨 일이 있었는지 보여준다.
    ap.add_argument("--note", metavar="파일", help="바뀐 내용을 한 줄로 적을 곳")
    args = ap.parse_args()

    path = Path(args.index)
    text = path.read_text(encoding="utf-8")
    current = load_current(text)
    have = count(current)

    known = known_subjects(text)

    session = requests.Session()
    session.headers["User-Agent"] = UA
    scraped = build(session, args.pause)

    reachable = sum(len(v) for g, subs in scraped.items() for s, v0 in subs.items()
                    if s in known.get(g, ()) for v in v0.values())
    print(f"수집 {count(scraped)}건 (GROUPS 안 {reachable}건) / 현재 페이로드 {have}건",
          file=sys.stderr)

    # 파서가 망가지면 조용히 빈손이 된다. 덧붙이기라 자료가 사라지진 않지만,
    # 아무것도 못 건진 채 "변경 없음"으로 끝나는 것도 실패로 알려야 한다.
    if reachable < have * 0.8:
        raise SystemExit(
            f"수집량이 기존의 80%에 못 미칩니다({reachable} < {have}). "
            "EBSi 페이지 구조가 바뀌었을 수 있어 파일을 건드리지 않습니다.")

    added, filled, skipped = merge(current, scraped, known)
    got = count(current)
    print(f"새 회차 {added}건 추가 → {got}건"
          + (f", 늦게 올라온 자료 {filled}칸 채움" if filled else ""), file=sys.stderr)
    if skipped:
        print(f"참고: GROUPS에 없어 담지 않은 과목 {len(skipped)}개 — "
              f"{', '.join(skipped[:12])}{' …' if len(skipped) > 12 else ''}", file=sys.stderr)

    blob = base64.b64encode(squeeze(
        json.dumps(current, ensure_ascii=False, separators=(",", ":")).encode())).decode()
    new = PAYLOAD_RE.sub(lambda m: m.group(1) + blob + m.group(3), text, count=1)

    if new == text:
        print("변경 없음", file=sys.stderr)
        return 0
    if args.dry_run:
        print(f"[dry-run] {added}건 증가 · {filled}칸 채움, 쓰지 않음", file=sys.stderr)
        return 0
    path.write_text(new, encoding="utf-8")
    print(f"갱신 완료: {have} → {got}건", file=sys.stderr)
    if args.note:
        Path(args.note).write_text(
            f"새 회차 {added}건" + (f", 늦게 올라온 자료 {filled}칸" if filled else ""),
            encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
