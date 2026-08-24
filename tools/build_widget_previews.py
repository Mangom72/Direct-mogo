#!/usr/bin/env python3
"""위젯 고르는 화면에 뜰 미리보기 그림을 만든다.

<h3>왜 그림인가</h3>
안드로이드 12부터는 `previewLayout`(진짜 레이아웃)을 쓸 수 있지만, 그것은
**빈 채로** 뜬다 — 위젯의 내용은 전부 코드가 채우고 레이아웃에는 글자가 하나도
없기 때문이다. 고르는 화면에 빈 상자 여섯 개가 나란히 서면 무엇이 무엇인지
가릴 수가 없다. 레이아웃마다 글자를 박아 넣은 사본을 또 만드는 길도 있으나,
그러면 같은 그림이 두 벌이 되어 한쪽만 고치는 날이 온다.

그림 한 장이면 API 24부터 34까지 전부에서 같은 것이 뜬다. 어두운 쪽은
`drawable-night-nodpi` 에 따로 두어 안드로이드가 골라 준다.

<h3>글꼴</h3>
저장소의 `fonts/GijulSans-*.woff2` 를 그대로 쓴다. 미리보기만 다른 글꼴이면
받아 놓고 열었을 때 딴 앱처럼 보인다. woff2 는 PIL이 못 읽으므로 fontTools 로
ttf 로 풀어 임시로 쓴다.

    python3 tools/build_widget_previews.py

고칠 일이 잦지 않다 — 위젯의 생김새를 손봤을 때만 다시 돌리면 된다.
"""
import math
import pathlib
import tempfile

from PIL import Image, ImageDraw, ImageFont
from fontTools.ttLib import TTFont

ROOT = pathlib.Path(__file__).resolve().parent.parent
RES = ROOT / "android/app/src/main/res"
S = 3                                    # 3배로 그려 둔다. 런처가 줄이면 곱게 나온다

LIGHT = dict(card="#FCFAF4", ink="#191713", ink2="#6B6353", rule="#CFC6AC",
             mark="#B4342A", gov="#1D4E6B", edu="#4A6B3D")
NIGHT = dict(card="#1F2531", ink="#ECE7DA", ink2="#AEB5C2", rule="#3A4353",
             mark="#F08379", gov="#8AC6EA", edu="#A6D48D")

# ── 미리보기에 담을 이야기 ──────────────────────────────────────────────
# 여섯 장이 같은 하루를 말하게 둔다. 장마다 다른 숫자가 적혀 있으면 무엇을
# 세는 위젯인지가 아니라 값이 눈에 걸린다.
TODAY = 24                               # 이 달의 24일, 화요일
DDAY = 87
MONTH = 8
CAL = {                                  # 날 → [(과목, 평가원인가)]
    3: [("확통", 1)], 4: [("미적", 0)], 8: [("언매", 1)],
    11: [("생1", 0), ("화1", 1)], 14: [("확통", 1)], 17: [("사문", 0)],
    18: [("미적", 1)], 21: [("지1", 0)],
    22: [("확통", 1), ("언매", 1), ("미적", 0)],
    24: [("확통", 1)], 25: [("생1", 0)],
}
WEEK = [1, 2, 2, 0, 0, 0, 0]             # 일~토
STREAK = 3
RECENT = [("8.24", "26 6평 확통", 1), ("8.24", "26 9평 미적", 1),
          ("8.23", "26 3모 언매", 0), ("8.22", "25 수능 생1", 1),
          ("8.21", "26 5모 사문", 0)]
NEXT = [("27 6평 확통", 1), ("26 수능 언매", 1), ("27 3모 사문", 0)]
DOW = ["일", "월", "화", "수", "목", "금", "토"]

_fonts = {}


def font(weight, size):
    key = (weight, round(size * S))
    if key not in _fonts:
        _fonts[key] = ImageFont.truetype(_ttf(weight), round(size * S))
    return _fonts[key]


_ttf_cache = {}


