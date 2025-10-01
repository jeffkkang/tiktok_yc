#!/usr/bin/env python3

import os
import time
import argparse
import asyncio
from typing import Optional

try:
    from src.scrapers.tiktok_video_metadata_scraper import TiktokVideoMetadataScraper
    from src.scrapers.thirdparty_tpcs_runner import run_tpcs as run_api_comments
    from src.downloaders.yt_dlp_downloader import YTDLPDownloader
    from src.utils.paths import parse_tiktok_url, make_run_dir
except ModuleNotFoundError:
    from scrapers.tiktok_video_metadata_scraper import TiktokVideoMetadataScraper
    from scrapers.thirdparty_tpcs_runner import run_tpcs as run_api_comments
    from downloaders.yt_dlp_downloader import YTDLPDownloader
    from utils.paths import parse_tiktok_url, make_run_dir


def _latest_downloaded_mp4(since_ts: float, timeout: int = 120, pattern: Optional[str] = None) -> Optional[str]:
    """
    Poll the user's Downloads directory for a new .mp4 file created after `since_ts`.
    Optionally filter by substring `pattern` in filename.
    Returns the newest matching path or None if not found in time.
    """
    downloads_dir = os.path.expanduser("~/Downloads")
    deadline = time.time() + timeout
    latest_path = None

    while time.time() < deadline:
        try:
            candidates = []
            for name in os.listdir(downloads_dir):
                if not name.lower().endswith(".mp4"):
                    continue
                if pattern and pattern not in name:
                    continue
                path = os.path.join(downloads_dir, name)
                try:
                    stat = os.stat(path)
                except FileNotFoundError:
                    continue
                # Consider files modified after the download action started
                if stat.st_mtime >= since_ts:
                    candidates.append((stat.st_mtime, path))
            if candidates:
                # newest by mtime
                latest_path = sorted(candidates, key=lambda x: x[0], reverse=True)[0][1]
                # Heuristic: ensure the file is no longer growing (settled)
                size1 = os.path.getsize(latest_path)
                time.sleep(1.5)
                size2 = os.path.getsize(latest_path)
                if size1 == size2 and size2 > 0:
                    return latest_path
        except FileNotFoundError:
            pass
        time.sleep(2)
    return latest_path


def analyze_url(
    url: str,
    do_face: bool = False,
    do_objects: bool = False,
    do_nlp: bool = False,
    transcribe: bool = False,
    do_comments: bool = False,
    meta_fast: bool = False,
    skip_metadata: bool = False,
    extract_audio_only: bool = False,
    browser: str = "pyppeteer",
    driver: str = "firefox",
) -> None:
    """Full pipeline for a TikTok URL: metadata -> download -> transcribe -> CV -> NLP."""
    base_runs = os.path.join(os.getcwd(), "runs")
    uploader, vid = parse_tiktok_url(url)
    run_dir = make_run_dir(base_runs, uploader, vid)
    print(f"Run directory: {run_dir}")

    # 1) Metadata summary (saved to run_dir) — lite uses fast-only path
    if not skip_metadata:
        scraper = TiktokVideoMetadataScraper(url, output_dir=run_dir)
        scraper.fast_scrape_summary()

    # 1.b) Comments scrape (optional)
    # Default: API-based scraper (thirdparty) for robustness; fallback to DOM if it fails
    if do_comments:
        try:
            print("[comments] Using API-based scraper (thirdparty) ...")
            # Fetch up to 500 to give room; downstream analysis can subselect
            run_api_comments(url, size=500, out_dir=run_dir)
        except Exception as e:
            print(f"[comments] API-based scrape failed ({e}); falling back to DOM scraper...")
            try:
                comments = TiktokVideoCommentsScraper(url, output_dir=run_dir, max_comments=500)
                asyncio.get_event_loop().run_until_complete(comments.scrape())
            except Exception as e2:
                print(f"[comments] DOM scrape also failed: {e2}")

    # 2) Download video (yt-dlp only in lite)
    mp4_path = None
    try:
        ytd = YTDLPDownloader(download_dir=run_dir)
        mp4_path = ytd.download(url)
    except Exception:
        mp4_path = None

    # If downloader returned a path that doesn't exist, try to locate by video id in Downloads
    if not mp4_path or not os.path.isfile(mp4_path):
        # Try to derive the video id from the URL and locate a matching file
        vid = None
        try:
            vid = url.rstrip('/').split('/')[-1]
        except Exception:
            vid = None
        if vid:
            candidate = _latest_downloaded_mp4(time.time() - 24*3600, timeout=2, pattern=vid)
            if candidate and os.path.isfile(candidate):
                # Move into run_dir for consistent outputs
                dest = os.path.join(run_dir, os.path.basename(candidate))
                try:
                    os.replace(candidate, dest)
                    mp4_path = dest
                except Exception:
                    mp4_path = candidate

    if not mp4_path or not os.path.isfile(mp4_path):
        raise RuntimeError("Could not download MP4 with yt-dlp. Please check the URL or try again later.")

    if extract_audio_only:
        # Extract MP3 only (optional feature). Import lazily to avoid Whisper dependency.
        try:
            try:
                from src.transcribers.tiktok_video_to_text import SpeechConverter  # type: ignore
            except ModuleNotFoundError:
                from transcribers.tiktok_video_to_text import SpeechConverter  # type: ignore
            sc = SpeechConverter(mp4_path)
            sc.convert_mp4_to_mp3()
        except Exception as e:
            print(f"[warn] Audio extraction not available: {e}")
        return

    _analyze_local_mp4(mp4_path, transcribe, do_face, do_objects, do_nlp)


