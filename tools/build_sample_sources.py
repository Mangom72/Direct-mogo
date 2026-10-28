#!/usr/bin/env python3
"""공식 예시 PDF의 정확한 URL 목록을 Android 허용 목록으로 생성한다."""
import argparse
import json
from pathlib import Path
from build_api import read_samples

ROOT=Path(__file__).resolve().parent.parent
TARGET=ROOT/'android/app/src/main/java/kr/gijul/direct/PaperSources.java'

def generated(samples):
    years={}
    for p in samples:
        for f in p['files']:
            if f['url'] in years and years[f['url']]!=p['schoolYear']:
                raise ValueError('같은 PDF의 대상 학년도가 다릅니다')
            years[f['url']]=p['schoolYear']
    values='\n'.join('        out.put('+json.dumps(u)+', '+str(years[u])+');' for u in sorted(years))
    return '''package kr.gijul.direct;

import java.util.Collections;
import java.util.HashMap;
import java.util.Map;

/** tools/build_sample_sources.py generates this exact list from the verified sample catalog.
 * Host-wide MOE/KICE downloads and redirected targets are not permitted. */
final class PaperSources {
    private PaperSources() { }
    private static final Map<String, Integer> PDFS = sources();
    private static Map<String, Integer> sources() {
        Map<String, Integer> out = new HashMap<>();
'''+values+'''
        return Collections.unmodifiableMap(out);
    }
    static boolean known(String url) { return url != null && PDFS.containsKey(url); }
    static String filename(String url) {
        Integer year = PDFS.get(url);
        return year == null ? null : year + "학년도 수능 예시문항.pdf";
    }
    static boolean redirectAllowed(String initial, String target) {
        return known(initial) && initial.equals(target);
    }
}
'''

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true');args=ap.parse_args()
    text=generated(read_samples((ROOT/'index.html').read_text()))
    if args.check:
        if not TARGET.exists() or TARGET.read_text()!=text:
            raise SystemExit('예시문항 원본과 Android 허용 목록이 다릅니다. build_sample_sources.py를 실행하세요.')
    else: TARGET.write_text(text)
    print('Android 공식 예시 PDF 허용 목록 일치' if args.check else 'Android 공식 예시 PDF 허용 목록 생성')

if __name__=='__main__':main()