def _ttf(weight):
    if weight not in _ttf_cache:
        out = pathlib.Path(tempfile.gettempdir()) / f"GijulSans-{weight}.ttf"
        if not out.exists():
            f = TTFont(ROOT / f"fonts/GijulSans-{weight}.woff2")
            f.flavor = None
            f.save(out)
        _ttf_cache[weight] = str(out)
    return _ttf_cache[weight]


def px(dp):
    return dp * S


def fit(span, ratio, lo, hi):
    """칸 크기에 맞춰 자란다. 자바 쪽 WidgetBase.fit 과 같은 셈이다 — 두 곳의
    숫자가 어긋나면 미리보기가 진짜와 다른 그림이 된다."""
    return max(lo, min(hi, span * ratio))


def mix(a, b, t):
    a, b = a.lstrip("#"), b.lstrip("#")
    return "#" + "".join(
        f"{round(int(a[i:i+2],16) + (int(b[i:i+2],16) - int(a[i:i+2],16)) * t):02x}"
        for i in (0, 2, 4))


def dim(c, alpha=0.19):
    """칸 바탕에 깔리는 옅은 색. 앱에서는 알파 0x30 을 얹는데, 그림에는 알파를
    남기지 않는다 — 런처가 뒤에 무엇을 깔지 알 수 없어서다."""
    return c, alpha


class Card:
    """위젯 한 장. 바탕·머리글·꼬리글은 여섯이 똑같다."""

    def __init__(self, w, h, c):
        self.w, self.h, self.c = w, h, c
        self.img = Image.new("RGBA", (px(w), px(h)), (0, 0, 0, 0))
        self.g = ImageDraw.Draw(self.img)
        self.g.rounded_rectangle([0, 0, px(w) - 1, px(h) - 1], px(18), fill=c["card"])

    def text(self, x, y, s, weight, size, color, anchor="la"):
        self.g.text((px(x), px(y)), s, font=font(weight, size), fill=color, anchor=anchor)

    def wide(self, s, weight, size):
        return self.g.textlength(s, font=font(weight, size)) / S

    def head(self, left, right):
        self.text(10, 10, left, 700, 13.5, self.c["ink"])
        if right:
            self.text(self.w - 10, 11.5, right, 700, 10.5, self.c["mark"], anchor="ra")

    def foot(self, s):
        self.text(10, self.h - 21, s, 500, 10.5, self.c["ink2"])

    def blend(self, box, color, alpha, radius=0):
        """카드 바탕 위에 옅게 얹는다"""
        self.g.rounded_rectangle(box, radius, fill=mix(self.c["card"], color, alpha))


# ── 여섯 장 ────────────────────────────────────────────────────────────

