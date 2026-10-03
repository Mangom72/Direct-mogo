"""Fixed-template synthetic OMR probe; does not validate physical camera accuracy.

Run in the isolated environment described in docs/omr-feasibility.md.
Only generated images are used; no exam files or user photographs are needed.
"""
import argparse
import json
from pathlib import Path
import cv2 as cv
import numpy as np
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', type=Path, default=Path('.git/codex-evidence/omr-photo'))
root = parser.parse_args().output
root.mkdir(parents=True, exist_ok=True)
W, H = (900, 1300)
anchors = np.float32([[50, 50], [850, 50], [850, 1250], [50, 1250]])
answers = [5, 3, 2, 4, 3, 3, 5, 1, 1, 2, 4, 1, 3, 2, 5, 5, 4, 2, 1, 1]
expected = answers.copy()
expected[5] = 'blank'
expected[11] = 'multiple'
expected[16] = 'faint'
centers = []
canvas = np.full((H, W, 3), 255, np.uint8)
for x, y in anchors:
    cv.rectangle(canvas, (int(x - 15), int(y - 15)), (int(x + 15), int(y + 15)), (10, 10, 10), -1)
cv.putText(canvas, 'GIJUL / PRACTICE OMR / 20', (90, 145), cv.FONT_HERSHEY_SIMPLEX, 0.9, (75, 75, 120), 2)
cv.putText(canvas, 'GM-20-01', (90, 198), cv.FONT_HERSHEY_SIMPLEX, 0.6, (110, 110, 110), 1)
for i, a in enumerate(answers):
    col, row = divmod(i, 10)
    y = 290 + row * 83
    xs = [140 + col * 400 + j * 49 for j in range(5)]
    centers.append([(x, y) for x in xs])
    cv.putText(canvas, str(i + 1), (85 + col * 400, y + 7), cv.FONT_HERSHEY_SIMPLEX, 0.6, (95, 85, 105), 1)
    for j, x in enumerate(xs):
        cv.ellipse(canvas, (x, y), (12, 17), 0, 0, 360, (180, 145, 215), 1)
        cv.putText(canvas, str(j + 1), (x - 4, y + 5), cv.FONT_HERSHEY_SIMPLEX, 0.35, (180, 145, 215), 1)
        if i == 5:
            continue
        if j + 1 == a or (i == 11 and j == 3):
            level = 160 if i == 16 else 15
            cv.ellipse(canvas, (x, y), (11, 16), 0, 0, 360, (level, level, level), -1)
cv.imwrite(str(root / 'synthetic-sheet.png'), canvas)

def corners(image):
    gray = cv.cvtColor(image, cv.COLOR_BGR2GRAY)
    _, bw = cv.threshold(gray, 75, 255, cv.THRESH_BINARY_INV)
    cs, _ = cv.findContours(bw, cv.RETR_EXTERNAL, cv.CHAIN_APPROX_SIMPLE)
    pts = []
    for c in cs:
        area = cv.contourArea(c)
        poly = cv.approxPolyDP(c, 0.03 * cv.arcLength(c, True), True)
        if 250 < area < 3000 and len(poly) == 4:
            m = cv.moments(c)
            pts.append([m['m10'] / m['m00'], m['m01'] / m['m00']])
    if len(pts) != 4:
        raise ValueError('alignment markers missing or ambiguous')
    p = np.float32(pts)
    left = p[np.argsort(p[:, 0])[:2]]
    right = p[np.argsort(p[:, 0])[2:]]
    return np.float32([left[np.argmin(left[:, 1])], right[np.argmin(right[:, 1])], right[np.argmax(right[:, 1])], left[np.argmax(left[:, 1])]])

def read(image):
    found = corners(image)
    fixed = cv.warpPerspective(image, cv.getPerspectiveTransform(found, anchors), (W, H), borderValue=(255, 255, 255))
    gray = cv.cvtColor(fixed, cv.COLOR_BGR2GRAY)
    background = cv.medianBlur(gray, 61)
    norm = np.clip(gray.astype(np.float32) * 255 / np.maximum(background.astype(np.float32), 1), 0, 255)
    got = []
    for row in centers:
        values = []
        for x, y in row:
            roi = norm[y - 9:y + 10, x - 6:x + 7]
            values.append(float(np.mean(1 - roi / 255)))
        strong = [i + 1 for i, v in enumerate(values) if v > 0.7]
        weak = [i + 1 for i, v in enumerate(values) if 0.2 < v <= 0.7]
        got.append('multiple' if len(strong) > 1 else 'faint' if weak else strong[0] if strong else 'blank')
    return got
cases = []
p0 = np.float32([[0, 0], [W - 1, 0], [W - 1, H - 1], [0, H - 1]])
for perspective, p1 in enumerate([p0, np.float32([[65, 40], [865, 85], [825, 1240], [35, 1270]]), np.float32([[95, 50], [840, 20], [875, 1225], [25, 1280]])]):
    for shadow in [False, True]:
        for blur in [0, 3]:
            image = cv.warpPerspective(canvas, cv.getPerspectiveTransform(p0, p1), (W, H), borderValue=(235, 235, 235))
            if shadow:
                image = np.clip(image.astype(float) * np.linspace(0.62, 1, W)[None, :, None], 0, 255).astype(np.uint8)
            if blur:
                image = cv.GaussianBlur(image, (blur, blur), 0.8)
            _, encoded = cv.imencode('.jpg', image, [cv.IMWRITE_JPEG_QUALITY, 80])
            image = cv.imdecode(encoded, cv.IMREAD_COLOR)
            got = read(image)
            ok = got == expected
            cases.append({'perspective': perspective, 'shadow': shadow, 'blur': blur, 'passed': ok, 'classified': got})
            if not ok:
                print('Mismatch:', cases[-1])
            if perspective == 1 and shadow and blur:
                cv.imwrite(str(root / 'synthetic-photo.jpg'), image)
clipped = canvas.copy()
clipped[:90, :90] = 255
try:
    read(clipped)
    reject = False
except ValueError:
    reject = True
result = {'opencv': cv.__version__, 'syntheticCases': len(cases), 'passed': sum((c['passed'] for c in cases)), 'missingCornerRejected': reject, 'expected': expected, 'cases': cases, 'scope': 'Own fixed-template synthetic images only; no physical camera or official OMR recognition tested.'}
(root / 'photo-probe.json').write_text(json.dumps(result, indent=2))
print({k: v for k, v in result.items() if k not in ['cases', 'expected']})
assert result['passed'] == len(cases) and reject
