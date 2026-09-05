#!/usr/bin/env python3
"""GitHub Actions 파일이 조용히 다른 셸 명령으로 바뀌지 않는지 본다.

YAML의 보통 문자열을 여러 줄로 쓰면 줄바꿈이 공백으로 접힌다. 셸 줄 연속용
역슬래시까지 섞이면 다음 인수 앞에 공백이 붙은 별도 명령이 되어, 워크플로는
문법상 유효한데 실행할 때만 실패한다. 2026-09 갱신 중단이 바로 그 경우였다.
"""
import re
import subprocess
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"
SHA = re.compile(r"^[0-9a-f]{40}$")
EXPR = re.compile(r"\$\{\{.*?\}\}")


def indent(line):
    return len(line) - len(line.lstrip(" "))


def run_commands(lines):
    """run 값을 (행 번호, 셸 입력)으로 돌려준다. 필요한 YAML만 작게 읽는다."""
    out = []
    i = 0
    while i < len(lines):
        m = re.match(r"^(\s*)run:\s*(.*)$", lines[i])
        if not m:
            i += 1
            continue
        line_no = i + 1
        value = m.group(2).rstrip()
        base = len(m.group(1))
        if value in ("|", "|-", "|+", ">", ">-", ">+"):
            block = []
            i += 1
            while i < len(lines) and (not lines[i].strip() or indent(lines[i]) > base):
                block.append(lines[i])
                i += 1
            out.append((line_no, value, textwrap.dedent("\n".join(block))))
        else:
            out.append((line_no, "plain", value))
            i += 1
    return out


def main():
    errors = []
    files = sorted([*WORKFLOWS.glob("*.yml"), *WORKFLOWS.glob("*.yaml")])
    if not files:
        errors.append("워크플로 파일이 없습니다")

    for path in files:
        rel = path.relative_to(ROOT)
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()

        if re.search(r"(?m)^\s*pull_request_target\s*:", text):
            errors.append(f"{rel}: pull_request_target은 외부 PR 코드에 쓰기 권한을 줄 수 있습니다")
        if not re.search(r"(?m)^permissions\s*:", text):
            errors.append(f"{rel}: 최상위 permissions가 없습니다")

        for no, line in enumerate(lines, 1):
            m = re.match(r"^\s*-?\s*uses:\s*([^\s#]+)", line)
            if not m:
                continue
            action = m.group(1)
            if action.startswith("./"):
                continue
            ref = action.rsplit("@", 1)[-1] if "@" in action else ""
            if not SHA.fullmatch(ref):
                errors.append(f"{rel}:{no}: 외부 action을 40자리 커밋 SHA로 고정하세요 ({action})")

        for no, style, command in run_commands(lines):
            if style.startswith(">"):
                errors.append(f"{rel}:{no}: run에는 YAML 접기(>) 대신 | 또는 한 줄을 쓰세요")
            if style == "plain" and command.endswith("\\"):
                errors.append(f"{rel}:{no}: 한 줄 run을 역슬래시로 이어 쓰지 마세요")
            # GitHub 표현식 자체는 bash 문법이 아니므로 단순 문자열로 바꿔 검사한다.
            shell = EXPR.sub("github-expression", command)
            checked = subprocess.run(["bash", "-n"], input=shell, text=True,
                                     capture_output=True)
            if checked.returncode:
                why = checked.stderr.strip().splitlines()[-1]
                errors.append(f"{rel}:{no}: 셸 문법 오류: {why}")

    if errors:
        for error in errors:
            print("★", error)
        return 1
    print(f"워크플로 {len(files)}개 · action SHA·권한·run 셸 문법 정상")
    return 0


if __name__ == "__main__":
    sys.exit(main())
