#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TikTok Creator Scraper V8 — EnsembleData API

Pure Python scraper (no Selenium, no browser) using EnsembleData's keyword
search API. Reuses V7's filtering logic (agency filter, email extraction,
priority scoring, creator dedup) with added region filtering.

Usage:
    # Test mode
    python -m tiktok_keyword_scraper.scraper_v8_api -k "kbeauty" --token YOUR_TOKEN --test

    # Full run (US only, last 30 days)
    python -m tiktok_keyword_scraper.scraper_v8_api -k "kbeauty" --token YOUR_TOKEN --max-pages 5 --period 30

    # Multiple regions
    python -m tiktok_keyword_scraper.scraper_v8_api -k "kbeauty" --token YOUR_TOKEN --region "US,CA,GB"

    # All regions (no filter)
    python -m tiktok_keyword_scraper.scraper_v8_api -k "kbeauty" --token YOUR_TOKEN --region all

    # With env var instead of --token
    export ENSEMBLE_DATA_TOKEN=your_token_here
    python -m tiktok_keyword_scraper.scraper_v8_api -k "kbeauty"
"""

import argparse
import csv
import json
import logging
import os
import random
import re
import sys
import time
from datetime import datetime
from typing import Dict, List, Optional, Set

import requests
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load .env from project root
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"))

# ---------------------------------------------------------------------------
# Email extraction (inline from email_utils.py for standalone usage)
# ---------------------------------------------------------------------------
try:
    from .email_utils import EmailExtractor
except ImportError:
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from email_utils import EmailExtractor
    except ImportError:
        # Minimal fallback if email_utils not available
        class EmailExtractor:
            EMAIL_PATTERN = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,15}\b'
            EXCLUDED_DOMAINS = {'example.com', 'test.com', 'domain.com', 'email.com', 'mail.com'}

            @staticmethod
            def extract_emails(text):
                if not text:
                    return []
                emails = re.findall(EmailExtractor.EMAIL_PATTERN, text)
                return [e.lower().strip() for e in emails
                        if '@' in e and e.split('@')[1] not in EmailExtractor.EXCLUDED_DOMAINS]

            @staticmethod
            def get_primary_email(emails):
                if not emails:
                    return 'example@example.com'
                for email in emails:
                    domain = email.split('@')[1]
                    if domain not in EmailExtractor.EXCLUDED_DOMAINS:
                        return email
                return emails[0] if emails else 'example@example.com'


# ---------------------------------------------------------------------------
# Agency Filtering (copied from V7 to avoid Selenium dependency)
# ---------------------------------------------------------------------------

AGENCY_BIO_KEYWORDS = [
    "mgmt", "management", "booking", "represented by",
    "agency", "talent", "inquiries contact", "business inquiries to",
]

AGENCY_EMAIL_PREFIXES = [
    "mgmt@", "booking@", "management@", "talent@", "pr@",
    "info@team", "team@",
]

AGENCY_DOMAINS = {
    "dulcedo.com", "select.co", "select-mgmt.com",
    "uta.com", "caa.com", "wmeagency.com", "icmpartners.com",
    "paradigmagency.com", "abramsentertainment.com",
    "coicollective.co", "evmglobal.co",
    "thedigitalbrandarchitects.com", "digitalbrandarchitects.com",
    "gleamfutures.com", "glowgroup.studio",
    "oezkanentertainment.com", "xo-ent.com",
    "whalar.com", "genflow.com", "goatAgency.com",
    "shade.co", "talentxent.com", "viral-nation.com",
    "influencer.com", "socialyte.co",
}

PERSONAL_DOMAINS = {
    "gmail.com", "yahoo.com", "yahoo.co.kr", "hotmail.com",
    "outlook.com", "icloud.com", "naver.com", "daum.net",
    "hanmail.net", "live.com", "protonmail.com", "me.com",
    "aol.com", "mail.com", "zoho.com", "ymail.com",
}

AGENCY_DOMAIN_PATTERNS = [
    "influencer", "talent", "agency", "management", "mgmt",
    "viralist", "media", "pr", "represent", "studio",
    "creative", "digital", "marketing", "group",
]


def _is_agency_domain_pattern(domain: str) -> bool:
    if domain in PERSONAL_DOMAINS:
        return False
    domain_name = domain.split(".")[0].lower()
    return any(pat in domain_name for pat in AGENCY_DOMAIN_PATTERNS)


def is_agency_managed(bio: str, email: str) -> bool:
    bio_lower = (bio or "").lower()
    for kw in AGENCY_BIO_KEYWORDS:
        if kw in bio_lower:
            return True

    if email:
        email_lower = email.lower()
        for prefix in AGENCY_EMAIL_PREFIXES:
            if email_lower.startswith(prefix):
                return True

        domain = email_lower.split("@")[1] if "@" in email_lower else ""
        if domain in AGENCY_DOMAINS:
            return True
        if _is_agency_domain_pattern(domain):
            return True

    return False


def classify_email_domain(email: str) -> str:
    if not email or "@" not in email:
        return "unknown_domain"
    domain = email.lower().split("@")[1]
    if domain in PERSONAL_DOMAINS:
        return "personal"
    if domain in AGENCY_DOMAINS:
        return "agency"
    if _is_agency_domain_pattern(domain):
        return "agency"
    return "unknown_domain"


# ---------------------------------------------------------------------------
# Creator Database (cross-run memory)
# ---------------------------------------------------------------------------

class CreatorDatabase:
    def __init__(self, filepath: str = "scraped_creators.json"):
        self.filepath = filepath
        self.data: Dict[str, dict] = {}
        self._load()

    def _load(self):
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    self.data = json.load(f)
                logger.info(f"Creator DB loaded: {len(self.data)} creators")
            except Exception as e:
                logger.warning(f"Creator DB load failed ({e}), starting fresh")
                self.data = {}
        else:
            logger.info("Creator DB not found, starting fresh")

    def save(self):
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    def is_known(self, username: str) -> bool:
        return username in self.data

    def add(self, username: str, email: str, follower_count: int):
        self.data[username] = {
            "first_seen": datetime.now().strftime("%Y-%m-%d"),
            "email": email,
            "follower_count": follower_count,
        }

    @property
    def total(self) -> int:
        return len(self.data)


# ---------------------------------------------------------------------------
# Query generation (adapted from V7 — no sort_type/publish_time, uses period)
# ---------------------------------------------------------------------------

def generate_search_keywords(base_keyword: str,
                             skip_keywords: Optional[Set[str]] = None) -> List[str]:
    """Generate diverse search keywords across 5 categories."""
    product_type = [
        "korean sunscreen", "korean toner", "snail mucin",
        "rice toner", "centella cream", "korean serum",
        "korean cleansing balm", "korean eye cream",
        "korean moisturizer", "niacinamide korean",
    ]

    routine_technique = [
        "glass skin routine", "10 step korean skincare",
        "korean skincare morning routine", "korean skincare night routine",
        "korean double cleanse", "korean layering skincare",
        "7 skin method", "slugging korean",
    ]

    brand_names = [
        "cosrx review", "beauty of joseon", "innisfree haul",
        "laneige review", "anua review", "torriden review",
        "skin1004 review", "round lab review", "medicube review",
        "isntree review", "mixsoon review",
    ]

    trends = [
        "kbeauty haul", "korean makeup tutorial", "korean lip tint",
        "kbeauty favorites", "korean skincare haul",
        "olive young haul", "kbeauty must haves",
        "korean skincare routine", "kbeauty recommendations",
    ]

    niche = [
        "kbeauty for acne", "kbeauty for dry skin", "affordable kbeauty",
        "kbeauty for oily skin", "kbeauty for sensitive skin",
        "kbeauty for beginners", "kbeauty on a budget",
        "kbeauty dark skin", "kbeauty anti aging",
    ]

    base = [
        base_keyword,
        f"{base_keyword} tutorial",
        f"{base_keyword} tips",
        f"{base_keyword} routine",
        f"{base_keyword} review",
    ]

    all_keywords = base + product_type + routine_technique + brand_names + trends + niche

    if skip_keywords:
        all_keywords = [k for k in all_keywords if k not in skip_keywords]
        logger.info(f"Skipping {len(skip_keywords)} used keywords, {len(all_keywords)} remaining")

    random.shuffle(all_keywords)
    return all_keywords


# ---------------------------------------------------------------------------
# EnsembleData API Client
# ---------------------------------------------------------------------------

ENSEMBLE_API_URL = "https://ensembledata.com/apis/tt/keyword/search"
PAGE_SIZE = 20  # EnsembleData returns 20 results per cursor offset


class EnsembleDataClient:
    """Thin wrapper around EnsembleData TikTok keyword search API."""

    def __init__(self, token: str):
        self.token = token
        self.session = requests.Session()
        self.api_calls = 0

    def search(self, keyword: str, cursor: int = 0,
               period: int = 0) -> Optional[dict]:
        """Call EnsembleData keyword search API.

        Args:
            keyword: Search keyword
            cursor: Pagination offset (0, 20, 40, ...)
            period: Time filter (0=all, 1=24h, 7=week, 30=month, 90=3mo, 180=6mo)

        Returns:
            Full API response dict, or None on error.
        """
        params = {
            "name": keyword,
            "cursor": cursor,
            "period": period,
            "token": self.token,
        }

        try:
            resp = self.session.get(ENSEMBLE_API_URL, params=params, timeout=30)
            self.api_calls += 1

            if resp.status_code == 200:
                return resp.json()
            elif resp.status_code == 401:
                logger.error("API 인증 실패 — 토큰을 확인하세요")
                return None
            elif resp.status_code == 429:
                logger.warning("API 레이트 리밋 — 5초 대기 후 재시도")
                time.sleep(5)
                resp = self.session.get(ENSEMBLE_API_URL, params=params, timeout=30)
                self.api_calls += 1
                if resp.status_code == 200:
                    return resp.json()
                logger.error(f"재시도 실패: HTTP {resp.status_code}")
                return None
            else:
                logger.warning(f"API 응답 에러: HTTP {resp.status_code}")
                return None

        except requests.exceptions.Timeout:
            logger.warning(f"API 타임아웃: keyword={keyword}, cursor={cursor}")
            return None
        except requests.exceptions.RequestException as e:
            logger.warning(f"API 요청 실패: {e}")
            return None


# ---------------------------------------------------------------------------
# V8 API Scraper
# ---------------------------------------------------------------------------

class ScraperV8API:
    """Pure API-based TikTok creator scraper using EnsembleData."""

    def __init__(
        self,
        token: str,
        creator_db_file: str = "scraped_creators.json",
        max_pages: int = 5,
        period: int = 0,
        regions: Optional[Set[str]] = None,
    ):
        self.client = EnsembleDataClient(token)
        self.creator_db = CreatorDatabase(creator_db_file)
        self.max_pages = max_pages
        self.period = period
        self.regions = regions  # None = all regions (no filter)

        self.stats = {
            "keywords_searched": 0,
            "api_calls": 0,
            "total_items_received": 0,
            "unique_creators_seen": 0,
            "known_skipped": 0,
            "no_email": 0,
            "agency_excluded": 0,
            "region_filtered": 0,
            "new_creators": 0,
            "emails_collected": 0,
            "priority_high": 0,
            "priority_medium": 0,
            "priority_low": 0,
            "flag_personal": 0,
            "flag_agency": 0,
            "flag_unknown_domain": 0,
        }
        self.keyword_stats: List[Dict] = []  # per-keyword performance data

    def _extract_creators_from_response(self, response: dict) -> List[dict]:
        """Extract creator info from a single API response.

        Response structure:
            data.data[].aweme_info.author.{unique_id, nickname, signature, ...}
            data.data[].aweme_info.author.follower_count  (or inside statistics)
        """
        items = []
        try:
            data_wrapper = response.get("data", {})
            if isinstance(data_wrapper, list):
                data_list = data_wrapper
            elif isinstance(data_wrapper, dict):
                data_list = data_wrapper.get("data", [])
                if not isinstance(data_list, list):
                    data_list = []
            else:
                data_list = []
        except Exception:
            return items

        for entry in data_list:
            try:
                aweme_info = entry.get("aweme_info", entry)
                author = aweme_info.get("author", {})
                unique_id = author.get("unique_id", "")
                if not unique_id:
                    continue

                # Follower count can be in multiple places
                follower_count = author.get("follower_count", 0)
                if not follower_count:
                    stats_obj = aweme_info.get("statistics", {})
                    follower_count = stats_obj.get("follower_count", 0)
                if not follower_count:
                    author_stats = aweme_info.get("authorStats", {})
                    follower_count = author_stats.get("followerCount", 0)

                region = author.get("region", "").upper()

                items.append({
                    "unique_id": unique_id,
                    "nickname": author.get("nickname", ""),
                    "signature": author.get("signature", ""),
                    "follower_count": int(follower_count) if follower_count else 0,
                    "following_count": int(author.get("following_count", 0)),
                    "region": region,
                })
            except Exception as e:
                logger.debug(f"Item parse error: {e}")
                continue

        return items

    def _build_row(self, creator: dict, keyword: str, today: str) -> Optional[Dict]:
        """Build a CSV row from API creator data.

        Returns None if filtered. Sets self._last_filter_reason to indicate why:
          "region", "no_email", "agency", or None (not filtered).
        """
        self._last_filter_reason = None
        username = creator["unique_id"]
        bio = creator.get("signature", "")
        follower_count = creator.get("follower_count", 0)
        region = creator.get("region", "")

        # Region filter
        if self.regions and region and region not in self.regions:
            self.stats["region_filtered"] += 1
            self._last_filter_reason = "region"
            return None

        # Email extraction
        emails = EmailExtractor.extract_emails(bio)
        email = EmailExtractor.get_primary_email(emails)

        if not email or email == "example@example.com":
            self.stats["no_email"] += 1
            self._last_filter_reason = "no_email"
            return None

        # Agency filter
        if is_agency_managed(bio, email):
            self.stats["agency_excluded"] += 1
            self._last_filter_reason = "agency"
            return None

        # Priority scoring
        if follower_count < 10_000:
            priority = "high"
        elif follower_count <= 50_000:
            priority = "medium"
        else:
            priority = "low"

        # Update creator DB
        self.creator_db.add(username, email, follower_count)

        self.stats["new_creators"] += 1
        self.stats["emails_collected"] += 1
        self.stats[f"priority_{priority}"] += 1

        email_flag = classify_email_domain(email)
        self.stats[f"flag_{email_flag}"] += 1

        return {
            "keyword": keyword,
            "creator_username": username,
            "creator_nickname": creator.get("nickname", ""),
            "creator_email": email,
            "follower_count": follower_count,
            "creator_region": region,
            "priority": priority,
            "email_flag": email_flag,
            "bio_text": bio,
            "video_url": f"https://www.tiktok.com/@{username}",
            "profile_url": f"https://www.tiktok.com/@{username}",
            "scraped_date": today,
        }

    def _search_keyword(self, keyword: str, today: str,
                        seen_usernames: Set[str]) -> List[Dict]:
        """Search one keyword with pagination. Returns list of CSV rows."""
        rows = []
        self.stats["keywords_searched"] += 1

        # Per-keyword counters for keyword_stats
        kw_total_creators = 0
        kw_emails = 0
        kw_under_10k = 0
        kw_agency = 0
        kw_known_skipped = 0

        for page in range(self.max_pages):
            cursor = page * PAGE_SIZE
            logger.info(f"  [{keyword}] page {page + 1}/{self.max_pages} (cursor={cursor})")

            response = self.client.search(keyword, cursor=cursor, period=self.period)
            if not response:
                logger.warning(f"  [{keyword}] API 응답 없음, 다음 키워드로")
                break

            creators = self._extract_creators_from_response(response)
            self.stats["total_items_received"] += len(creators)
            kw_total_creators += len(creators)

            if not creators:
                logger.info(f"  [{keyword}] 결과 없음 (page {page + 1}), 다음 키워드로")
                break

            new_this_page = 0
            for creator in creators:
                username = creator["unique_id"]

                if username in seen_usernames:
                    continue
                seen_usernames.add(username)
                self.stats["unique_creators_seen"] += 1

                if self.creator_db.is_known(username):
                    self.stats["known_skipped"] += 1
                    kw_known_skipped += 1
                    continue

                row = self._build_row(creator, keyword, today)
                if row:
                    rows.append(row)
                    new_this_page += 1
                    kw_emails += 1
                    if row["follower_count"] < 10_000:
                        kw_under_10k += 1
                elif self._last_filter_reason == "agency":
                    kw_agency += 1

            logger.info(f"  [{keyword}] page {page + 1}: {len(creators)} items, {new_this_page} new emails")

            # Check if there's more data
            has_more = False
            try:
                data_wrapper = response.get("data", {})
                if isinstance(data_wrapper, dict):
                    has_more = data_wrapper.get("has_more", 0) == 1
                    if not has_more:
                        has_more = bool(data_wrapper.get("cursor"))
            except Exception:
                pass

            if not has_more and page > 0:
                logger.info(f"  [{keyword}] 더 이상 결과 없음")
                break

            # Rate limiting
            if page < self.max_pages - 1:
                delay = random.uniform(0.5, 1.0)
                time.sleep(delay)

        # Count agency filtered for this keyword from global stats delta
        # (agency_excluded is tracked in _build_row via self.stats)
        # We track it by counting rows that were None due to agency filter
        # Simpler: count from _build_row calls that returned None for agency
        # Already tracked globally — compute from per-keyword rows

        self.keyword_stats.append({
            "keyword": keyword,
            "total_creators_found": kw_total_creators,
            "emails_found": kw_emails,
            "under_10k_count": kw_under_10k,
            "agency_filtered": kw_agency,
            "already_known_skipped": kw_known_skipped,
        })

        return rows

    def run(self, base_keyword: str, keywords: Optional[List[str]] = None,
            limit: int = 200, skip_keywords: Optional[Set[str]] = None) -> List[Dict]:
        """Execute the full API scraping pipeline.

        Args:
            base_keyword: Base keyword for query generation
            keywords: Override keyword list (if None, auto-generate)
            limit: Target email count
            skip_keywords: Keywords to skip

        Returns:
            List of CSV row dicts
        """
        start_time = time.time()
        today = datetime.now().strftime("%Y-%m-%d")

        if keywords is None:
            keywords = generate_search_keywords(base_keyword, skip_keywords)

        region_str = "all" if not self.regions else ",".join(sorted(self.regions))
        logger.info(f"=== V8 API Scraper starting ===")
        logger.info(f"  Base keyword: {base_keyword}")
        logger.info(f"  Keywords: {len(keywords)}")
        logger.info(f"  Max pages per keyword: {self.max_pages}")
        logger.info(f"  Period: {self.period}")
        logger.info(f"  Region filter: {region_str}")
        logger.info(f"  Target: {limit} emails")
        logger.info(f"  Creator DB: {self.creator_db.total} existing")

        rows = []
        seen_usernames: Set[str] = set()

        for idx, keyword in enumerate(keywords):
            logger.info(f"\n[{idx + 1}/{len(keywords)}] Searching: {keyword}")

            new_rows = self._search_keyword(keyword, today, seen_usernames)
            rows.extend(new_rows)

            # Save DB periodically
            if (idx + 1) % 5 == 0:
                self.creator_db.save()

            # Check if target reached
            if len(rows) >= limit:
                logger.info(f"\n  Target reached: {len(rows)}/{limit} emails")
                break

            # Brief delay between keywords
            if idx < len(keywords) - 1:
                time.sleep(random.uniform(0.3, 0.7))

        # Sort by follower count ascending (smallest first = highest priority)
        rows.sort(key=lambda r: r["follower_count"])

        # Final save
        self.creator_db.save()

        self.stats["api_calls"] = self.client.api_calls
        self.stats["elapsed_seconds"] = int(time.time() - start_time)

        # Save per-keyword stats for future learning loop
        self._save_keyword_stats()

        return rows

    def _save_keyword_stats(self, filepath: str = "keyword_stats.json"):
        """Append per-keyword performance data to keyword_stats.json."""
        existing = []
        if os.path.exists(filepath):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    existing = json.load(f)
            except (json.JSONDecodeError, Exception):
                existing = []

        run_date = datetime.now().strftime("%Y-%m-%d %H:%M")
        for entry in self.keyword_stats:
            entry["run_date"] = run_date

        existing.extend(self.keyword_stats)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)

        logger.info(f"Keyword stats saved: {len(self.keyword_stats)} entries → {filepath}")

    def print_summary(self, output_file: str):
        s = self.stats
        elapsed = s.get("elapsed_seconds", 0)
        minutes = elapsed // 60
        seconds = elapsed % 60

        region_str = "all" if not self.regions else ",".join(sorted(self.regions))

        print(f"""
