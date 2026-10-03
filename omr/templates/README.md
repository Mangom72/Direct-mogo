# Official specimen images

Source: Gyeonggi Office of Education, “2026학년도 수능 답안지 견본”, 2025-10-29.
https://www.goe.go.kr/goe/na/ntt/selectNttInfo.do?mi=10961&nttSn=2330309

Public attachment:
https://www.goe.go.kr/resource/goe/na/bbs_2675/2025/10/3b72ea50-8b53-46bc-9cee-bc92e17483f1.zip

The six front-side PDFs were rendered unmodified using `pdftoppm -scale-to 1800
-singlefile -png` and encoded as lossless WebP (OpenCV `IMWRITE_WEBP_QUALITY=101`).
Each image is 1800×1406. The original specimen watermark is preserved. No personal
answer sheets or actual student photographs are bundled. Dynamic study metadata
is a separate DOM layer; the official images themselves are not retitled.
See [implementation and limits](../../docs/omr.md).


## Manual-entry fronts without a specimen watermark

`manual/` uses the six unmodified front-side JPEGs in the official **2027학년도
(2026년 시행) 9월 모평 실시요강** HWP, publicly posted by a Gyeonggi Education school:
https://gcja-h.goeay.kr/gcja-h/na/ntt/selectNttInfo.do?bbsId=2506&mi=5763&nttSn=1329024

Direct original:
https://gcja-h.goeay.kr/upload/gcja-h/na/bbs_2506/2026/08/040b6b26-ca97-4783-9fd5-cea5e3d17eb7.hwp

HWP SHA-256: `ad031e20abd3a9544b1ee7abd23b855117c6c0d73c72dd94f1dd7c0f7ef730e5`.

Extract the compressed OLE `BinData/BIN0002.jpg` through `BIN0007.jpg` streams
using raw DEFLATE (`zlib.decompress(data, -15)`). In order: Korean, math, English,
history, inquiry, second language. They are 3420×2683 pixels, except inquiry
3447×2683. No rotation, retouching, watermark removal or upscaling is applied.
Encode each original as lossless WebP. The assets retain the source JPEG pixels,
including the original printing and registration marks. These fronts have no
specimen watermark. Compared with the prior 786×619 fronts, the width is over
four times larger. Lossless assets total about 15 MiB and are cached offline.

Marking coordinates use a logical 1800px width with per-image aspect ratios.
Each layout was recalibrated against the new originals. These manual fronts are
never substituted for the separately calibrated 2026 CSAT photo recognition
reference. Printed periods and areas remain intact. Compiled SVG exam/year presets use
per-image pixel rectangles; the original 2027 September title remains intact
when it matches. Inquiry area presets distinguish social/science/vocational
subjects. The original image files and photo references remain unmodified.
See [preset generation and license](../HEADINGS.md).
