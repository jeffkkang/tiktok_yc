#!/usr/bin/env python3

import os
import json
import argparse
from typing import Dict, Any


def load_quick_fields(metadata_path: str) -> Dict[str, Any]:
    """
    Return only the selected fields from a metadata file, quickly.
    If a sidecar summary exists (<meta>_summary.json), load that.
    Otherwise fall back to reading the full metadata JSON and slicing keys.
    """
    base, _ = os.path.splitext(metadata_path)
    summary_path = f"{base}_summary.json"
    if os.path.isfile(summary_path):
        with open(summary_path, "r", encoding="utf-8") as f:
            return json.load(f)

    with open(metadata_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    keys = [
        "video_url",
        "platform_labels",
        "location_created",
        "music_title",
        "saves_count",
    ]
    return {k: data.get(k) for k in keys}


def main():
    p = argparse.ArgumentParser(description="Load quick TikTok metadata fields")
    p.add_argument("metadata", help="Path to full metadata JSON (@user_video_<id>_metadata.json)")
    args = p.parse_args()
    info = load_quick_fields(args.metadata)
    print(json.dumps(info, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
