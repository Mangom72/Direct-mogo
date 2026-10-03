#!/usr/bin/env python3
"""Extract review candidates from a local official problem PDF, never publish them.
Requires Poppler's pdftotext. Identity must be checked on the rendered first page.
Unmarked questions may use 2 points ONLY with --unmarked-two, an explicit reviewer
choice after checking the official subject scoring rule and the original PDF.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

START = re.compile(r'(?m)^([1-9]\d?)\.\s')
POINT = re.compile(r'\[\s*(\d+(?:\.\d+)?)\s*점\s*\]')


def extract(text, count, maximum, unmarked_two=False):
    starts = list(START.finditer(text))
    if [int(m[1]) for m in starts] != list(range(1, count + 1)):
        raise ValueError('문항 번호가 누락·중복·역순입니다. 원본을 확인해야 합니다.')
    points, implicit = [], []
    for i, start in enumerate(starts):
        end = starts[i + 1].start() if i + 1 < count else len(text)
        marks = POINT.findall(text[start.end():end])
        if len(marks) > 1 or marks and not re.fullmatch(r'[1234]', marks[0]):
            raise ValueError(f'{i + 1}번 배점 표시가 모호하거나 지원 범위를 벗어납니다.')
        if not marks:
            if not unmarked_two:
                raise ValueError(f'{i + 1}번의 배점 표시가 없습니다. 2점으로 추정하지 않습니다.')
            implicit.append(i + 1)
        points.append(int(marks[0]) if marks else 2)
    if sum(points) != maximum:
        raise ValueError(f'배점 합계 {sum(points)}점이 만점 {maximum}점과 다릅니다.')
    return points, implicit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pdf', type=Path)
    parser.add_argument('--count', type=int, required=True, choices=[20, 30, 45])
    parser.add_argument('--maximum', type=int, required=True, choices=[50, 100])
    parser.add_argument('--source', required=True, help='공식 원본 URL')
    parser.add_argument('--subject', required=True, help='원본 첫 페이지에서 확인할 과목명')
    parser.add_argument('--unmarked-two', action='store_true')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    data = args.pdf.read_bytes()
    if len(data) > 64 * 1024 * 1024 or not data.startswith(b'%PDF-'):
        parser.error('64MB 이하 PDF 원본이 필요합니다.')
    if not args.source.startswith('https://'):
        parser.error('원본 출처는 HTTPS URL이어야 합니다.')
    try:
        result = subprocess.run(['pdftotext', '-raw', str(args.pdf.resolve()), '-'],
                                capture_output=True, text=True, timeout=45, check=True)
        points, implicit = extract(result.stdout, args.count, args.maximum, args.unmarked_two)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        parser.error(str(error))
    candidate = {'reviewed': False, 'subjectToCheck': args.subject, 'source': args.source,
                 'sha256': hashlib.sha256(data).hexdigest(), 'points': points,
                 'implicitTwo': implicit, 'extractorWarnings': result.stderr.strip(),
                 'review': '첫 페이지의 시험명·시행일·과목·홀짝형 및 모든 배점을 원본과 대조 후 등록'}
    args.output.write_text(json.dumps(candidate, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'{len(points)}문항, {sum(points)}점: 검토 후보 저장 (아직 등록되지 않음)')


if __name__ == '__main__':
    main()
