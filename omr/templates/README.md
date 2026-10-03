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
