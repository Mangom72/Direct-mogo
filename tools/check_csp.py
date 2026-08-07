#!/usr/bin/env python3
"""index.html의 CSP 해시가 실제 인라인 스크립트와 맞는지 본다.

CSP를 해시로 걸면 인라인 스크립트를 한 글자만 고쳐도 그 스크립트가 통째로
막힌다. 화면은 조용히 반쪽만 동작하고, 콘솔을 열어보기 전에는 알 수 없다.
스크립트를 고친 뒤 이걸 돌리면 어긋난 자리를 짚어준다.

    python3 tools/check_csp.py            # 확인만
    python3 tools/check_csp.py --fix      # 어긋난 해시를 지금 값으로 고쳐 쓴다

payload 블록(type="application/octet-stream")은 실행되지 않으므로 세지 않는다 —
월간 자료 갱신이 그 블록만 고쳐 쓰는 덕에 자료가 늘어도 해시는 그대로다.
"""
import argparse
import base64
import hashlib
import pathlib
import re
import sys


def sha(body: str) -> str:
    return "sha256-" + base64.b64encode(hashlib.sha256(body.encode()).digest()).decode()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", default="index.html")
    ap.add_argument("--fix", action="store_true", help="어긋난 해시를 고쳐 쓴다")
    a = ap.parse_args()

    path = pathlib.Path(a.index)
    html = path.read_text(encoding="utf-8")

    meta = re.search(r'<meta http-equiv="Content-Security-Policy" content="(.*?)">', html, re.S)
    if not meta:
        print("CSP meta 태그가 없습니다", file=sys.stderr)
        return 1

    want = [sha(m.group(1)) for m in re.finditer(r"<script>(.*?)</script>", html, re.S)]
    have = re.findall(r"'(sha256-[A-Za-z0-9+/=]+)'", meta.group(1))

    if want == have:
        print(f"맞습니다 — 인라인 스크립트 {len(want)}개, 해시 {len(have)}개")
        return 0

    print(f"어긋났습니다 — 스크립트 {len(want)}개, CSP에 적힌 해시 {len(have)}개")
    for i, w in enumerate(want):
        mark = "  " if i < len(have) and have[i] == w else "★ "
        print(f"  {mark}{i + 1}번째  실제 {w}")
        if i < len(have) and have[i] != w:
            print(f"        CSP  {have[i]}")
    for extra in have[len(want):]:
        print(f"  ★ CSP에만 있음  {extra}")

    if not a.fix:
        print("\n--fix 를 주면 지금 값으로 고쳐 씁니다")
        return 1

    body = meta.group(1)
    for old, new in zip(have, want):
        body = body.replace(old, new, 1)
    # 개수가 늘었으면 script-src 줄에 덧붙인다
    for new in want[len(have):]:
        body = re.sub(r"(script-src [^;]*)", rf"\1 '{new}'", body, count=1)
    html = html[:meta.start(1)] + body + html[meta.end(1):]
    path.write_text(html, encoding="utf-8")
    print("\n고쳐 썼습니다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
