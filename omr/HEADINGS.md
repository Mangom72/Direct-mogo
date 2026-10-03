# OMR heading presets

`headings.svg` contains fixed exam/area symbols and ten year-digit symbols.
They are SVG paths, with no `<text>`, runtime font loading, or text measurement.
The app selects a preset and stamps digits into the measured header rectangle.
The original period circles/labels and non-inquiry area printing remain intact.
Titles that already match the underlying official form are kept unchanged.
Original source images and recognition references are never retouched.

Native-pixel rectangles `(x, y, width, height)` are in `forms.js`:

| Form | Title | Inquiry area |
|---|---|---|
| Manual Korean/English/history/language | 176, 213, 1400, 78 | — |
| Manual math | 176, 187, 1400, 78 | — |
| Manual inquiry | 190, 188, 1390, 77 | 458, 315, 532, 110 |
| Photo review | 120, 105, 550, 42 | 260, 166, 400, 64 |

Exam names are CSAT, June/September mock CSAT, and month-specific national
academic evaluations. CSAT/mock CSAT use the academic year (execution year + 1);
national academic evaluations use the execution year. Unrecognized exam titles
use a generic answer-sheet preset and retain the exact exam name in the sidebar.
The presets are learning labels rather than an officially issued new form.

Outlines use Noto Sans CJK KR Medium version 2.004, distributed under SIL OFL 1.1.
Source project: https://github.com/notofonts/noto-cjk
Pinned source (Korean face 1 of the TTC):
https://raw.githubusercontent.com/notofonts/noto-cjk/f8d157532fbfaeda587e826d4cd5b21a49186f7c/Sans/OTC/NotoSansCJK-Medium.ttc

SHA-256: `197d5e1e019faca33a4d55931c7d68b8056f3b97cb862049f5cb8de9efdfb8ce`.
Copyright and license: [headings-OFL.txt](headings-OFL.txt).
The font binary is a build input only and is not loaded by the app.

Rebuild using `requirements/fonts.txt` (also included in the pinned test env):

```sh
python3 tools/build_omr_headings.py --font /path/to/NotoSansCJK-Medium.ttc
python3 tools/build_omr_headings.py --font /path/to/NotoSansCJK-Medium.ttc --check
```

Tests measure coloured oval positions in the original pixels, check that heading
regions do not overlap answer buttons, and load actual preset paths in Chromium
and the required WebKit CI run. Photo tests continue using unmodified references.
