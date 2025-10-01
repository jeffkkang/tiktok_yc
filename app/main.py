#!/usr/bin/env python3

import os
import time
import glob
from typing import Optional, List

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

try:
    from src.pipeline import analyze_url
except ModuleNotFoundError:
    from pipeline import analyze_url  # type: ignore


GCS_BUCKET = os.getenv("GCS_BUCKET", "")

app = FastAPI(title="TikTok Analyzer API", version="1.0.0")


class AnalyzeRequest(BaseModel):
    url: str
    comments: bool = True


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


def _latest_run_dir(base: str = None) -> Optional[str]:
    base = base or os.path.join(os.getcwd(), "runs")
    if not os.path.isdir(base):
        return None
    cands = [d for d in glob.glob(os.path.join(base, "*")) if os.path.isdir(d)]
    if not cands:
        return None
    return max(cands, key=os.path.getmtime)


def _upload_dir_to_gcs(local_dir: str, bucket_name: str, prefix: str) -> List[str]:
    # Lazy import to allow local runs without gcloud deps
    from google.cloud import storage  # type: ignore

    client = storage.Client()
    bucket = client.bucket(bucket_name)
    uploaded = []
    for root, _, files in os.walk(local_dir):
        for f in files:
            lp = os.path.join(root, f)
            rel = os.path.relpath(lp, local_dir)
            blob = bucket.blob(f"{prefix}/{rel}")
            blob.upload_from_filename(lp)
            uploaded.append(f"gs://{bucket_name}/{prefix}/{rel}")
    return uploaded


@app.post("/analyze")
def analyze(req: AnalyzeRequest):
    try:
        analyze_url(
            req.url,
            do_comments=req.comments,
            transcribe=False,  # transcription disabled by default
            meta_fast=True,
            skip_metadata=False,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"pipeline failed: {e}")

    run_dir = _latest_run_dir()
    if not run_dir:
        raise HTTPException(status_code=500, detail="run directory not found")

    if not GCS_BUCKET:
        # local/dev mode: return local path without uploading
        return {"status": "ok", "local_run_dir": run_dir}

    stamp = int(time.time())
    prefix = f"runs/{os.path.basename(run_dir)}-{stamp}"
    try:
        uploaded = _upload_dir_to_gcs(run_dir, GCS_BUCKET, prefix)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"gcs upload failed: {e}")

    return {
        "status": "ok",
        "gcs_prefix": f"gs://{GCS_BUCKET}/{prefix}/",
        "files": uploaded,
    }


@app.post("/metadata-only")
def analyze_metadata_only(req: AnalyzeRequest):
    """
    Extract only metadata from TikTok video without downloading video file.
    Optimized for lightweight metadata extraction.
    """
    try:
        analyze_url(
            req.url,
            do_comments=False,  # Skip comments for metadata-only
            transcribe=False,   # No transcription
            meta_fast=True,     # Fast metadata extraction
            skip_metadata=False,
            video_download=False,  # Skip video download
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"metadata extraction failed: {e}")

    run_dir = _latest_run_dir()
    if not run_dir:
        raise HTTPException(status_code=500, detail="run directory not found")

    if not GCS_BUCKET:
        # local/dev mode: return local path without uploading
        return {"status": "ok", "local_run_dir": run_dir}

    stamp = int(time.time())
    prefix = f"metadata/{os.path.basename(run_dir)}-{stamp}"
    
    try:
        # Upload only metadata files
        uploaded = _upload_metadata_only_to_gcs(run_dir, GCS_BUCKET, prefix)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"gcs upload failed: {e}")

    return {
        "status": "ok",
        "gcs_prefix": f"gs://{GCS_BUCKET}/{prefix}/",
        "files": uploaded,
    }


def _upload_metadata_only_to_gcs(local_dir: str, bucket_name: str, prefix: str) -> List[str]:
    """Upload only metadata files to GCS"""
    from google.cloud import storage  # type: ignore

    client = storage.Client()
    bucket = client.bucket(bucket_name)
    uploaded = []
    
    # Only upload specific metadata files
    metadata_patterns = ["*metadata*.json", "*info*.json", "*summary*.json"]
    
    for root, _, files in os.walk(local_dir):
        for f in files:
            # Check if file matches metadata patterns
            if any(pattern.replace("*", "") in f.lower() for pattern in metadata_patterns):
                lp = os.path.join(root, f)
                rel = os.path.relpath(lp, local_dir)
                blob = bucket.blob(f"{prefix}/{rel}")
                blob.upload_from_filename(lp)
                uploaded.append(f"gs://{bucket_name}/{prefix}/{rel}")
    
    return uploaded