========== SCRAPER V8 API RUN SUMMARY ==========
Keywords searched: {s['keywords_searched']}
API calls: {s['api_calls']}
Total items received: {s['total_items_received']}
Unique creators seen: {s['unique_creators_seen']}
Region filter: {region_str}
Period filter: {self.period}

Filtering:
  Already known (skipped): {s['known_skipped']}
  No email in bio: {s['no_email']}
  Agency-managed (excluded): {s['agency_excluded']}
  Region filtered: {s['region_filtered']}

Results:
  New creators found: {s['new_creators']}
  Emails collected: {s['emails_collected']}
    - High priority (under 10K): {s['priority_high']}
    - Medium priority (10K-50K): {s['priority_medium']}
    - Low priority (50K+): {s['priority_low']}
  Email domain classification:
    - Personal (gmail, etc.): {s['flag_personal']}
    - Agency/management: {s['flag_agency']}
    - Unknown domain: {s['flag_unknown_domain']}

Time elapsed: {minutes}m {seconds}s
Output saved to: {output_file}
Creator database: {self.creator_db.filepath} ({self.creator_db.total} total)
=================================================================
""")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="TikTok Creator Scraper V8 (EnsembleData API)"
    )
    parser.add_argument("-k", "--keyword", required=True, help="Base search keyword")
    parser.add_argument("--token", default=None,
                        help="EnsembleData API token (or set ENSEMBLE_DATA_TOKEN env var)")
    parser.add_argument("-l", "--limit", type=int, default=200, help="Target email count")
    parser.add_argument("--max-pages", type=int, default=5,
                        help="Max pages per keyword (each page = 20 results)")
    parser.add_argument("--period", type=int, default=0,
                        choices=[0, 1, 7, 30, 90, 180],
                        help="Time filter: 0=all, 1=24h, 7=week, 30=month, 90=3mo, 180=6mo")
    parser.add_argument("--region", default="US",
                        help="Region filter: 'US', 'US,CA,GB', or 'all' for no filter")
    parser.add_argument("--creator-db", default="scraped_creators.json",
                        help="Creator DB file path")
    parser.add_argument("--keywords-file", default=None,
                        help="File with one keyword per line (overrides auto-generation)")
    parser.add_argument("--skip-keywords", nargs="*", default=None,
                        help="Keywords to skip")
    parser.add_argument("--test", action="store_true",
                        help="Test mode: 2 keywords, 1 page each")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Token
    token = args.token or os.environ.get("ENSEMBLE_DATA_TOKEN")
    if not token:
        logger.error("API 토큰이 필요합니다. --token 또는 ENSEMBLE_DATA_TOKEN 환경변수를 설정하세요.")
        sys.exit(1)

    # Region parsing
    regions: Optional[Set[str]] = None
    if args.region.lower() != "all":
        regions = {r.strip().upper() for r in args.region.split(",") if r.strip()}

    # Keywords from file
    keywords = None
    if args.keywords_file:
        if os.path.exists(args.keywords_file):
            with open(args.keywords_file, "r", encoding="utf-8") as f:
                keywords = [line.strip() for line in f if line.strip()]
            logger.info(f"Loaded {len(keywords)} keywords from {args.keywords_file}")
        else:
            logger.error(f"Keywords file not found: {args.keywords_file}")
            sys.exit(1)

    # Test mode overrides
    max_pages = args.max_pages
    limit = args.limit
    if args.test:
        max_pages = 1
        limit = 10
        if keywords is None:
            keywords = [args.keyword, f"{args.keyword} review"]
        else:
            keywords = keywords[:2]
        logger.info(f"TEST MODE: {len(keywords)} keywords, 1 page each, limit {limit}")

    skip_kw = set(args.skip_keywords) if args.skip_keywords else None

    scraper = ScraperV8API(
        token=token,
        creator_db_file=args.creator_db,
        max_pages=max_pages,
        period=args.period,
        regions=regions,
    )

    rows = scraper.run(
        base_keyword=args.keyword,
        keywords=keywords,
        limit=limit,
        skip_keywords=skip_kw,
    )

    # Save CSV
    output_file = f"results/{args.keyword}_v8.csv"
    os.makedirs("results", exist_ok=True)

    fieldnames = [
        "keyword", "creator_username", "creator_nickname", "creator_email",
        "follower_count", "creator_region", "priority", "email_flag",
        "bio_text", "video_url", "profile_url", "scraped_date",
    ]

    file_exists = os.path.exists(output_file) and os.path.getsize(output_file) > 0
    mode = "a" if file_exists else "w"

    with open(output_file, mode, newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        for row in rows:
            writer.writerow(row)

    if file_exists:
        logger.info(f"Appended {len(rows)} rows to existing {output_file}")

    scraper.print_summary(output_file)


if __name__ == "__main__":
    main()
