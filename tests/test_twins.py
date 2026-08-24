"""화면과 위젯이 같은 말을 하는가 — 두 벌로 적힌 규칙이 어긋나지 않았는가.

<h3>왜 두 벌인가</h3>
회차 이름을 '26 6평 확통'으로 줄이는 규칙과 수능 날을 셈하는 규칙이 페이지
(`index.html`)와 앱(`Solved.java`·`Widgets.java`) <b>양쪽에</b> 있다. 합칠 수가
없다 — 위젯은 홈 화면에 뜨는 것이라 페이지를 열어 물어볼 수 없고, 물어보자고
자료를 받아 오게 하면 잔디밭 한 장 그리려고 망을 타게 된다.

<h3>어긋나면 어떻게 되는가</h3>
조용하다. 목록에는 '26 6평 확통'이라고 적히고 위젯에는 '25 6월 모평 확률과
통계'라고 적히는데, 어느 쪽도 오류가 아니라서 아무 데도 걸리지 않는다. 과목이
새로 생기는 날(교육과정이 바뀔 때)에 한쪽만 고치면 정확히 그렇게 된다.

그래서 여기서 두 파일을 열어 직접 견준다. 브라우저도 기기도 쓰지 않는다.
"""
import re, sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from harness import ROOT

BAD = []
def ck(cond, msg):
    if not cond:
        BAD.append(msg)

JS = (ROOT / "index.html").read_text(encoding="utf-8")
SOLVED = (ROOT / "android/app/src/main/java/kr/gijul/direct/Solved.java").read_text(encoding="utf-8")
WIDGETS = (ROOT / "android/app/src/main/java/kr/gijul/direct/Widgets.java").read_text(encoding="utf-8")

# ── 1. 과목 줄임말 표 ───────────────────────────────────────────────────
m = re.search(r"const SHORT_SUB = \{(.*?)\};", JS, re.S)
ck(m, "index.html 에서 SHORT_SUB 를 찾지 못했습니다")
js_map = dict(re.findall(r'"([^"]+)"\s*:\s*"([^"]+)"', m.group(1))) if m else {}

m = re.search(r"String\[\]\[\] t = \{(.*?)\};", SOLVED, re.S)
ck(m, "Solved.java 에서 줄임말 표를 찾지 못했습니다")
jv_map = dict(re.findall(r'\{"([^"]+)","([^"]+)"\}', m.group(1))) if m else {}

print(f"1. 줄임말 — 화면 {len(js_map)}개 · 앱 {len(jv_map)}개")
only_js = sorted(k for k in js_map if k not in jv_map)
only_jv = sorted(k for k in jv_map if k not in js_map)
differ = sorted(k for k in js_map if k in jv_map and js_map[k] != jv_map[k])
print("   화면에만:", only_js or "없음", "· 앱에만:", only_jv or "없음")
print("   값이 다름:", [(k, js_map[k], jv_map[k]) for k in differ] or "없음")
ck(not only_js, f"앱에 없는 과목이 있습니다: {only_js}")
ck(not only_jv, f"화면에 없는 과목이 있습니다: {only_jv}")
ck(not differ, f"줄임말이 다릅니다: {[(k, js_map[k], jv_map[k]) for k in differ]}")

# ── 2. 회차 이름 줄이기 ─────────────────────────────────────────────────
#
# 두 쪽의 정규식을 꺼내 파이썬으로 같은 이름에 돌린다. 자바스크립트와 자바가
# 서로 다른 엔진이라 '똑같이 쓰였는가'를 글자로만 견주면 표기 차이에 걸리므로,
# 실제 회차 이름 198종에 돌려 <b>결과가 같은가</b>를 본다.
def js_rules():
    body = re.search(r"function shortRound\(title\)\{(.*?)\n\}", JS, re.S).group(1)
    out = []
    for mm in re.finditer(r"\.replace\(/(.+?)/(g?),\s*\"(.*?)\"\)", body):
        out.append((mm.group(1), mm.group(3), mm.group(2) == "g"))
    return out

