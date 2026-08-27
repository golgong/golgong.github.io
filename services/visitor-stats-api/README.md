# Visitor statistics API

GitHub Pages가 GA4의 합산 방문 통계를 커밋 없이 읽기 위한 Cloud Run 서비스입니다.

## 공개 범위

- 분석을 허용한 오늘·어제·최근 7일·최근 30일의 활성 사용자, 방문, 페이지 조회
- 현재 30분 활성 사용자
- 최근 30일 일별 합산 추이
- 최근 30일 공개 페이지 상위 10개의 합산 방문자·페이지 조회

위치, 기기, 유입어, 개별 방문 시각, 사용자 식별 정보는 조회하거나 반환하지 않습니다. 클라이언트가 기간·지표·페이지를 바꾸는 쿼리 파라미터도 허용하지 않습니다.

## 필요한 설정

1. 결제가 연결된 Google Cloud 프로젝트
2. 숫자형 GA4 속성 ID
3. 전용 Cloud Run 서비스 계정
4. GA4 관리의 `속성 액세스 관리`에서 전용 서비스 계정에 부여한 `뷰어` 권한
5. GA4 속성 시간대 `대한민국 표준시`

서비스 계정 JSON 키는 만들지 않습니다. Cloud Run 서비스 ID의 Application Default Credentials를 사용합니다.

## 환경 변수

- `GA4_PROPERTY_ID`: 숫자형 GA4 속성 ID
- `ALLOWED_ORIGIN`: 기본값 `https://golgong.github.io`
- `CACHE_TTL_SECONDS`: 기본값 `1800`, 허용 범위 60~3600

## 로컬 시험

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python -m unittest -v test_main.py
```

실제 GA4 호출은 Cloud Run 배포 후 확인합니다. `/healthz`는 인증 설정과 무관하게 서비스 프로세스만 확인하고, `/v1/visitor-stats`가 정상이어야 실제 연결이 끝난 것입니다.

## 배포

Cloud Shell에서 `PROJECT_ID`와 `GA4_PROPERTY_ID`를 설정한 뒤 다음을 실행합니다.

```bash
export PROJECT_ID='실제 GCP 프로젝트 ID'
export GA4_PROPERTY_ID='숫자형 GA4 속성 ID'
bash deploy-cloud-shell.sh
```

스크립트가 출력한 서비스 계정 이메일을 GA4 속성의 뷰어로 추가한 뒤, 같은 명령을 다시 실행하면 Cloud Run을 배포합니다. 출력된 URL 뒤에 `/v1/visitor-stats`를 붙여 `data/visitor-api.json`의 `endpoint`에 한 번 저장합니다.

