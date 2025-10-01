#!/usr/bin/env python3

import argparse
import os
import sys

# Support both `python -m src.default_runner` and `python src/default_runner.py`
try:
    from src.pipeline import analyze_url  # when invoked from repo root
except ModuleNotFoundError:
    THIS_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.abspath(os.path.join(THIS_DIR, os.pardir))
    if PROJECT_ROOT not in sys.path:
        sys.path.insert(0, PROJECT_ROOT)
    from pipeline import analyze_url  # type: ignore


def main():
    p = argparse.ArgumentParser(description="Default: metadata + comments + Whisper transcription")
    p.add_argument("url", help="TikTok video URL")
    args = p.parse_args()

    analyze_url(
        args.url,
        do_face=False,
        do_objects=False,
        do_nlp=False,
        transcribe=False,
        do_comments=True,
        meta_fast=True,
        skip_metadata=False,
        extract_audio_only=False,
        browser="pyppeteer",
        driver="firefox",
    )


if __name__ == "__main__":
    main()