def jv_rules():
    body = re.search(r"static String shortRound\(String title\) \{(.*?)\n    \}", SOLVED, re.S).group(1)
    out = []
    for mm in re.finditer(r'replaceAll\("((?:[^"\\]|\\.)*)",\s*"((?:[^"\\]|\\.)*)"\)', body):
        # 자바 소스의 문자열 리터럴을 푼다. unicode_escape 를 쓰면 한글이
        # 깨진다 — UTF-8 바이트를 latin-1 로 읽어 버린다. 여기서 실제로 이스케이프
        # 되어 있는 것은 역슬래시와 따옴표뿐이다. 
        pat = mm.group(1).replace('\\"', '"').replace("\\\\", "\\")
        rep = mm.group(2).replace('\\"', '"').replace("\\\\", "\\")
        out.append((pat, rep, True))          # replaceAll 은 언제나 전부
    return out

def run(rules, s):
    for pat, rep, g in rules:
        rep = re.sub(r"\$(\d)", r"\\\1", rep)
        s = re.sub(pat, rep, s, count=0 if g else 1)
    return s.strip()

jr, vr = js_rules(), jv_rules()
print(f"2. 이름 줄이기 규칙 — 화면 {len(jr)}줄 · 앱 {len(vr)}줄")
ck(len(jr) == len(vr), f"규칙 수가 다릅니다: 화면 {len(jr)} · 앱 {len(vr)}")

import base64, gzip, json
raw = gzip.decompress(base64.b64decode(
    re.search(r'<script id="payload"[^>]*>(.*?)</script>', JS, re.S).group(1).strip()))
titles = sorted({r[0] for g in json.loads(raw).values()
                 for sub in g.values() for yr in sub.values() for r in yr})
diff = [(t, run(jr, t), run(vr, t)) for t in titles if run(jr, t) != run(vr, t)]
print(f"   회차 이름 {len(titles)}종 중 다르게 줄어드는 것:", len(diff))
for t, a, b in diff[:4]:
    print(f"      {t!r} → 화면 {a!r} · 앱 {b!r}")
ck(not diff, f"{len(diff)}종이 화면과 앱에서 다르게 줄어듭니다")
print("   보기:", [f"{t} → {run(jr, t)}" for t in titles[:3]])

# ── 3. 수능 날 셈하는 규칙 ──────────────────────────────────────────────
#
# 11월 13~19일 사이의 목요일. 7일 창이라 목요일이 하나뿐이어서 해만 알면 날이
# 정해진다. 한쪽만 창을 옮기면 D-day 가 화면과 위젯에서 하루 이상 갈린다.
def window(src, lo_pat, hi_pat):
    lo = re.search(lo_pat, src)
    hi = re.search(hi_pat, src)
    return (int(lo.group(1)) if lo else None, int(hi.group(1)) if hi else None)

js_win = window(JS, r"for\(let d = (\d+); d <= \d+", r"for\(let d = \d+; d <= (\d+)")
jv_win = window(WIDGETS, r"for \(int d = (\d+); d <= \d+", r"for \(int d = \d+; d <= (\d+)")
print(f"3. 수능 창 — 화면 11월 {js_win[0]}~{js_win[1]}일 · 앱 11월 {jv_win[0]}~{jv_win[1]}일")
ck(js_win == (13, 19), f"화면의 창이 11월 13~19일이 아닙니다: {js_win}")
ck(js_win == jv_win, f"수능 창이 화면과 앱에서 다릅니다: {js_win} vs {jv_win}")
ck("THURSDAY" in WIDGETS, "앱이 목요일을 찾지 않습니다")

print("\n=== 문제:", "없음" if not BAD else "")
for x in BAD:
    print("  ★", x)
sys.exit(1 if BAD else 0)
