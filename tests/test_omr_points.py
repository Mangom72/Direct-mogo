"""Fail closed on ambiguous PDF point extraction; source-matched reviewed points."""
import pathlib
import sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'tools'))
from collect_omr_points import extract


def rejects(text, count, maximum, implicit=False):
    try:
        extract(text, count, maximum, implicit)
    except ValueError:
        return
    raise AssertionError('Ambiguous extraction accepted')


assert extract('1. question [2점]\n2. question [3점]', 2, 5) == ([2, 3], [])
assert extract('1. question\n2. question [3점]', 2, 5, True) == ([2, 3], [1])
rejects('1. question\n2. question [3점]', 2, 5)
rejects('1. question [2점]\n1. duplicated [3점]', 2, 5)
rejects('2. question [3점]\n1. reversed [2점]', 2, 5)
rejects('1. question [2점] [3점]\n2. question [2점]', 2, 5)
rejects('1. question [2.5점]\n2. question [2점]', 2, 5)
rejects('1. question [2점]\n2. question [3점]', 2, 100)

import json
root = pathlib.Path(__file__).resolve().parents[1]
reviewed = json.loads((root / 'omr/points-reviewed.json').read_text())['entries']
assert len(reviewed) == 36
assert len({tuple(e['key']) for e in reviewed}) == 36
for entry in reviewed:
    count = len(entry['points'])
    assert count in [20, 30, 45]
    assert sum(entry['points']) == entry['maximum']
    assert all(p in [1, 2, 3, 4] for p in entry['points'])
    assert len(entry['sha256']) == 64 and entry['problemURL'].startswith('https://wdown.ebsi.co.kr/')
math = [e['points'] for e in reviewed if e['key'][1] in ['140119', '140120', '140121']]
assert len(math) == 18 and all(p == math[0] for p in math)
for subject in ['140117', '80003', '63004', '158', '191', '195']:
    points = [tuple(e['points']) for e in reviewed if e['key'][1] == subject]
    assert len(set(points)) > 1, subject
print('배점 추출의 누락·중복·역순·중복 배점·총점 거절, 36개 원본 배점: 통과')
