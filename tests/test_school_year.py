"""Long labels use 20nn학년도; short labels use nn, consistently across all exams."""
import json
from harness import CHROME, ROOT, site
from playwright.sync_api import sync_playwright
_srv, SITE=site()
with sync_playwright() as pw:
    browser=pw.chromium.launch(executable_path=CHROME)
    page=browser.new_page(service_workers='block')
    page.goto(SITE);page.wait_for_selector('.item')
    page.wait_for_function('()=>!!window.GijulOmrForms')
    cases=[
        ('20260902','9월 모평(평가원)','2027학년도','27 9평',2027),
        ('20260604','6월 모평(평가원)','2027학년도','27 6평',2027),
        ('20261119','수능','2027학년도','27 수능',2027),
        ('20251113','수능 홀수형','2026학년도','26 수능',2026),
        ('20260324','3월 학평(서울)','2027학년도','27 3모',2027),
        ('20211012','10월 학평(서울)','2022학년도','22 10모',2022),
    ]
    for date,title,label,short,printed in cases:
        got=page.evaluate('''([date,title])=>{const meta={date,title,grade:'D300',subjectId:'158'};return {
          label:yearLabel(meta),short:shortName(date.slice(0,4),title,'생명과학Ⅰ'),
          heading:GijulOmrForms.heading(meta),printed:GijulOmrForms.paperPreset(meta,GijulOmrForms.forms.inquiry).year,
          file:fileName(date.slice(0,4),title,'생명과학Ⅰ','문제','same.pdf','D300','158',date),
          folder:folderName(date.slice(0,4),title,'생명과학Ⅰ','D300','158',date)};}''',[date,title])
        assert got['label']==label,got
        assert got['short'].startswith(short+' '),got
        assert got['heading']==label+' '+title,got
        assert got['printed']==str(printed),got
        assert label in got['file'] and label in got['folder'],got
    # Check every catalog row against the existing source-backed official metadata.
    rows=[]
    for f in (ROOT/'data').glob('D*/*.json'):
        for p in json.loads(f.read_text())['papers']:
            rows.append([p['date'].replace('-',''),p['title'],f"{p['year']+1}학년도"])
    got=page.evaluate('rows=>rows.map(([date,title,expected])=>[yearLabel({date,title}),expected])',rows)
    assert all(actual==expected for actual,expected in got),[r for r in got if r[0]!=r[1]][:5]
    assert page.locator('#yr option[value="2026"]').inner_text()=='2027학년도'
    assert page.locator('.yr-head .y').first.inner_text()=='2027학년도'
    assert '2027학년도' in page.locator('.item .meta').first.inner_text()
    page.goto(SITE+'s/D300/158.html');page.wait_for_selector('tbody tr')
    row=page.locator('tbody tr').filter(has_text='2026-09-02')
    assert '2027학년도' in row.inner_text()
    assert '2027학년도' in row.get_attribute('data-nm')
    print(f'Academic/execution years: six official cases, {len(rows)} catalog rows, filenames, OMR and static pages passed')
    browser.close()
