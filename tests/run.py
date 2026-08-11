#!/usr/bin/env python3
"""시험을 모두 돌린다.

    python3 tests/run.py                # 전부
    python3 tests/run.py sw stale       # 이름에 그 말이 든 것만
    python3 tests/run.py -v             # 출력까지 그대로

서버는 여기서 한 번만 띄워 모든 시험이 나눠 쓴다. 자기 사본이 필요한 시험
(서비스 워커가 셸 변경을 알아채는지 보는 것들)은 제 서버를 따로 띄운다.

**합격 판정.** 종료 코드가 0이 아니면 실패다. 그리고 아래 표시가 출력에 있으면
역시 실패로 본다 — 시험들이 사람이 읽을 수 있게 결과를 적어 온 방식이라,
그 표시를 그대로 판정에 쓴다. 새 시험을 쓸 때도 이 표시를 따르면 된다.

    ★              무엇이 어긋났는지 적을 때
    전체: 실패 / 문제: 있음 / ERRORS: [ / 기대대로: False
"""
import os
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from harness import Serve, SHOT                                    # noqa: E402

FAIL = re.compile(r"★|전체: 실패|문제: 있음|ERRORS: \[|기대대로: False")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    loud = "-v" in sys.argv or "--verbose" in sys.argv
    tests = sorted(p for p in HERE.glob("test_*.py")
                   if not args or any(a in p.stem for a in args))
    if not tests:
        print("고른 시험이 없습니다"); return 1

    with Serve() as srv:
        env = dict(os.environ, GIJUL_URL=srv.url, GIJUL_SHOT=str(SHOT))
        print(f"서버 {srv.url} · 시험 {len(tests)}개 · 남는 그림 {SHOT}\n")
        bad, t0 = [], time.time()
        for p in tests:
            began = time.time()
            r = subprocess.run([sys.executable, str(p)], env=env,
                               capture_output=True, text=True, timeout=900)
            out = r.stdout + r.stderr
            failed = r.returncode != 0 or FAIL.search(out)
            bad.append(p.stem) if failed else None
            print(f"  {'★ 실패' if failed else '통과  '}  {p.stem:<20} {time.time()-began:5.1f}초")
            if loud or failed:
                print("".join(f"        {l}\n" for l in out.rstrip().split("\n")[-40:]))
    print(f"\n{len(tests) - len(bad)}/{len(tests)} 통과 · {time.time()-t0:.0f}초")
    if bad:
        print("실패:", ", ".join(bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
