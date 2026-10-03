# 기록 동기화 연결

10.1의 동기화는 Firebase Authentication의 Google 계정과 Cloud Firestore를 사용한다.
2026-10-03 기준 `sync/config.json`은 `enabled:true`이며 운영 프로젝트는
`direct-mogo`, Standard Firestore `(default)` / `asia-northeast3`다.
`sync/config.json`의 `enabled:false` 동안에는 기존 기록·백업 동작을 유지하고 SDK도
받지 않는다. 프로젝트 연결·규칙 배포·전송 검증이 끝난 뒤 활성화한다. 실제 기기의 Google 로그인은 별도로 확인한다.

## 프로젝트 준비

1. Firebase 콘솔에서 프로젝트를 만든다. Analytics는 선택 사항이고 동기화에 필요하지 않다.
2. Authentication의 로그인 제공업체에서 Google을 활성화하고 지원 이메일을 지정한다.
3. Firestore Database를 Standard edition의 프로덕션 모드로 만든다. 가까운 리전을 선택한다. 데이터베이스
   위치는 나중에 쉽게 바꿀 수 없으므로 생성 전에 확인한다.
4. 웹 앱을 등록하고 프로젝트 설정의 firebaseConfig를 복사한다. Authentication의
   승인 도메인에 `mangom72.github.io`를 등록한다. 로컬 기기 시험은 `localhost`도
   명시적으로 등록한다.
5. Android 앱을 `kr.gijul.direct`로 등록하고 기존 릴리스 인증서 SHA-1
   `e75911e46988d7d44bb36e33ba832d240e79b919`과 SHA-256
   `54370ed90c11e53dbc7d3cc05558f49dd111bd6578e433850d6e83622cfd10c1`을 등록한다.
   디버그 계정 시험은 디버그 인증서 지문을 추가해야 한다. 키 파일은 공유하지 않는다.
6. Google 로그인용 **웹** OAuth client ID를 복사한다. Android client ID와 다르다.
7. `sync/firestore.rules`를 콘솔의 Firestore 규칙에 배포한다. CLI가 준비된 경우
   `npx -y firebase-tools@latest deploy --only auth,firestore:rules --config sync/firebase.json --project PROJECT_ID`.
   테스트 모드의 공개 읽기·쓰기 규칙은 사용하지 않는다.
8. `sync/config.json`의 firebase에 웹 설정을 넣고 googleWebClientId를 채운다.
   프로젝트 ID·API key·app ID·OAuth client ID는 클라이언트용 공개 설정이다.
   서비스 계정 키·OAuth client secret은 받거나 정적 사이트에 넣지 않는다.
9. 규칙 컴파일·에뮬레이터 권한 시험·실제 SDK 전송 시험을 확인하고 실제 프로젝트에
   규칙과 Auth 설정을 배포한 뒤 enabled를 true로 배포한다. 실제 Google 계정의
   브라우저/Android 로그인·두 기기 시험 여부는 별도로 명시한다.

## 데이터와 전달

회차별 푼 날·시간·점수·오답, 내 과목·테마를 각각 변경 항목으로 만든다. Firestore
경로는 `users/{Firebase uid}/events/{UUID}`이다. 이벤트는 생성 후 수정·삭제하지
않고 재전송 때도 같은 UUID를 쓴다. IndexedDB의 읽기/쓰기 트랜잭션에 항목 값과
전송 대기 이벤트를 함께 보관한다. UI 변경은 먼저 localStorage의 작은 변경 의도로
남기고, 저널 트랜잭션의 receipt로 재시작 시 중복 적용을 막는다. 서버 트랜잭션에서
기존 UUID의 내용이 같으면 재전송을 완료하고, 없는 이벤트만 만든다. 서버 쓰기나
기존 이벤트 확인이 끝난 뒤에만 대기를 지운다. 이벤트의 receivedAt은 서버 시각이며
순서 판정에는 쓰지 않는다. 적용한 receivedAt 체크포인트를 저널과 함께 저장하여
다음 연결은 경계 시각부터 받는다. 경계와 같은 시각의 이벤트는 중복으로 받아도
안전하다. 잘못된 payload는 격리하며 다른 정상 변경의 수신을 막지 않는다.
오프라인에서 전송이 끝났다고 표시하지 않으며 실패한 전송을 다시 시도한다.

삭제는 null 값을 가진 이벤트로 남긴다. 다른 기기의 오래된 백업을 처음 연결할 때
클라우드에 이미 있는 값·삭제 이력은 덮지 않고 없는 항목만 채운다. 서로 다른
회차·항목의 변경은 독립적으로 합쳐진다. 같은 항목의 동시 편집은 논리 시계와
UUID 순서로 결정하여 두 기기가 같은 결과로 수렴한다. 이전 이벤트는 서버에
남지만 아직 버전 선택 복원 UI는 없다. 마지막 저장 시각으로 비교하지 않으므로
기기 시계가 틀렸다고 변경 순서가 뒤집히지는 않는다.

