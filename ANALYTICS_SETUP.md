# Google Tag Manager와 Analytics 연결

사이트에는 Google Tag Manager 컨테이너 `GTM-TT9XKSMX`와 공개 방문 통계 배너가 연결돼 있습니다. 서비스 계정 키는 저장소에 넣지 않습니다.

## 1. Tag Manager와 웹 데이터 스트림

Google Analytics에서 속성과 웹 데이터 스트림을 만듭니다.

- 웹사이트 URL: `https://golgong.github.io`
- 스트림 이름: `골때리는공작소`
- 속성 보고 시간대: `대한민국`
- 향상된 측정의 외부 링크 클릭 수집은 끕니다.
- 광고 연결, Google Signals, 사용자 제공 데이터 수집은 사용하지 않습니다.

Tag Manager 컨테이너 `GTM-TT9XKSMX`에서 Google 태그를 만들고 웹 스트림의 `G-` 측정 ID를 연결한 뒤 게시합니다. 사이트는 방문자가 분석을 허용한 뒤에만 이 컨테이너를 불러옵니다. 향상된 측정은 전부 끄고 기본 페이지 조회만 사용합니다.

사이트를 다시 만들고 검증하는 명령은 다음과 같습니다.

```powershell
python .\tools\build_site.py
python .\tools\validate_site.py
```

## 2. 공개 통계 자동 갱신

`.github/workflows/update-visitor-stats.yml`은 매일 오전 6시 17분경 최근 방문 통계를 갱신합니다. 당일과 전일은 빼고, 2일 전까지의 최근 7일을 집계합니다.

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

홈에는 Google Analytics의 `activeUsers`로 측정된 최근 7일 분석 허용 활성 사용자와 직전 7일 대비 변화만 표시합니다. 이는 실제 사람 수가 아니며, 한 사람이 여러 기기나 브라우저를 사용하면 서로 다르게 집계될 수 있습니다. 페이지별 방문, 유입어, 위치, 기기, 방문 시각은 공개하지 않습니다. 최근 7일 분석 허용 활성 사용자가 5명 미만이면 정확한 숫자와 추이를 숨깁니다.

## 4. 인증 제한

Workload Identity Federation의 GitHub 주체 조건은 저장소 `golgong/golgong.github.io`와 브랜치 `refs/heads/main`으로 제한합니다.