@app.post("/comments-only")
def analyze_comments_only(req: AnalyzeRequest):
    """
    Extract only comments from TikTok video without downloading video file or metadata.
    Optimized for lightweight comment extraction.
    """
    try:
        analyze_url(
            req.url,
            do_comments=True,   # Only extract comments
            transcribe=False,   # No transcription
            meta_fast=False,    # Skip metadata
            skip_metadata=True,  # Skip metadata entirely
            video_download=False,  # Skip video download
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"comment extraction failed: {e}")

    run_dir = _latest_run_dir()
    if not run_dir:
        raise HTTPException(status_code=500, detail="run directory not found")

    if not GCS_BUCKET:
        # local/dev mode: return local path without uploading
        return {"status": "ok", "local_run_dir": run_dir}

    stamp = int(time.time())
    prefix = f"comments/{os.path.basename(run_dir)}-{stamp}"
    
    try:
        # Upload only comment files
        uploaded = _upload_comments_only_to_gcs(run_dir, GCS_BUCKET, prefix)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"gcs upload failed: {e}")

    return {
        "status": "ok",
        "gcs_prefix": f"gs://{GCS_BUCKET}/{prefix}/",
        "files": uploaded,
    }


def _upload_comments_only_to_gcs(local_dir: str, bucket_name: str, prefix: str) -> List[str]:
    """Upload only comment files to GCS"""
    from google.cloud import storage  # type: ignore

    client = storage.Client()
    bucket = client.bucket(bucket_name)
    uploaded = []
    
    # Only upload comment-related files
    comment_patterns = ["*comment*.json", "*comments*.json", "*comment*.csv"]
    
    for root, _, files in os.walk(local_dir):
        for f in files:
            # Check if file matches comment patterns
            if any(pattern.replace("*", "") in f.lower() for pattern in comment_patterns):
                lp = os.path.join(root, f)
                rel = os.path.relpath(lp, local_dir)
                blob = bucket.blob(f"{prefix}/{rel}")
                blob.upload_from_filename(lp)
                uploaded.append(f"gs://{bucket_name}/{prefix}/{rel}")
    
    return uploaded

@app.post("/video-only")
def analyze_video_only(req: AnalyzeRequest):
    """
    Download only TikTok video without extracting metadata or comments.
    Optimized for lightweight video download.
    """
    try:
        analyze_url(
            req.url,
            do_comments=False,   # Skip comments
            transcribe=False,    # No transcription
            meta_fast=False,     # Skip metadata
            skip_metadata=True,  # Skip metadata entirely
            extract_audio_only=False,  # Don't extract audio
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"video download failed: {e}")

    run_dir = _latest_run_dir()
    if not run_dir:
        raise HTTPException(status_code=500, detail="run directory not found")

    if not GCS_BUCKET:
        # local/dev mode: return local path without uploading
        return {"status": "ok", "local_run_dir": run_dir}

    stamp = int(time.time())
    prefix = f"videos/{os.path.basename(run_dir)}-{stamp}"
    
    try:
        # Upload only video files
        uploaded = _upload_video_only_to_gcs(run_dir, GCS_BUCKET, prefix)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"gcs upload failed: {e}")

    return {
        "status": "ok",
        "gcs_prefix": f"gs://{GCS_BUCKET}/{prefix}/",
        "files": uploaded,
    }


def _upload_video_only_to_gcs(local_dir: str, bucket_name: str, prefix: str) -> List[str]:
    """Upload only video files to GCS"""
    from google.cloud import storage  # type: ignore

    client = storage.Client()
    bucket = client.bucket(bucket_name)
    uploaded = []
    
    # Only upload video files
    video_patterns = ["*.mp4", "*.webm", "*.mov", "*.avi", "*.mkv"]
    
    for root, _, files in os.walk(local_dir):
        for f in files:
            # Check if file matches video patterns
            if any(f.lower().endswith(pattern.replace("*", "")) for pattern in video_patterns):
                lp = os.path.join(root, f)
                rel = os.path.relpath(lp, local_dir)
                blob = bucket.blob(f"{prefix}/{rel}")
                blob.upload_from_filename(lp)
                uploaded.append(f"gs://{bucket_name}/{prefix}/{rel}")
    
    return uploaded
