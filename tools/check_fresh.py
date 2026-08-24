#!/usr/bin/env python3
"""EBSi가 새 회차를 아직 올리고 있는가.

`refresh_data.py` 는 <b>수집량이 기존의 80%에 못 미치면</b> 스스로 실패한다.
EBSi 화면 구조가 바뀌어 스크레이퍼가 빈손이 되는 경우는 그것이 잡는다.

잡지 못하는 결이 하나 남는다 — **옛 자료는 그대로 잘 주면서 새 회차만 안 올라오는**
경우다. 수집량은 100%이고 워크플로는 매일 초록불인데 자료는 그날로 멈춘다. 사람이
지켜보지 않는 것을 전제로 만든 저장소라, 알아차릴 자리가 없다.

<h3>왜 날짜 간격으로 재지 않는가</h3>
'며칠째 새 회차가 없으면 이상하다'로 두면 거짓 경보만 낸다. 시행일 간격이 원래
들쭉날쭉하기 때문이다 — 3월 중순은 지난 11월 수능 이후로 **127일**이 비어 있는
것이 정상이고, 7~9월도 53일이 빈다. 그 위에 문턱을 두면 4개월짜리 알람이 되어
아무것도 못 잡는다.

<h3>그래서 수능 하나만 본다</h3>
수능은 **날짜를 우리가 셈할 수 있는 유일한 회차**다(11월 13~19일 사이의 목요일).
그리고 반드시 EBSi에 올라온다. 그 하루가 지나고도 3주가 지났는데 그 시행일의
회차가 자료에 하나도 없으면, 그것은 간격이 아니라 고장이다. 거짓 경보가 원리적으로
나올 수 없고, 하필 학생이 가장 급한 때(수능 직후)에 멈춘 것을 잡는다.

    python3 tools/check_fresh.py [--index index.html] [--date 2026-12-15]
"""
import argparse
import base64
import datetime
import gzip
import json
import re
import sys

GRACE = 21          # EBSi는 한 회차를 며칠에 걸쳐 올린다. 넉넉히 준다.


def payload(text):
    m = re.search(r'<script id="payload"[^>]*>(.*?)</script>', text, re.S)
    if not m:
        raise SystemExit("index.html 에서 payload 를 찾지 못했습니다")
    return json.loads(gzip.decompress(base64.b64decode(m.group(1).strip())))


def suneung(year):
    """11월 13~19일 사이의 목요일. 7일 창이라 목요일이 하나뿐이다."""
    for d in range(13, 20):
        t = datetime.date(year, 11, d)
        if t.weekday() == 3:
            return t
    return datetime.date(year, 11, 19)      # 닿을 수 없다


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", default="index.html")
    ap.add_argument("--date", help="오늘로 칠 날 (YYYY-MM-DD). 시험용")
    a = ap.parse_args()

    today = (datetime.date.fromisoformat(a.date) if a.date
             else datetime.date.today())
    db = payload(open(a.index, encoding="utf-8").read())
    dates = {r[1] for g in db.values() for sub in g.values()
             for yr in sub.values() for r in yr}

    # 지나간 수능 중 가장 최근 것
    t = suneung(today.year)
    if t > today:
        t = suneung(today.year - 1)

    waited = (today - t).days
    key = t.strftime("%Y%m%d")
    have = sum(1 for d in dates if d == key)
    print(f"가장 최근 수능: {t} ({waited}일 전) · 자료에 있는 그날 회차: {have}개")

    if waited < GRACE:
        print(f"아직 {GRACE}일이 안 지났습니다 — 넘어갑니다")
        return 0
    if have:
        return 0

    print()
    print(f"★ {t} 수능이 {waited}일 전인데 그날의 회차가 자료에 하나도 없습니다.")
    print("  EBSi 가 올리지 않았거나, 우리가 못 받고 있습니다.")
    print("  https://www.ebsi.co.kr 에서 직접 확인하고, 올라와 있다면")
    print("  tools/refresh_data.py 가 그 회차를 왜 못 봤는지 보십시오.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
