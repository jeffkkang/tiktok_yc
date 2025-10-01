#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   PROJECT_ID=your-gcp-project \
#   REGION=asia-northeast3 \
#   REPO=tiktokanalyzer \
#   IMAGE_TAG=api:0.1.0 \
#   SERVICE_NAME=tiktok-analyzer \
#   BUCKET_NAME=${PROJECT_ID}-tiktok-runs \
#   ./scripts/deploy-cloud-run.sh

: "${PROJECT_ID:?set PROJECT_ID}"
: "${REGION:?set REGION}"
: "${REPO:?set REPO}"
: "${IMAGE_TAG:?set IMAGE_TAG}"  # e.g., api:0.1.0
: "${SERVICE_NAME:?set SERVICE_NAME}"
: "${BUCKET_NAME:?set BUCKET_NAME}"

IMAGE_PATH="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/${IMAGE_TAG}"

echo "Enabling APIs..."
gcloud services enable run.googleapis.com artifactregistry.googleapis.com cloudbuild.googleapis.com secretmanager.googleapis.com

echo "Creating Artifact Registry repo (if not exists)..."
gcloud artifacts repositories create "${REPO}" \
  --repository-format=docker \
  --location="${REGION}" \
  --description="TikTok analyzer" || true

echo "Building and pushing image: ${IMAGE_PATH}"
gcloud builds submit --tag "${IMAGE_PATH}"

echo "Creating service account (if not exists)..."
gcloud iam service-accounts create tiktok-analyzer-sa --display-name="tiktok-analyzer" || true

echo "Creating storage bucket (if not exists): gs://${BUCKET_NAME}"
gcloud storage buckets create "gs://${BUCKET_NAME}" --location="${REGION}" || true

echo "Granting bucket permissions to service account..."
gcloud storage buckets add-iam-policy-binding "gs://${BUCKET_NAME}" \
  --member="serviceAccount:tiktok-analyzer-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role=roles/storage.objectAdmin || true

echo "Deploying Cloud Run service: ${SERVICE_NAME}"
gcloud run deploy "${SERVICE_NAME}" \
  --image "${IMAGE_PATH}" \
  --region "${REGION}" \
  --platform managed \
  --cpu 1 --memory 1Gi --timeout 900 --concurrency 1 \
  --max-instances 3 \
  --service-account "tiktok-analyzer-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
  --set-env-vars "GCS_BUCKET=${BUCKET_NAME}" \
  --no-allow-unauthenticated

echo "Done. Use 'gcloud run services describe ${SERVICE_NAME} --region ${REGION}' to view URL."

