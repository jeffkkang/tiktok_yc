#!/usr/bin/env python3

import os
from typing import Optional

from yt_dlp import YoutubeDL


class YTDLPDownloader:
    def __init__(self, download_dir: Optional[str] = None):
        self.download_dir = download_dir or os.path.expanduser("~/Downloads")

    def download(self, url: str) -> Optional[str]:
        os.makedirs(self.download_dir, exist_ok=True)
        outtmpl = os.path.join(self.download_dir, "%(uploader)s_%(id)s.%(ext)s")
        ydl_opts = {
            "outtmpl": outtmpl,
            "merge_output_format": "mp4",
            # Prefer mp4 if available, otherwise best
            "format": "mp4/best",
            "quiet": False,
            "noprogress": True,
            # Don't use cache outside project dir
            "cachedir": os.path.join(self.download_dir, ".cache"),
        }
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            # Resolve final output filename using yt-dlp's template resolver
            try:
                filename = ydl.prepare_filename(info)
                return filename
            except Exception:
                pass
            # Fallbacks
            if info.get("_filename"):
                return info["_filename"]
            if info.get("requested_downloads"):
                rd = info["requested_downloads"][0]
                if rd.get("_filename"):
                    return rd["_filename"]
            if info.get("id") and info.get("ext"):
                # As a last resort, try <uploader>_<id>.<ext> in downloads dir
                up = info.get("uploader") or ""
                candidate = f"{up}_{info['id']}.{info['ext']}" if up else f"{info['id']}.{info['ext']}"
                return os.path.join(self.download_dir, candidate)
        return None
