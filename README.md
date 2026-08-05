# 기출 직행

수능·모의평가·전국연합학력평가 **원본 PDF로 한 번에 이동하는** 페이지입니다.
EBSi를 헤매지 않고 학년 → 과목 → 연도만 고르면 문제·정답·해설이 바로 나옵니다.

**→ [mangom72.github.io/Direct-mogo](https://mangom72.github.io/Direct-mogo/)**

![밝은 화면과 어두운 화면](docs/screenshot.png)

2006년 시행분부터 **3,844회차 · 49과목**을 담고 있습니다.

## 할 수 있는 것

- **내 과목** — 자주 보는 과목을 ★로 저장해 한 줄 버튼으로. 꾹 눌러 순서 변경, 링크로 다른 기기에 옮기기
- **보내기** — PDF를 받아 공유 시트로 넘깁니다. 홈 화면 앱에서도 노트앱으로 바로 보낼 수 있습니다
- **오프라인 저장** — 회차의 문제·정답·해설을 한 번에 내려받아, 연결이 없어도 파일 앱에서 엽니다
- **오프라인** — 한 번 열어두면 지하철·비행기에서도 조회·필터가 그대로 동작합니다
- **다크 모드** — 자동 / 밝게 / 어둡게
- **주소로 공유** — `#/D300/158/2024/gov` 처럼 화면 그대로 북마크·공유

## 어떻게 동작하나

빌드 도구도 서버도 없습니다. GitHub Pages에 정적 파일만 올라갑니다.

| 파일 | 역할 |
|---|---|
| `index.html` | 앱 전체. 자료 3,844회차가 gzip+base64로 안에 들어 있습니다 (154KB) |
| `sw.js` | 서비스 워커. 앱 셸·폰트·받아둔 PDF를 캐시합니다 |
| `data/`, `llms.txt` | AI·프로그램용 정적 JSON과 사용 안내 |
| `tools/refresh_data.py` | EBSi에서 새 회차를 긁어 페이로드를 갱신합니다 |
| `tools/build_api.py` | 페이로드를 `data/` JSON과 `llms.txt`로 내보냅니다 |
| `mcp/gijul_server.py` | Claude에 도구로 붙이는 MCP 서버 |
| `android/` | 앱 폴더에 담고 앱에서 여는 WebView 앱 (안드로이드) |
| `.github/workflows/refresh-data.yml` | 매월 5일 자동 실행 |

자료를 `index.html` 안에 넣어둔 덕분에, **이 파일 하나만 캐시하면 조회·필터가 네트워크 없이 전부 동작합니다.** 네트워크가 필요한 건 PDF를 받을 때뿐입니다.

PDF는 EBSi가 `Access-Control-Allow-Origin: *`를 주기 때문에 페이지가 직접 받아
`navigator.share()`로 넘길 수 있습니다. 그래서 설치형 앱에서도 노트앱으로 보내집니다.

## AI·프로그램에서 쓰기

화면용 HTML은 자료가 압축돼 있어 AI가 읽어도 소용없습니다. 같은 자료를
**정적 JSON으로도 함께 배포**합니다. 서버도 인증도 키도 필요 없습니다.

```
https://mangom72.github.io/Direct-mogo/llms.txt          AI용 사용 안내
https://mangom72.github.io/Direct-mogo/data/index.json   과목 목록과 각 과목 JSON 주소
https://mangom72.github.io/Direct-mogo/data/D300/158.json 고3 생명과학Ⅰ 전 회차
```

과목 하나가 평균 26KB라 필요한 과목만 받아 가면 됩니다. 각 회차에 문제·정답·해설
**절대 주소**가 들어 있어 경로 규칙을 몰라도 바로 열립니다.

아무 AI에게든 `llms.txt` 주소를 주면 나머지는 알아서 합니다.

### Claude에 도구로 붙이기 (MCP)

`mcp/gijul_server.py`가 위 JSON을 읽어 Claude에 도구로 노출합니다 —
`list_subjects`, `find_papers`, `site_info`.

```bash
pip install "mcp[cli]" httpx

# Claude Code
claude mcp add 기출직행 -- python3 "$PWD/mcp/gijul_server.py"
```

Claude Desktop은 `claude_desktop_config.json`에:

```json
{ "mcpServers": {
    "기출직행": { "command": "python3", "args": ["/절대/경로/mcp/gijul_server.py"] }
} }
```

붙이고 나면 이렇게 물으면 됩니다 — *"2026학년도 수능 생명과학Ⅰ 문제 찾아줘"*.
배포된 JSON을 읽으므로 저장소를 클론하지 않아도 되고, 월간 갱신도 그대로 따라옵니다.

## 안드로이드 앱 (앱 폴더에 담고 앱에서 열기)

웹에서는 저장 위치를 정할 수 없습니다 — 안드로이드 크롬에 File System Access API가
없어 다운로드 폴더로만 떨어집니다. `android/`의 WebView 앱은 그 부분만 네이티브로
처리합니다. 받은 파일은 **앱 데이터 폴더**에 회차별 하위 폴더로 들어갑니다.

```
Android/data/kr.gijul.direct/files/
  2026 7월 학평(인천) 생명과학Ⅰ/
      … 문제.pdf   … 정답.png   … 해설.pdf
```

권한을 물을 필요가 없고, 앱을 지우면 함께 정리됩니다. 대신 **안드로이드 11+에서는
다른 파일 관리자가 이 경로를 열 수 없으므로**, 앱이 목록과 열기를 직접 제공합니다 —
회차 목록 위의 **받아둔 자료** 버튼입니다. 열기는 FileProvider로 `content://` 를 넘겨
기기의 PDF 뷰어를 띄웁니다.

페이지는 `window.GijulNative`가 있을 때만 이 경로를 씁니다. **다른 OS·브라우저는 그대로**
다운로드로 저장되고, 받아둔 자료 버튼도 나타나지 않습니다.

### 문제지 읽기

문제·정답·해설은 **앱 안에서 엽니다.** WebView에는 PDF 뷰어가 없어 처음에는 기본
브라우저로 넘겼는데, 자료를 열 때마다 앱이 크롬으로 바뀌는 건 이 앱의 요점을 잃는
일이었습니다. `PdfRenderer`로 직접 그립니다 — 페이지는 `RecyclerView`로 필요한 것만
그리고(20쪽짜리를 통째로 비트맵으로 들면 메모리가 남아나지 않습니다), 확대는 다시
그리지 않고 뷰 변형으로 처리해 손가락을 따라옵니다. 정답은 PNG라 한 장으로 보여줍니다.

회차 하나가 길어야 스무 쪽 남짓이라, **열 때 전 쪽을 낮은 해상도로 한 번 훑어
둡니다** — 어디로 넘겨도 빈 종이가 없습니다. 그 위에 보고 있는 쪽만 제 해상도로
덮어쓰고, **확대하면 그 배율에 맞춰 다시 그립니다.** 밑그림 해상도는 쪽수를 보고
정합니다(고정값이면 쪽 많은 자료에서 조용히 메모리를 다 먹습니다). 메모리가
부족해지면 선명한 쪽부터 놓아주고 밑그림은 남깁니다 — 그게 빈 종이를 막는 보루입니다. **축소는 1배 아래로도** 내려가 양옆에 여백이 생기며,
그만큼 여러 쪽이 한눈에 들어옵니다. 상단에 현재 쪽(`3 / 16`)을 표시합니다.

화면에는 현재 쪽(`3 / 16`)과 배율이 뜹니다. 배율을 누르면 **폭 맞춤 ↔ 쪽 맞춤**을
오갑니다 — 문항을 읽을 때와 한 쪽을 통째로 훑을 때가 서로 다른 배율입니다.
**가리기**를 누르거나 화면을 한 번 두드리면 막대와 시스템 표시줄이 사라지고, 다시
두드리면 돌아옵니다. 뒤쪽까지 내려가면 **맨 위로** 단추가 나타납니다.

이미 받아둔 자료에 같은 파일이 있으면 그걸 씁니다. 필기 앱·인쇄로 넘길 때를 위해
화면 위의 **다른 앱** 버튼을 남겨뒀습니다. EBSi 사이트 링크처럼 자료가 아닌 주소는
그대로 브라우저 몫입니다.

앱은 사이트를 그대로 불러오므로 페이지를 고쳐도 APK를 다시 만들 필요가 없습니다.

### 앱 자체 업데이트

껍데기(WebView 바깥의 네이티브 부분)를 고칠 때만 APK가 새로 필요한데, 스토어를
거치지 않으니 알려줄 주체가 없습니다. 그래서 **명세를 사이트에 같이 올려두고 앱이
직접 읽습니다.**

```
app/latest.json        versionCode·versionName·url·size·sha256·notes
app/gijul-direct.apk   최신 릴리스 APK (이름은 늘 같습니다)
```

앱은 실행할 때 최대 6시간에 한 번 이 명세를 보고, 설치된 versionCode보다 크면
알림 막대를 띄웁니다. 누르면 받아서 시스템 설치 화면으로 넘깁니다.

설치 화면을 띄우기 **전에** 받은 파일을 직접 열어 세 가지를 확인합니다 — SHA-256이
명세와 같은지, 패키지 이름이 우리 것인지, **서명 인증서가 지금 실행 중인 앱과
같은지.** 세 번째는 안드로이드도 강제하지만 그건 설치 화면이 뜬 뒤의 일이라, 그
앞에서 먼저 거릅니다. 그래서 **서명 키가 바뀌면 기기가 업데이트를 거부합니다.**

안드로이드 8+에서는 이 앱에 "이 출처 허용"을 한 번 줘야 하며, 없으면 앱이 해당
설정 화면으로 안내합니다.

새 판본을 올리려면 `build.gradle`의 `versionCode`를 올리고:

```bash
cd android && gradle assembleRelease && cd ..
python3 tools/publish_apk.py --notes "무엇이 달라졌는지 한 줄"
```

versionCode가 늘지 않았으면 스크립트가 거부합니다. 서명 키가 CI 시크릿에 들어
있으면 `android/`를 고쳐 main에 밀 때 워크플로가 이 과정을 대신합니다.

### 빌드

Actions의 **APK 빌드** 워크플로를 수동 실행하면 artifact로 받을 수 있습니다.
직접 빌드하려면:

```bash
cd android
echo "sdk.dir=$ANDROID_HOME" > local.properties
gradle assembleDebug        # app/build/outputs/apk/debug/app-debug.apk
```

설치할 때 "출처를 알 수 없는 앱"을 허용해야 합니다.

### 릴리스 서명

릴리스 빌드는 저장소에 없는 키로 서명합니다. 키를 만들고 `android/keystore.properties`에
경로·비밀번호를 적어두면 `assembleRelease`가 그걸 씁니다 (둘 다 gitignore 대상입니다).

```bash
cd android
keytool -genkeypair -v -keystore gijul-release.jks -alias gijul \
  -keyalg RSA -keysize 4096 -validity 10000
cat > keystore.properties <<'EOF'
storeFile=gijul-release.jks
storePassword=…
keyAlias=gijul
keyPassword=…
EOF
gradle assembleRelease
```

CI에서 빌드하려면 저장소 시크릿에 `KEYSTORE_BASE64`(키를 base64로 인코딩한 값),
`KEYSTORE_PASSWORD`, `KEY_ALIAS`, `KEY_PASSWORD`를 넣습니다. 시크릿이 없으면 디버그로 빌드합니다.

**서명 키를 바꾸면 기존 앱 위에 덮어쓸 수 없습니다.** 지우고 새로 설치해야 하며 받아둔 자료도
사라집니다. 자체 업데이트도 서명이 다르면 설치 전에 스스로 멈춥니다. 키를 잃어버리면 같은
서명으로 업데이트할 방법이 영영 없으니, 저장소 밖에 따로 보관하세요.

## 자료 갱신

새 회차는 워크플로가 알아서 채웁니다. 직접 돌리려면:

```bash
pip install requests
python3 tools/refresh_data.py --dry-run   # 무엇이 늘어나는지만 확인
python3 tools/refresh_data.py             # index.html 갱신
```

기존 기록은 고치지 않고 **아직 없는 시행일만 덧붙입니다.** 수집량이 기존의 80%에
못 미치면 EBSi 구조가 바뀐 것으로 보고 파일을 건드리지 않은 채 실패합니다.

## 로컬에서 보기

```bash
python3 -m http.server 8000
```

서비스 워커는 `localhost`에서도 동작합니다. 캐시 때문에 변경이 안 보이면
개발자도구 → Application → Service Workers에서 Unregister 하세요.

## 출처와 저작권

모든 링크는 **EBSi가 공개 제공하는 파일 주소로 직접 연결**되며(로그인 불필요),
이 저장소는 어떤 파일도 저장하거나 재배포하지 않습니다.
문제지 저작권은 **한국교육과정평가원** 및 **각 시·도교육청**에 있습니다.

연도는 **시행 연도** 기준입니다. 평가원 시험의 학년도는 시행 연도 + 1이므로
(2013년 시행 = 2014학년도 6월 모평) 화면에 학년도를 함께 표기합니다.
