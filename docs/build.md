<!-- README에서 옮겨온 문서. 이 저장소를 고칠 사람에게 필요한 내용이고,
     자료를 찾으러 온 사람에게는 필요 없어서 여기로 뺐습니다. -->

# 만드는 쪽

빌드 도구도 서버도 없습니다. GitHub Pages에 정적 파일만 올라갑니다.

| 파일 | 역할 |
|---|---|
| `index.html` | 앱 전체. 자료 3,844회차가 gzip+base64로 안에 들어 있습니다 (154KB) |
| `sw.js` | 서비스 워커. 앱 셸·글꼴·받아둔 PDF를 캐시합니다 |
| `data/`, `llms.txt`, `llms-full.txt` | AI·프로그램용 정적 JSON과 사용 안내 |
| `s/`, `sitemap.xml` | 검색엔진과 사람이 읽는 과목별 정적 페이지 |
| `robots.txt` | 크롤러 안내 ([아래](#robotstxt는-이-저장소에서-효력이-없습니다) 참고) |
| `fonts/` | 화면에 나오는 글자만 담은 웹폰트 |
| `tools/refresh_data.py` | EBSi에서 새 회차를 긁어 페이로드를 갱신합니다 |
| `tools/build_api.py` | 페이로드를 `data/` JSON과 `llms.txt`로 내보냅니다 |
| `tools/build_pages.py` | `data/`를 `s/` 정적 페이지와 `sitemap.xml`로 내보냅니다 |
| `tools/build_fonts.py` | 저장소 안의 글자를 모아 웹폰트를 잘라 만듭니다 |
| `tools/check_csp.py` | 인라인 스크립트 해시가 CSP와 맞는지 봅니다 |
| `android/` | WebView 앱 ([docs/android.md](android.md)) |
| `.github/workflows/refresh-data.yml` | 매일 23시(KST) 자동 실행 |

자료를 `index.html` 안에 넣어둔 덕분에 **이 파일 하나만 캐시하면 조회·필터가
네트워크 없이 전부 동작합니다.** 네트워크가 필요한 건 PDF를 받을 때뿐입니다.

PDF는 EBSi가 `Access-Control-Allow-Origin: *`를 주기 때문에 페이지가 직접 받아
`navigator.share()`로 넘길 수 있습니다. 그래서 설치형 앱에서도 노트앱으로 보내집니다.

## 자료 갱신

새 회차는 워크플로가 알아서 채웁니다. 직접 돌리려면:

```bash
pip install requests "fonttools[woff]" brotli
python3 tools/refresh_data.py --dry-run   # 무엇이 늘어나는지만 확인
python3 tools/refresh_data.py             # index.html 갱신
python3 tools/build_api.py                # → data/, llms.txt
python3 tools/build_pages.py              # → s/, sitemap.xml
python3 tools/build_fonts.py              # → fonts/
```

**순서가 있습니다.** `build_fonts.py`는 화면에 실제로 나오는 글자만 담으므로 맨
나중에 돌아야 새 회차 제목과 새 과목 페이지의 글자를 함께 봅니다. 빠뜨리면 그
글자가 네모(□)로 보입니다. `python3 tools/build_fonts.py --check`가 망 없이
확인만 해 줍니다. 워크플로도 같은 순서로 돕니다.

기존 기록의 **있는 값은 고치지 않습니다.** 새 시행일을 덧붙이고, 이미 있는 회차는
**비어 있던 칸만** 뒤늦게 채웁니다. 수집량이 기존의 80%에 못 미치면 EBSi 구조가
바뀐 것으로 보고 파일을 건드리지 않은 채 실패합니다.

### 왜 매일이고, 왜 23시인가

EBSi가 한 회차를 한 번에 올리지 않습니다. 파일 헤더(`Last-Modified`)로 재보면
시행일 0시 기준으로:

| | 빠르면 | 늦으면 |
|---|---|---|
| 정답 | +11시간 | +18시간 |
| 문제 | +9시간 | **+6일** |
| 해설 (평가원) | +25시간 | **+4.7일** |

정답과 문제는 대개 **시행 당일 저녁**에 올라오므로 23시에 보면 그날 시험이 그날
안에 실립니다. 해설은 며칠 걸리는 일이 흔해서, 한 번에 다 잡으려 하지 않고 매일
보면서 빈칸을 채웁니다(`top_up`). 덧붙이기만 하던 예전 방식으로 매일 돌리면
반쪽만 잡힌 회차의 빈칸이 **영영 빈칸으로** 남습니다.

새 자료가 없는 날은 페이로드가 그대로이므로 워크플로가 거기서 끝납니다 — 정적
JSON·과목 페이지·글꼴을 다시 만들지 않고, 커밋도 하지 않습니다.

`data/index.json`의 `updated`는 **수록된 가장 최근 시행일**입니다. 돌린 날이
아니므로, 새 회차가 없으면 출력이 바이트 단위로 같고 워크플로도 커밋하지 않습니다.

`index.html`의 인라인 스크립트를 고쳤다면 `python3 tools/check_csp.py --fix`로
CSP 해시를 다시 맞춰야 합니다. 어긋난 채로 나가면 그 스크립트가 통째로 막혀
화면이 껍데기만 남습니다.

## 검색에서 찾아지게

`index.html`은 자료를 압축해 품고 JS로 풉니다. 사람에게는 빠르지만 검색엔진에는
**빈 페이지 한 장**입니다 — 3,844회차가 통째로 안 보입니다. 그래서 같은 자료를
스크립트 없이 그냥 읽히는 HTML로도 깔아 둡니다.

```
/s/                     과목 색인 49과목
/s/D300/158.html        고3·N수 생명과학Ⅰ 전 회차 (문제·정답·해설 직접 링크)
/sitemap.xml            위 51장
```

회차별 페이지는 만들지 않습니다. 3,844장이 되는데 한 장에 링크 세 개뿐이라
검색엔진이 알맹이 없는 페이지로 보고 오히려 깎습니다. 과목 페이지 한 장이 그 과목의
링크를 전부 담으므로 잃는 것도 없습니다.

앱 화면과 과목 페이지는 서로 오갑니다. 둘 다 canonical로 자기 자신을 가리켜
중복으로 잡히지 않습니다.

서비스 워커는 **앱 제 주소로 들어오는 이동만** 셸에서 답합니다. 과목 페이지까지
가로채면 첫 방문 때 셸 캐시에 얼어붙어 갱신이 영영 닿지 않습니다.

### robots.txt는 이 저장소에서 효력이 없습니다

크롤러는 **도메인 뿌리의 robots.txt 하나만** 읽습니다 —
`https://mangom72.github.io/robots.txt`. 여기는 프로젝트 페이지라 이 저장소의
파일이 놓이는 자리는 `/Direct-mogo/robots.txt`이고, 그 주소는 아무도 보지 않습니다.

실제로 효력을 갖는 사본은
[mangom72.github.io](https://github.com/Mangom72/mangom72.github.io) 저장소
뿌리에 있습니다. 이 저장소의 `robots.txt`를 고치면 **그쪽에도 같이 옮겨야
합니다.** 그 저장소는 앱 딥링크용 `.well-known/assetlinks.json`도 같은 방식으로
서비스하고 있습니다.

뿌리의 robots.txt는 그 계정의 **모든 프로젝트 페이지**에 적용됩니다. 다만 내용이
`Allow: /`라 기본 동작과 같으므로 실제로 달라지는 것은 `Sitemap:` 한 줄뿐입니다.

## 로컬에서 보기

```bash
python3 -m http.server 8000
```

서비스 워커는 `localhost`에서도 동작합니다. 캐시 때문에 변경이 안 보이면
개발자도구 → Application → Service Workers에서 Unregister 하세요.
