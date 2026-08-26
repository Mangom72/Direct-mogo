# 웹과 앱 — 무엇이 어디에 있는가

개발용 지도입니다. 같은 `index.html` 하나가 세 군데에서 돕니다.

| 실행 환경 | 무엇으로 가리는가 | 무엇이 다른가 |
|---|---|---|
| 데스크톱·iOS 브라우저 | `NATIVE === false` · `__androidWeb === false` | 순수 웹 |
| 안드로이드 브라우저 | `NATIVE === false` · `__androidWeb === true` | 위 + **앱 설치 권유 막대** |
| 앱(WebView) | `NATIVE`(= `window.GijulNative`)가 있음 | 위 + **창구 20개** |

`const NATIVE = typeof GijulNative !== "undefined" && GijulNative;` (index.html)
하나가 모든 갈림의 기준입니다. **UA를 보지 않습니다** — 창구가 실제로 있는지만
봅니다. UA로 가리면 검색엔진 렌더러와 성능 측정 도구까지 함께 걸립니다
(`tests/test_toapp.py`가 지킵니다).

---

## 앱에만 있던 것 가운데 웹으로 내려온 것

| 기능 | 앱 | 웹 |
|---|---|---|
| 오프라인 저장(회차 전체) | `MainActivity.save()` | Cache Storage — `webVault().save()` |
| 받아둔 자료 목록·열기·지우기 | `listSaved`·`openSaved`·`deleteSaved` | 같은 화면, 뒤판만 다름 |
| '담김' 표시 | `listSaved` 대조 | 통 이름 대조 |

셋 다 **EBSi가 CORS를 열어 두어서** 가능해진 것입니다 — 응답을 우리가 읽을 수
있어야 담고 크기를 셉니다. 저쪽이 그 헤더를 지우면 웹 쪽만 조용히 멈춥니다.
자세한 것은 [docs/ios.md](ios.md)에 있습니다.

---

## 양쪽에 똑같이 있는 것

전부 `index.html` 안에서만 돌고 앱은 아무것도 안 합니다.

| 기능 | 비고 |
|---|---|
| 회차 조회·거르기 | 5,059회차가 `<script id="payload">`에 gzip+base64로 들어 있습니다 |
| 내 과목 | `★` 저장 · 길게 눌러 순서 변경 · `#subs=` 링크로 다른 기기에 |
| 푼 회차 표시 | `✓` · 푼 날 도장(길게 눌러 수정) · 연도별 진도 · **안 푼 것만** |
| 푼 날 달력 | 태블릿 2단 / 폰 1단 · 화살표·Home/End·PageUp/Down |
| 백업 파일 | 내보내기·가져오기 · 합치기가 기본 |
| 다크 모드 | 자동/밝게/어둡게. 앱에서는 `systemDark()`로 시스템을 물어봅니다 |
| 주소로 공유 | `#/D300/158/2024/gov` |
| 수능 D-day | 11월 13~19일 사이의 목요일로 셈 |
| 등급컷·정답률 | EBSi 풀서비스로 나가는 링크(고3 2022-03-24 이후) |
| 오프라인 | 서비스 워커. **웹뷰도 SW를 지원하므로 앱에서도 같습니다** |
| AI로 쓰기 · 자료 갱신 내역 | 갱신 내역은 `api.github.com`을 직접 읽습니다 |

---

## 앱에만 있는 것

| 기능 | 어디 | 왜 웹으로 못 하는가 |
|---|---|---|
| 앱 안 PDF 뷰어 | `PdfViewActivity` | WebView에 PDF 뷰어가 없습니다 |
| **시험 시간 재기** | `Clock`·`Timing`·`Exam` | 문제지가 새 탭으로 열려 우리 화면이 안 보입니다 |
| 다른 앱 위에 띄우기 | `FloatService`·`PickerView`·`Catalog` | 브라우저에 오버레이 창이 없습니다 |
| 홈 화면 위젯 여섯 | `*Widget`·`WidgetBase`·`Widgets`·`Solved` | — |
| 자동 백업 | SAF 지속 권한 | `File System Access API`가 안드로이드 크롬에 없습니다 |
| 앱 사본에서 되살리기 | `savedSolved` | — |
| 앱 자체 업데이트 | `Updater` | 스토어를 안 거칩니다 |
| 앱 링크 | `assetlinks.json` | — |

---

## 같은 기능인데 갈래가 다른 것

**여기가 버그가 숨는 자리입니다.** 한쪽만 고치면 다른 쪽이 조용히 어긋납니다.

| 기능 | 앱 | 웹 |
|---|---|---|
| 문제지 열기 | 앱 안 뷰어(`openPaperAt`) | 새 탭 |
| 보내기 | 네이티브 공유 시트(`shareFile`) | Web Share API → 실패 시 다운로드 |
| 오프라인 저장 | 앱 폴더에 **회차별 하위 폴더** | **Cache Storage에 회차별 통** (`gijul-vault:회차`) |
| 파일로 받기 | 위와 같음 | 시트의 '파일로 내려받기' — 낱개, 400ms 간격 |
| '담김' 표시 | 있음 | **있음** — 보관함은 우리 것이라 물어볼 수 있습니다 |
| 홈 화면 권유 | 없음(이미 앱) | 안드로이드는 APK, **iOS는 '홈 화면에 추가'** |
| 백업 내보내기 | 공유 시트(`saveBackup`) | `<a download>` |
| 백업 가져오기 | SAF(`pickBackup`) | `<input type="file">` |