def cal(c, w=250, h=250):
    k = Card(w, h, c)
    n = sum(len(v) for v in CAL.values())
    k.head(f"{MONTH}월", f"{n}회차")
    k.foot(f"수능 D-{DDAY} · 오늘 {len(CAL[TODAY])}회차")

    x0, y0 = 10, 33
    gw, gh = w - 20, h - 21 - 6 - y0
    weeks = 5
    cw = gw / 7
    ch0 = gh / (weeks + 0.55)
    head, ch = ch0 * 0.55, ch0

    dow = fit(head, 0.62, 8, 13)
    for i, d in enumerate(DOW):
        k.text(x0 + cw * (i + .5), y0 + head - dow * 0.35 - dow, d, 700, dow,
               c["mark"] if i == 0 else c["ink2"], anchor="ma")

    pad = max(2, cw * 0.045)
    day = fit(ch, 0.17, 8.5, 14)
    chip_t = fit(ch, 0.15, 7.5, 12)
    chip_h, gap = chip_t * 1.55, chip_t * 1.55 * 0.16

    for d in range(1, 32):
        col, row = (d - 1) % 7, (d - 1) // 7
        cx, cy = x0 + cw * col, y0 + head + ch * row
        k.g.rectangle([px(cx), px(cy), px(cx + cw), px(cy + ch)], outline=c["rule"], width=S)
        ty = cy + pad + day                        # 글자 밑선
        if d == TODAY:
            rr = day * 0.78
            ccx, ccy = cx + pad + rr, ty - day * 0.36
            k.g.ellipse([px(ccx - rr), px(ccy - rr), px(ccx + rr), px(ccy + rr)], fill=c["ink"])
            k.text(ccx, ccy, str(d), 700, day, c["card"], anchor="mm")
        else:
            k.text(cx + pad, ty - day, str(d), 500, day,
                   c["mark"] if col == 0 else c["ink2"])

        it = CAL.get(d)
        if not it:
            continue
        top = ty + day * 0.45
        room = cy + ch - top - pad
        fits = int(room // (chip_h + gap))
        show = min(fits, len(it))
        if show < len(it) and show > 0 and room - show * (chip_h + gap) < chip_t:
            show -= 1
        for i in range(show):
            name, gov = it[i]
            bar = c["gov"] if gov else c["edu"]
            cyy = top + i * (chip_h + gap)
            bw = max(1.6, cw * 0.018)
            k.blend([px(cx + pad), px(cyy), px(cx + cw - pad), px(cyy + chip_h)], bar, .19)
            k.g.rectangle([px(cx + pad), px(cyy), px(cx + pad + bw), px(cyy + chip_h)], fill=bar)
            k.text(cx + pad + bw * 1.7, cyy + (chip_h - chip_t) * 0.38, name, 500, chip_t, c["ink"])
        if show < len(it):
            k.text(cx + pad, top + show * (chip_h + gap), f"+{len(it) - show}",
                   500, chip_t * 0.94, c["ink2"])
    return k.img


def week(c, w=250, h=110):
    k = Card(w, h, c)
    k.text(10, 9, f"{STREAK}일째", 700, 24, c["mark"])
    k.text(10 + k.wide(f"{STREAK}일째", 700, 24) + 6, 21, "이어서 풀고 있습니다", 500, 11, c["ink2"])
    k.foot(f"수능 D-{DDAY} · 이번 주 {sum(WEEK)}회차")

    x0, y0 = 10, 40
    aw, ah = w - 20, h - 26 - y0
    lab, foot = fit(ah, 0.22, 10, 17), fit(ah, 0.20, 9, 15)
    txt = fit(ah, 0.14, 8, 12)
    area = max(1, ah - lab - foot)
    cw = min((aw - 5 * 6) / 7, min(28, area * 0.55))
    gap = max(5, min((aw - cw * 7) / 6, cw * 1.1))
    left = x0 + (aw - (cw * 7 + gap * 6)) / 2
    top, bot = y0 + lab, y0 + ah - foot
    rnd = min(6, cw * 0.28)
    hi = max(1, max(WEEK))
    for i, n in enumerate(WEEK):
        x = left + i * (cw + gap)
        k.text(x + cw / 2, top - txt * 1.45, DOW[i], 700, txt,
               c["mark"] if i == 0 else c["ink2"], anchor="ma")
        k.g.rounded_rectangle([px(x), px(top), px(x + cw), px(bot)], px(rnd), fill=c["rule"])
        if n:
            fill = max(rnd * 2, (bot - top) * n / hi)
            k.g.rounded_rectangle([px(x), px(bot - fill), px(x + cw), px(bot)], px(rnd), fill=c["mark"])
            k.text(x + cw / 2, bot + foot * 0.2, str(n), 500, txt, c["ink2"], anchor="ma")
        if i == 2:      # 오늘은 밑줄로 — 막대 색을 바꾸면 '많이 푼 날'과 헷갈린다
            k.g.rectangle([px(x), px(bot + 2), px(x + cw), px(bot + 3.5)], fill=c["ink"])
    return k.img


def turf(c):
    k = Card(250, 110, c)
    weeks = 15
    k.head("푼 날", f"{STREAK}일째")
    # 씨앗 없는 난수 대신 정해진 무늬 — 다시 돌려도 같은 그림이 나와야 한다.
    # 뒤로 갈수록 촘촘하다. 잔디밭이 답하는 질문이 '요즘 하고 있나'라서다.
    pat = []
    for col in range(weeks):
        for row in range(7):
            h = (col * 37 + row * 61 + 11) % 100
            pat.append(0 if h >= 18 + col * 5 else 3 if h < 3 + col else 2 if h < 8 else 1)
    k.foot(f"수능 D-{DDAY} · {weeks}주 {sum(pat)}회차")

    x0, y0, w, h = 10, 34, 230, 46
    cell = (h - 2 * 6) / 7
    gap = max(2, cell * 0.16)
    cell = (h - gap * 6) / 7
    for col in range(weeks):
        for row in range(7):
            n = pat[col * 7 + row]
            t = {0: 0, 1: .38, 2: .68, 3: 1.0}[n]
            fill = c["rule"] if n == 0 else mix(c["rule"], c["mark"], t)
            x, y = x0 + col * (cell + gap), y0 + row * (cell + gap)
            k.g.rounded_rectangle([px(x), px(y), px(x + cell), px(y + cell)],
                                  px(max(1.5, cell * 0.18)), fill=fill)
    return k.img


def recent(c):
    k = Card(250, 172, c)
    k.head("최근 푼 것", f"{STREAK}일째")
    k.foot(f"수능 D-{DDAY} · 오늘 {len(CAL[TODAY])}회차")
    y = 34
    for d, t, gov in RECENT:
        k.text(10, y, d, 500, 10.5, c["ink2"])
        k.g.rounded_rectangle([px(48), px(y - 1), px(51), px(y + 13)], px(1.5),
                              fill=c["gov"] if gov else c["edu"])
        k.text(57, y - 1, t, 500, 11.5, c["ink"])
        y += 21
    return k.img


def dday(c):
    k = Card(110, 110, c)
    k.text(55, 20, f"D-{DDAY}", 700, 30, c["mark"], anchor="ma")
    k.text(55, 57, "수능까지", 500, 10.5, c["ink2"], anchor="ma")
    hit, days = len(CAL), 31
    k.g.rounded_rectangle([px(10), px(76), px(100), px(81)], px(2.5), fill=c["rule"])
    k.g.rounded_rectangle([px(10), px(76), px(10 + 90 * hit / days), px(81)], px(2.5), fill=c["mark"])
    k.text(55, 88, f"{MONTH}월 {hit}일 · {sum(len(v) for v in CAL.values())}회차",
           500, 10.5, c["ink2"], anchor="ma")
    return k.img


def nxt(c):
    k = Card(250, 122, c)
    k.head("다음에 풀 것", "안 푼 것")
    k.foot("누르면 그 과목으로")
    y = 33
    for t, gov in NEXT:
        k.g.rounded_rectangle([px(10), px(y - 1), px(13), px(y + 14)], px(1.5),
                              fill=c["gov"] if gov else c["edu"])
        k.text(20, y, t, 700, 12, c["ink"])
        y += 20
    return k.img


DRAW = {"cal": cal, "week": week, "turf": turf,
        "recent": recent, "dday": dday, "next": nxt}


def main():
    for theme, colors, out in (("밝은", LIGHT, RES / "drawable-nodpi"),
                               ("어두운", NIGHT, RES / "drawable-night-nodpi")):
        out.mkdir(parents=True, exist_ok=True)
        for name, fn in DRAW.items():
            img = fn(colors)
            p = out / f"w_pre_{name}.png"
            # 알파를 남긴다 — 모서리가 둥글어서, 없애면 검은 귀가 네 개 생긴다
            img.quantize(colors=192, method=Image.FASTOCTREE).save(p, optimize=True)
            print(f"  {theme} {p.name} {p.stat().st_size // 1024}KB {img.size[0]}×{img.size[1]}")


if __name__ == "__main__":
    main()
