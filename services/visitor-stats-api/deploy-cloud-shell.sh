#!/usr/bin/env bash
set -euo pipefail

: "${PROJECT_ID:?PROJECT_ID is required}"
: "${GA4_PROPERTY_ID:?GA4_PROPERTY_ID is required}"
[[ "$GA4_PROPERTY_ID" =~ ^[0-9]+$ ]] || { echo "GA4_PROPERTY_ID must be numeric" >&2; exit 2; }

REGION="asia-northeast3"
SERVICE="golgong-visitor-stats"
RUNTIME_SA_NAME="golgong-visitor-stats"
RUNTIME_SA="${RUNTIME_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

gcloud config set project "$PROJECT_ID"
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  analyticsdata.googleapis.com

if ! gcloud iam service-accounts describe "$RUNTIME_SA" >/dev/null 2>&1; then
  gcloud iam service-accounts create "$RUNTIME_SA_NAME" \
    --display-name="Golgong visitor statistics reader"
  echo
  echo "GA4 속성 액세스 관리에서 아래 계정을 뷰어로 추가한 뒤 이 스크립트를 다시 실행하십시오."
  echo "$RUNTIME_SA"
  exit 3
fi

PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role="roles/run.builder" \
  --quiet >/dev/null

gcloud run deploy "$SERVICE" \
  --source "$SCRIPT_DIR" \
  --region "$REGION" \
  --service-account "$RUNTIME_SA" \
  --allow-unauthenticated \
  --min-instances=0 \
  --max-instances=1 \
  --cpu=1 \
  --memory=256Mi \
  --timeout=30 \
  --concurrency=20 \
  --set-env-vars="GA4_PROPERTY_ID=${GA4_PROPERTY_ID},ALLOWED_ORIGIN=https://golgong.github.io,CACHE_TTL_SECONDS=1800"

SERVICE_URL="$(gcloud run services describe "$SERVICE" --region "$REGION" --format='value(status.url)')"
echo "Health: ${SERVICE_URL}/v1/health"
echo "Stats:  ${SERVICE_URL}/v1/visitor-stats"
