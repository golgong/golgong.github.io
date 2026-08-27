# Google Analytics 연결

사이트에는 Google Analytics 측정 ID `G-569GH22CPH`와 공개 방문 통계 배너가 연결돼 있습니다. 서비스 계정 키는 저장소에 넣지 않습니다.

## 1. 웹 데이터 스트림

Google Analytics에서 속성과 웹 데이터 스트림을 만듭니다.

- 웹사이트 URL: `https://golgong.github.io`
- 스트림 이름: `골때리는공작소`
- 속성 보고 시간대: `대한민국`
- 향상된 측정의 외부 링크 클릭 수집은 끕니다.
- 광고 연결, Google Signals, 사용자 제공 데이터 수집은 사용하지 않습니다.

웹 스트림의 측정 ID `G-569GH22CPH`를 사이트에 직접 연결했습니다. Google 태그 파일은 페이지를 열 때 불러오되, 방문자가 분석을 허용한 뒤에만 방문 분석 이벤트를 보냅니다. 향상된 측정은 전부 끄고 기본 페이지 조회만 사용합니다.

사이트를 다시 만들고 검증하는 명령은 다음과 같습니다.

```powershell
python .\tools\build_site.py
python .\tools\validate_site.py
```

## 2. 공개 통계 동적 조회

사이트는 `data/visitor-api.json`에 기록된 Cloud Run API에서 공개용 집계 결과를 읽습니다. 브라우저는 페이지를 연 직후 조회하고, 페이지가 보이는 동안 10분마다 새로 확인합니다. API는 GA4를 30분 동안 캐시하므로 통계 갱신을 위해 저장소에 새 커밋을 만들지 않습니다.

Cloud Run 서비스는 전용 서비스 계정으로 실행하며, 그 계정에는 GA4 속성의 `Viewer` 권한만 줍니다. JSON 키나 개인 Google 계정 정보는 저장소, HTML, Cloud Run 환경 변수에 넣지 않습니다.

배포에는 `services/visitor-stats-api/deploy-cloud-shell.sh`를 사용합니다. 필요한 값은 Cloud Shell 세션에서만 지정합니다.

```bash
export PROJECT_ID="chrome-inkwell-416005"
export GA4_PROPERTY_ID="551051297"
bash services/visitor-stats-api/deploy-cloud-shell.sh
```

API가 일시적으로 응답하지 않으면 사이트는 `data/visitor-stats.json`에 보관한 마지막 정적 집계를 표시하고, 저장 데이터임을 화면에 알립니다.

## 3. 공개 범위

홈에는 오늘 방문자·방문 횟수·페이지 조회 수와 최근 7일의 작은 추이를 표시합니다. `/stats/`에서는 현재 30분, 오늘, 어제, 최근 7일, 최근 30일 집계와 30일 추이, 공개 페이지별 방문자·조회 수를 확인할 수 있습니다.

방문자는 Google Analytics의 `activeUsers`이며 실제 사람 수와 완전히 같지는 않습니다. 한 사람이 여러 기기나 브라우저를 사용하면 서로 다르게 집계될 수 있고, 방문 분석에 동의한 이용자만 포함됩니다. 유입어, 위치, 기기, 개인 식별자와 개별 방문 시각은 공개하지 않습니다. GA4 처리 지연으로 당일 수치는 나중에 보정될 수 있습니다.

## 4. API 제한

공개 API는 서버가 정한 기간과 지표만 조회하며 요청자가 기간, 측정기준, 필터를 바꿀 수 없습니다. 응답에는 집계값만 포함하고, CORS 허용 출처는 `https://golgong.github.io`로 제한합니다. Cloud Run 실행 계정은 GA4 속성 뷰어 외의 Analytics 권한을 갖지 않습니다.
