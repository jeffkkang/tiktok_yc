# Agent Guide: Understanding and Using the Deployed TikTok Analyzer

This guide enables any agent (human or automated) to quickly understand this codebase and reliably use the Cloud Run–deployed API. Transcription (Whisper) is disabled by default; the service focuses on metadata, comments, and video download.

## 1) What This Service Does
- Input: A public TikTok video URL in the shape `https://www.tiktok.com/@USER/video/VIDEO_ID`.
- Actions: Fetch fast metadata, optionally scrape up to ~500 comments, download the MP4.
- Output: A run folder with artifacts uploaded to a Google Cloud Storage (GCS) bucket; the API returns the GCS prefix and file list.

## 2) Key Entry Points in Repo
- API server: `app/main.py`
  - Exposes `POST /analyze` and `GET /healthz`.
- Pipeline: `src/pipeline.py`
  - `analyze_url(url, ..., transcribe=False)` orchestrates metadata → comments → download.
  - Stores outputs under `runs/<uploader>_<videoId>_<YYYYMMDD_HHMMSS>/`.
- Scrapers:
  - `src/scrapers/tiktok_video_metadata_scraper.py` (fast metadata summary)
  - `src/scrapers/thirdparty_tpcs_runner.py` (comment scraper wrapper)
- Downloader: `src/downloaders/yt_dlp_downloader.py`
- Utilities: `src/utils/paths.py` (URL parsing, run dir naming)
- Container: `Dockerfile` (ffmpeg installed; no Whisper/PyTorch)

## 3) Cloud Run API Contract
- Base URL: Cloud Run service URL (e.g., `https://tiktok-analyzer-XXXXXXXX-xx.a.run.app`).
- Health check:
  - Method: GET `/healthz`
  - Response: `{ "status": "ok" }`
- Analyze:
  - Method: POST `/analyze`
  - Auth: Cloud Run OIDC Bearer token (service-to-service). For local dev, you may allow unauthenticated or omit `GCS_BUCKET` to return local run path.
  - Request JSON:
    ```json
    {
      "url": "https://www.tiktok.com/@USER/video/VIDEO_ID",
      "comments": true
    }
    ```
  - Response JSON (success):
    ```json
    {
      "status": "ok",
      "gcs_prefix": "gs://<PROJECT_ID>-tiktok-runs/runs/<run>-<ts>/",
      "files": [
        "gs://<PROJECT_ID>-tiktok-runs/runs/<run>-<ts>/@USER_video_VIDEO_ID_metadata_summary.json",
        "gs://<...>/<uploader>_<id>.mp4",
        "gs://<...>/<base>_comments.json",
        "gs://<...>/<base>_comments.jsonl"
      ]
    }
    ```
  - Response JSON (local/dev without bucket):
    ```json
    { "status": "ok", "local_run_dir": "/app/runs/<run>" }
    ```
  - Errors: HTTP 4xx/5xx with `{ "detail": "..." }` message.

## 4) Authentication (Service-to-Service)
- Acquire OIDC token for the Cloud Run URL and send as Bearer.
- Node example:
  ```js
  import {GoogleAuth} from 'google-auth-library';
  const url = 'https://tiktok-analyzer-XXXXXXXX-xx.a.run.app/analyze';
  const client = await new GoogleAuth().getIdTokenClient(url);
  const res = await client.request({
    url, method: 'POST',
    data: { url: 'https://www.tiktok.com/@USER/video/VIDEO_ID', comments: true }
  });
  ```
- Curl (developer auth):
  ```bash
  ID_TOKEN=$(gcloud auth print-identity-token)
  curl -X POST "$BASE_URL/analyze" \
    -H "Authorization: Bearer $ID_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"url":"https://www.tiktok.com/@USER/video/VIDEO_ID","comments":true}'
  ```

## 5) Environment Variables
- `GCS_BUCKET` (required in Cloud Run): Target bucket for run uploads, e.g., `<PROJECT_ID>-tiktok-runs`.
  - When unset (local dev), the API returns `local_run_dir` and does not upload.

## 6) Outputs and File Layout
- GCS prefix: `gs://<BUCKET>/runs/<run-name>-<timestamp>/`
- Typical files (presence depends on options):
  - `<uploader>_<id>.mp4` (downloaded video)
  - `@USER_video_VIDEO_ID_metadata_summary.json`
  - `<base>_comments.json`, `<base>_comments.jsonl`
  - Additional helper JSON from the pipeline as added over time

## 7) Operational Expectations
- Latency: Dominated by `yt-dlp` download time; set Cloud Run timeout to 15m.
- Concurrency: Default 1 for stability; scale out via max instances.
- Retries: Clients should implement idempotent retries on 5xx with backoff.
- Rate limits/Quotas: Governed by Cloud Run and external site behavior; avoid high parallelism against TikTok.

## 8) Local Development Workflow
- Without Cloud Run: run `uvicorn app.main:app --host 0.0.0.0 --port 8080` and POST to `/analyze`.
- Without GCS: omit `GCS_BUCKET` and read artifacts from `local_run_dir`.
- CLI path: `python -m src.pipeline --url "..." --comments` for quick testing.

## 9) Extending the Service
- Add new analysis steps:
  1. Implement logic in `src/pipeline.py` (extend `_analyze_local_mp4` or `analyze_url`).
  2. Persist outputs into the run directory.
  3. Ensure `app/main.py` uploads the new files (no change needed if you write into the same run dir).
- Add new API endpoints:
  1. Define a new route in `app/main.py` and keep I/O JSON minimal and documented.
  2. If request/response schema changes materially, bump an API version path (e.g., `/v1/analyze`).

## 10) Security and IAM
- Cloud Run service account: `tiktok-analyzer-sa@<PROJECT_ID>.iam.gserviceaccount.com` needs `roles/storage.objectAdmin` on the bucket.
- Clients: Grant `roles/run.invoker` to caller service accounts.
- Keep the service private (`--no-allow-unauthenticated`) unless testing.

## 11) Troubleshooting Quick Checks
- Health: `GET /healthz` should return `{ "status": "ok" }`.
- Logs: `gcloud logs tail --service tiktok-analyzer --region <REGION>`
- GCS: `gsutil ls -r gs://<PROJECT_ID>-tiktok-runs/runs/**`
- Common causes:
  - ffmpeg missing (not in our container)
  - TikTok page changes → update `yt-dlp` / scrapers
  - Network egress restrictions from Cloud Run env

## 12) Versioning and Change Management
- Image tags: bump `IMAGE_TAG` (e.g., `api:0.1.1`) when behavior or outputs change.
- Document output schema changes here and in `DOCS/deploy-cloud-run.md`.
- Keep breaking changes behind a new path (e.g., `/v2/...`) if necessary.

---
If additional capabilities (e.g., LLM-based video analysis) are added, follow the same pattern: write outputs into the run directory and return stable pointers (GCS URIs) from the API.
