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

`manual/` uses the six front-side images on PDF pages 23–28 of the 2023 September
mock assessment guide (2024 academic year), publicly hosted by Incheon Education:
https://www.ice.go.kr/upload/board/553/2023/08/94fb44f69915ae62e22e90c609421995.pdf

The embedded 619×786 JPEGs were extracted with `pdfimages -f 23 -l 28 -j`,
rotated clockwise, and encoded as lossless WebP with ImageMagick. The resulting
786×619 pixels retain the original printed content; this source has no specimen
watermark. Its original resolution is lower than the CSAT specimen. Each layout
has its own marking coordinates in `forms.js`; these images are used for manual
entry, never substituted into the photo recognition reference mask. The exam
heading shown to learners is a separate DOM layer.