def _analyze_local_mp4(
    mp4_path: str,
    transcribe: bool = False,
    do_face: bool = False,
    do_objects: bool = False,
    do_nlp: bool = False,
) -> None:
    # 4) Transcription disabled by default. Only run if explicitly requested.
    text = None
    if transcribe:
        try:
            try:
                from src.transcribers.tiktok_video_to_text import SpeechConverter  # type: ignore
            except ModuleNotFoundError:
                from transcribers.tiktok_video_to_text import SpeechConverter  # type: ignore
            speech_converter = SpeechConverter(mp4_path)
            text = speech_converter.extract_and_transform_speech()
        except Exception as e:
            print(f"[warn] Transcription not available: {e}")

    # CV steps removed in lite

    # 7) NLP analysis
    # NLP steps removed in lite (can be re-enabled in full version)


def main():
    parser = argparse.ArgumentParser(description="One-shot TikTok analyzer pipeline.")
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--url", type=str, help="TikTok video URL")
    g.add_argument("--mp4", type=str, help="Local MP4 file path (skip download)")

    parser.add_argument("--no-face", action="store_true", help="Disable face detection")
    parser.add_argument("--no-objects", action="store_true", help="Disable object detection")
    parser.add_argument("--no-nlp", action="store_true", help="Disable NLP analysis")
    parser.add_argument("--comments", action="store_true", help="Also scrape comments from the video page")

    parser.add_argument("--browser", "-b", choices=["pyppeteer", "selenium"], default="pyppeteer")
    parser.add_argument("--driver", "-d", choices=["chrome", "firefox"], default="firefox")
    parser.add_argument("--meta-fast", action="store_true", help="Use fast metadata summary mode (no headless browser)")
    parser.add_argument("--skip-metadata", action="store_true", help="Skip metadata scraping entirely")
    parser.add_argument("--extract-audio-only", action="store_true", help="Only download video and extract MP3 (no NLP/CV)")
    parser.add_argument("--transcribe", action="store_true", help="Run Whisper transcription (no NLP by default)")

    args = parser.parse_args()

    do_face = not args.no_face
    do_objects = not args.no_objects
    do_nlp = not args.no_nlp

    if args.url:
        analyze_url(
            args.url,
            do_face=do_face,
            do_objects=do_objects,
            do_nlp=do_nlp,
            do_comments=args.comments,
            transcribe=args.transcribe,
            meta_fast=args.meta_fast,
            skip_metadata=args.skip_metadata,
            extract_audio_only=args.extract_audio_only,
            browser=args.browser,
            driver=args.driver,
        )
    else:
        if not os.path.isfile(args.mp4):
            raise FileNotFoundError(f"MP4 not found: {args.mp4}")
        _analyze_local_mp4(args.mp4, do_face=do_face, do_objects=do_objects, do_nlp=do_nlp)


if __name__ == "__main__":
    main()
