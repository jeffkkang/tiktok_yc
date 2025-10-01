#!/usr/bin/env python3

import re
import os
import json
import argparse
import requests


class TiktokVideoMetadataScraper:
    def __init__(self, url, output_dir: str = None):
        self.url = url
        self.output_file = self._output_file(output_dir)

    def _output_file(self, output_dir: str = None):
        pattern = r'https://www\.tiktok\.com/(@\w+)/video/(\d+)'
        match = re.search(pattern, self.url)
        if output_dir is None:
            downloads_dir = os.path.expanduser("~" + os.path.sep + "Downloads/")
        else:
            downloads_dir = output_dir if output_dir.endswith(os.path.sep) else output_dir + os.path.sep
        transformed_string = f"{match.group(1)}_video_{match.group(2)}" if match else "tiktok_video"
        return downloads_dir + transformed_string + "_metadata.json"

    def fast_scrape_summary(self):
        """
        Fast path: single HTTP GET (no headless browser). Extract embedded JSON and
        write only the compact summary JSON for quick access.
        """
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.tiktok.com/",
        }
        resp = requests.get(self.url, headers=headers, timeout=30)
        resp.raise_for_status()
        html = resp.text
        derived = self._extract_from_embedded_state(html)

        summary = {
            "video_url": self.url,
            "platform_labels": derived.get("platform_labels"),
            "location_created": derived.get("location_created"),
            "music_title": derived.get("music_title"),
            "saves_count": derived.get("saves_count"),
        }
        base, _ = os.path.splitext(self.output_file)
        summary_path = f"{base}_summary.json"
        with open(summary_path, 'w', encoding='utf-8') as jf:
            json.dump(summary, jf, ensure_ascii=False, indent=2)
        print(f"Fast metadata summary saved to {summary_path}.")

    @staticmethod
    def _extract_from_embedded_state(html: str) -> dict:
        def safe_get(d, path, default=None):
            cur = d
            for key in path:
                if isinstance(cur, dict) and key in cur:
                    cur = cur[key]
                else:
                    return default
            return cur

        extracted = {
            "platform_labels": None,
            "location_created": None,
            "music_title": None,
            "saves_count": None,
        }

        candidates = []
        m = re.search(r'<script[^>]+id=["\']SIGI_STATE["\'][^>]*>(.*?)</script>', html, re.DOTALL)
        if m:
            try:
                candidates.append(json.loads(m.group(1)))
            except Exception:
                pass
        m2 = re.search(r'<script[^>]+id=["\']__UNIVERSAL_DATA_FOR_REHYDRATION__["\'][^>]*>(.*?)</script>', html, re.DOTALL)
        if m2:
            try:
                candidates.append(json.loads(m2.group(1)))
            except Exception:
                pass

        item = None
        for data in candidates:
            if not isinstance(data, dict):
                continue
            item_module = data.get("ItemModule")
            if isinstance(item_module, dict) and item_module:
                try:
                    item = next(iter(item_module.values()))
                    break
                except Exception:
                    item = None
            default_scope = data.get("__DEFAULT_SCOPE__")
            if isinstance(default_scope, dict):
                webapp = default_scope.get("webapp.video-detail") or default_scope.get("webapp.video-detail-client")
                if isinstance(webapp, dict):
                    item_struct = safe_get(webapp, ["itemInfo", "itemStruct"])
                    if isinstance(item_struct, dict):
                        item = item_struct
                        break

        if isinstance(item, dict):
            extracted["platform_labels"] = item.get("diversificationLabels")
            extracted["location_created"] = item.get("locationCreated")
            music = item.get("music") or {}
            extracted["music_title"] = music.get("title")
            stats = item.get("stats") or {}
            saves = stats.get("collectCount")
            try:
                extracted["saves_count"] = int(saves)
            except Exception:
                extracted["saves_count"] = saves

        return extracted


def main():
    parser = argparse.ArgumentParser(description="Fast TikTok metadata summary scraper (no browser)")
    parser.add_argument("url", help="URL to scrape")
    args = parser.parse_args()

    scraper = TiktokVideoMetadataScraper(args.url)
    scraper.fast_scrape_summary()


if __name__ == "__main__":
    main()
