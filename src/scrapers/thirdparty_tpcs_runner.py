#!/usr/bin/env python3

import os
import sys
import time
import glob
import json
import argparse
import subprocess
from typing import Optional

# Flexible import of project utils
try:
    from src.utils.paths import parse_tiktok_url
    from src.scrapers.comments_ingest import ingest as ingest_comments
except ModuleNotFoundError:
    THIS_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.abspath(os.path.join(THIS_DIR, os.pardir, os.pardir))
    if PROJECT_ROOT not in sys.path:
        sys.path.insert(0, PROJECT_ROOT)
    from src.utils.paths import parse_tiktok_url
    from src.scrapers.comments_ingest import ingest as ingest_comments


def _latest_json(dirpath: str) -> Optional[str]:
    files = sorted(glob.glob(os.path.join(dirpath, "*.json")), key=os.path.getmtime, reverse=True)
    return files[0] if files else None


def run_tpcs(url_or_id: str, size: int, out_dir: str) -> str:
    """Run thirdparty tiktok-comment-scrapper and ingest results into our runs folder.

    Returns the path to the normalized JSON summary in out_dir.
    """
    thirdparty_root = os.path.join(os.getcwd(), "thirdparty", "tiktok-comment-scrapper")
    tpcs_main = os.path.join(thirdparty_root, "main.py")
    tpcs_data = os.path.join(thirdparty_root, "data")
    os.makedirs(tpcs_data, exist_ok=True)

    # Invoke the third-party scraper
    # Extract aweme id if a full URL is provided
    uploader, vid = parse_tiktok_url(url_or_id) if url_or_id.startswith("http") else ("", None)
    aweme_id = vid or url_or_id
    # Ensure output path ends with separator for third-party concatenation
    output_arg = tpcs_data if tpcs_data.endswith(os.sep) else tpcs_data + os.sep
    cmd = [sys.executable, tpcs_main, f"--aweme_id={aweme_id}", f"--output={output_arg}"]
    print("[runner] invoking:", " ".join(cmd))
    subprocess.run(cmd, check=True)

    # Determine produced JSON path
    if aweme_id:
        candidate = os.path.join(tpcs_data, f"{aweme_id}.json")
        json_path = candidate if os.path.isfile(candidate) else _latest_json(tpcs_data)
    else:
        json_path = _latest_json(tpcs_data)
    if not json_path:
        raise FileNotFoundError("Could not locate output JSON from third-party scraper")

    # Ensure url (for metadata)
    final_url = url_or_id
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            payload = json.load(f)
            final_url = payload.get("video_url") or url_or_id
    except Exception:
        pass

    # Ingest into our schema in out_dir
    return ingest_comments(json_path, final_url, out_dir, limit=size if size else 0)


def main():
    p = argparse.ArgumentParser(description="Run third-party TikTok comment scraper and ingest results")
    p.add_argument("url", help="TikTok video URL or ID")
    p.add_argument("--out", required=True, help="Output runs directory")
    p.add_argument("--size", type=int, default=50, help="Maximum number of comments to fetch (default 50)")
    args = p.parse_args()

    out = run_tpcs(args.url, args.size, args.out)
    print("Normalized comments ->", out)


if __name__ == "__main__":
    main()
