import os
import re
import time
from typing import Tuple


def parse_tiktok_url(url: str) -> Tuple[str, str]:
    """Return (uploader, video_id) parsed from a TikTok URL; empty strings if not found."""
    m = re.search(r"https?://www\.tiktok\.com/@([^/]+)/video/(\d+)", url)
    if m:
        return m.group(1), m.group(2)
    return "", ""


def make_run_dir(base_dir: str, uploader: str, video_id: str) -> str:
    ts = time.strftime('%Y%m%d_%H%M%S')
    name = f"{uploader}_{video_id}_{ts}" if uploader and video_id else f"tiktok_run_{ts}"
    run_dir = os.path.join(base_dir, name)
    os.makedirs(run_dir, exist_ok=True)
    return run_dir