파일 백업 v1·기존 localStorage 키와 네이티브 setSolved payload는 유지한다.
첫 연결 전 전체 파일 백업 사본을 `gijul.sync.before.v1`에 남긴다. 백업 화면에서
이 사본을 복구할 수 있으며 모르는 과목의 풀이 기록도 유지한다. 기기 기록의 초기
등록은 클라우드에 없는 항목만 대상으로 하며 기존 값과 삭제 이력을 덮지 않는다.
네이티브 Google 로그인은 Credential Manager를 사용하고 Firebase가 ID 토큰을
검증한다. 구형 앱은 앱 업데이트 안내를 표시하며 WebView 안에서 Google 로그인
페이지를 열지 않는다.

한 기기의 기록이 다른 계정으로 조용히 전송되지 않도록 저널을 최초 계정에 묶는다.
로그아웃 후에도 기존 계정의 대기 기록은 보존한다. 다른 계정으로 변경하는 기능은
이번 버전에 제공하지 않는다. 로그아웃은 서버 기록 삭제가 아니다. 로그아웃 중 변경도 기존 계정의 저널에
남을 수 있으며 같은 계정에 다시 연결하면 전송한다. 현재 클라우드 기록 삭제 UI는
없다. 보관·삭제 요청 안내는 [PRIVACY.md](../PRIVACY.md)를 따른다.

Firebase가 연결된 앱은 기존 SAF 자동쓰기·읽기 합치기를 멈춘다. Drive는 별도
파일 내보내기/가져오기 용도로 남긴다. 기존 자동백업 파일·내부 복구 사본은
지우지 않는다. 로그아웃해도 구형 자동 백업을 자동으로 재개하지 않는다.
새 동기화가 켜지지 않은 기기는 기존 방식으로 계속 사용할 수
있으므로 두 기기 모두 업데이트하고 같은 계정으로 연결해야 한다.

## 검증

`python3 tests/test_sync.py`는 실제 IndexedDB에서 실패 후 재시작·서버 확인 후 ACK·
동일 이벤트 재전송·서로 다른 항목 병합·삭제 재생 방지·같은 항목 동시 변경 수렴·
계정 분리를 검증한다. 서버 어댑터를 대신한 브라우저 시험은 실제 Google 계정,
실제 Firebase 규칙 배포와 클라우드 전송을 검증한 것으로 취급하지 않는다.

SDK는 `sync/vendor/source.json`의 공식 gstatic 12.19.0 URL과 SHA-256으로 고정한다.
직접 빌드하거나 새 프레임워크를 도입하지 않는다. 로그에 ID 토큰을 남기지 않는다.

실제 SDK 통신과 보안 규칙은 운영 데이터를 사용하지 않는 demo 프로젝트의
Auth/Firestore 에뮬레이터에서 확인한다. `tests/firestore_rules.cjs`는 계정별 접근,
불변 이력, 타입·크기·서버 시각을 검증하고 `tests/firestore_transport.py`는 네트워크
단절, 재전송, 두 브라우저 연결, 서버 체크포인트 수신을 검증한다.

에뮬레이터는 Java 21 이상을 선택하고, 저장소의 고정 Python 시험 환경을 활성화한다.
Node 의존성은 시험용 경로에만 설치하며 웹 빌드에는 npm을 쓰지 않는다.

```sh
npm install --prefix .git/codex-firebase-tests --no-save firebase@12.19.0 @firebase/rules-unit-testing@5.0.2
export NODE_PATH="$PWD/.git/codex-firebase-tests/node_modules"
npx -y firebase-tools@latest emulators:exec --only auth,firestore --project demo-gijul-sync --config sync/firebase.json 'node tests/firestore_rules.cjs && python3 tests/firestore_transport.py'
```

보안 규칙은 사용자만 읽고 자기 UID 경로에만 쓸 수 있는 제한된 초기 규칙이다.
JSON payload의 내부 값은 클라이언트에서 검증한다. 이벤트는 지우지 않으므로 사용량에
따라 보관·압축 정책을 후속 검토한다. 운영 데이터의 삭제나 공개 접근을 허용하지 않는다.

현재 프로젝트는 `direct-mogo`, Standard / `asia-northeast3`다. 웹·Android 앱 등록,
기존 릴리스 서명 SHA-1/SHA-256, Google 로그인 제공업체, 사이트 승인 도메인,
Firestore 규칙 배포를 확인했다. Android 설정이 반환한 웹 OAuth client ID도
`sync/config.json`과 일치한다. 실제 Google 로그인 화면까지의 웹 smoke 시험은
통과했으며 계정 선택 이후의 로그인과 실제 Android 기기 로그인은 별도 확인 대상이다.
Analytics SDK는 사용하지 않는다.
