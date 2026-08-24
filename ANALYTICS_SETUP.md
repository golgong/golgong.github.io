# Google Analytics 연결

사이트에는 Google Analytics 측정 ID `G-569GH22CPH`와 공개 방문 통계 배너가 연결돼 있습니다. 서비스 계정 키는 저장소에 넣지 않습니다.

## 1. 웹 데이터 스트림

Google Analytics에서 속성과 웹 데이터 스트림을 만듭니다.

- 웹사이트 URL: `https://golgong.github.io`
- 스트림 이름: `골때리는공작소`
- 속성 보고 시간대: `대한민국`
- 향상된 측정의 외부 링크 클릭 수집은 끕니다.
- 광고 연결, Google Signals, 사용자 제공 데이터 수집은 사용하지 않습니다.

웹 스트림의 측정 ID `G-569GH22CPH`를 사이트에 직접 연결했습니다. 사이트는 방문자가 분석을 Google 태그 파일은 페이지를 열 때 불러오고, 허용한 뒤에만 방문 분석 이벤트를 보냅니다. 향상된 측정은 전부 끄고 기본 페이지 조회만 사용합니다.

사이트를 다시 만들고 검증하는 명령은 다음과 같습니다.

```powershell
python .\tools\build_site.py
python .\tools\validate_site.py
```

## 2. 공개 통계 자동 갱신

`.github/workflows/update-visitor-stats.yml`은 매일 오전 6시 17분경 전날의 방문자·방문 횟수·페이지 조회 수와 최근 7일의 일별 방문자 추이를 갱신합니다.

Google Cloud에서 Analytics Data API를 켜고 GitHub Actions용 Workload Identity Federation과 서비스 계정을 만듭니다. 서비스 계정 이메일에는 GA4 속성의 `Viewer` 권한만 줍니다.

GitHub 저장소의 Actions variables에 아래 세 값을 등록합니다.

| 이름 | 값 |
| --- | --- |
| `GA4_PROPERTY_ID` | GA4 속성의 숫자 ID |
| `GCP_WORKLOAD_IDENTITY_PROVIDER` | Workload Identity Provider 전체 경로 |
| `GCP_SERVICE_ACCOUNT` | 읽기 전용 서비스 계정 이메일 |

장기 서비스 계정 JSON 키와 개인 Google 계정 정보는 GitHub Secrets, 파일, HTML에 넣지 않습니다.

설정 후 Actions의 `방문 통계 갱신`을 한 번 직접 실행합니다. GA4는 설치 전 방문을 소급해서 보여 주지 않으며, 일반 보고서 반영에는 24~48시간이 걸릴 수 있습니다.

## 3. 공개 범위

홈에는 Google Analytics의 `activeUsers`로 측정된 전날 방문자 수, `sessions` 방문 횟수, `screenPageViews` 페이지 조회 수와 최근 7일의 일별 방문자 추이를 표시합니다. 이는 실제 사람 수가 아니며, 한 사람이 여러 기기나 브라우저를 사용하면 서로 다르게 집계될 수 있습니다. 페이지별 방문, 유입어, 위치, 기기, 방문 시각은 공개하지 않습니다. GA4 처리 지연으로 전날 수치는 다음 갱신 때 보정될 수 있습니다.

## 4. 인증 제한

Workload Identity Federation의 GitHub 주체 조건은 저장소 `golgong/golgong.github.io`와 브랜치 `refs/heads/main`으로 제한합니다.