저장과 보관함은 **`Vault` 어댑터 하나**를 지납니다(`index.html`). 뒤판이 둘이고
(`nativeVault()` / `webVault()`) 부르는 쪽은 어느 쪽인지 모릅니다 — 이 파일에서
`NATIVE.무엇`을 흩뿌리지 않는 첫 자리입니다. 갈래가 셋 이상 되는 기능부터
이렇게 갑니다.

---

## 다리 — 페이지 → 앱

`window.GijulNative`의 창구 20개입니다. 전부 `MainActivity.Bridge`에 있습니다.

| 창구 | 하는 일 |
|---|---|
| `systemDark()` → `boolean` | 시스템이 야간 모드인가 |
| `where()` → `String` | 받아둔 자료가 놓이는 경로(사람이 읽는 용) |
| `openPaper(url, name)` | 뷰어로 연다 |
| `openPaperIn(url, name, grade, sub)` | + 어느 과목에서 왔는지 |
| `openPaperAt(url, name, grade, sub, key)` | + **회차 열쇠**(잰 시간을 여기 남깁니다) |
| `shareFile(name, url)` | 받아서 공유 시트로 |
| `savePaper(json)` | 회차 전체를 앱 폴더에 |
| `listSaved()` → `String` | 받아둔 것 목록 |
| `openSaved(folder, name)` | 받아둔 것 하나를 연다 |
| `deleteSaved(folder)` | 지운다(빈 문자열이면 전부) |
| `setSolved(json)` | 표시·내 과목·테마를 앱에 옮겨 적는다 → 위젯·자동 백업 |
| `savedSolved()` → `String` | 앱이 든 사본을 백업 모양으로 |
| `takeTimings()` → `String` | 잰 시간을 가져간다(한 번 넘긴 것은 지움) |
| `saveBackup(json, name)` | 백업 파일을 만들어 공유 시트로 |
| `pickBackup()` | 백업 파일을 고르게 한다 |
| `pickAutoBackup()` | 자동 백업할 자리를 고르게 한다 |
| `autoBackup()` → `String` | 지금 어디에 쓰는지 · 막혔는지 |
| `stopAutoBackup()` | 그만둔다 |
| `appVersion()` → `String` | 지금 판 |
| `checkUpdate(announce)` · `installUpdate()` | 새 판 확인·설치 |

## 다리 — 앱 → 페이지

앱이 `evaluateJavascript`로 부릅니다. 전부 `window.gijul*` 입니다.

| 창구 | 언제 |
|---|---|
| `gijulBack()` → `boolean` | 뒤로가기 — 열린 것 하나를 닫고 참을 준다 |
| `gijulOpenCal()` | 달력 위젯을 눌렀는데 앱이 이미 떠 있을 때 |
| `gijulThemeChanged()` | 시스템 야간 모드가 바뀜 |
| `gijulShareDone(ok, msg)` | 공유 끝 |
| `gijulSaveResult(ok, n, msg)` | 저장·삭제 끝 |
| `gijulBackupPicked(text)` | 백업 파일을 골랐다 |
| `gijulAutoBackup(state)` | 자동 백업 상태가 바뀜 |
| `gijulUpdateFound(json)` · `gijulUpdate(state, msg)` | 새 판 확인·설치 진행 |

---

## 창구를 더할 때의 규칙

**사다리는 `toApp()` 한 곳에 있습니다.** 호출부는 한 줄이고, 창구가 늘 때마다
칸이 붙는 자리는 그 함수 안뿐입니다 — `Vault` 와 같은 생각입니다.

**있던 메서드에 인자를 더하지 않습니다.** 자바스크립트 다리는 인자 수가 맞아야
찾아갑니다. 인자를 더하면 옛 앱에서 맞는 메서드가 없어 **호출이 통째로
실패**하고, 페이지는 앱보다 먼저 갱신되므로 그 사이 그 기능이 죽습니다.

이름을 새로 내고 갈래를 둡니다.

```js
if(NATIVE.openPaperAt && key) NATIVE.openPaperAt(url, nm, g, s, key);
else if(NATIVE.openPaperIn)   NATIVE.openPaperIn(url, nm, g, s);
else                          NATIVE.openPaper(url, nm);
```

`setSolved`의 꾸러미도 마찬가지입니다. `favs`·`theme`을 **더하는** 것은
안전하지만(모르는 열쇠는 지나갑니다) `marks`→`solved`처럼 **이름을 바꾸면**
그날 옛 앱의 위젯이 통째로 빕니다.

---

## 어디를 고치면 무엇이 도는가

| 고친 곳 | 워크플로 | 무엇 |
|---|---|---|
| `index.html`·`sw.js`·`s/`·`fonts/`·`tools/`·`tests/` | `tests.yml` | 회귀 시험 35종 |
| `android/**` | `android.yml` | `test_twins` → JVM 단위 시험 23개 → 서명 빌드 → 지문 확인 → 릴리스 |
| (매일 23시 KST) | `refresh-data.yml` | EBSi 수집 → 수능 날짜 대조 → 새 회차 카나리아 |

**앱을 고쳤으면 판올림까지가 한 벌입니다.** 올리지 않은 변경은 CI가 빌드만 하고
버리므로 아무에게도 가지 않습니다.

---

이 갈림을 **iOS로 옮길 수 있는가**는 [docs/ios.md](ios.md)에 있습니다 — 앱의
기능 하나하나를 Safari·홈 화면 웹 앱과 대조해 A/B/C/D로 갈라 두었습니다.
