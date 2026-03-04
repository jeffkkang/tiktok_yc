#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TikTok Creator Scraper V7 — Selenium Hybrid

Combines the browser-based scraping pipeline (Selenium + DOM parsing) with
V6's search diversity (sort_type × publish_time) and V7 upgrades:
  - Scroll-based pagination (real browser scrolling)
  - Cross-run creator memory (scraped_creators.json)
  - Agency filtering
  - Follower-based priority sorting
  - Enhanced CSV output

Uses the existing package modules: cookie.py, profile.py, email_utils.py, utils.py, models.py

Usage:
    # Test mode (2 queries, limited scroll)
    python -m tiktok_keyword_scraper.scraper_v7 -k "kbeauty" --test

    # Full run
    python -m tiktok_keyword_scraper.scraper_v7 -k "kbeauty" -l 200

    # Standalone (from project root)
    python tiktok_keyword_scraper/scraper_v7.py -k "kbeauty" -l 200 --cookies data/tiktok_cookies.json
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
from typing import Dict, List, Optional
from urllib.parse import quote

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Handle both package and standalone execution
# ---------------------------------------------------------------------------
try:
    from .cookie import CookieManager
    from .profile import ProfileScraper
    from .email_utils import EmailExtractor
    from .utils import parse_count, random_delay, get_random_user_agent
    from .scraper import TikTokSearchScraper, CaptchaDetectedException
except ImportError:
    # Standalone execution — add parent to path
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from cookie import CookieManager
    from profile import ProfileScraper
    from email_utils import EmailExtractor
    from utils import parse_count, random_delay, get_random_user_agent
    from scraper import TikTokSearchScraper, CaptchaDetectedException


# ---------------------------------------------------------------------------
# Agency Filtering
# ---------------------------------------------------------------------------

AGENCY_BIO_KEYWORDS = [
    "mgmt", "management", "booking", "represented by",
    "agency", "talent", "inquiries contact", "business inquiries to",
]

AGENCY_EMAIL_PREFIXES = [
    "mgmt@", "booking@", "management@", "talent@", "pr@",
    "info@team", "team@",
]

# Known agency/management domains
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

# Personal email domains (always pass)
PERSONAL_DOMAINS = {
    "gmail.com", "yahoo.com", "yahoo.co.kr", "hotmail.com",
    "outlook.com", "icloud.com", "naver.com", "daum.net",
    "hanmail.net", "live.com", "protonmail.com", "me.com",
    "aol.com", "mail.com", "zoho.com", "ymail.com",
}

# Domain name patterns that indicate agency/management companies
AGENCY_DOMAIN_PATTERNS = [
    "influencer", "talent", "agency", "management", "mgmt",
    "viralist", "media", "pr", "represent", "studio",
    "creative", "digital", "marketing", "group",
]


def _is_agency_domain_pattern(domain: str) -> bool:
    """Check if a domain name contains agency-indicating patterns.

    Only applies to unknown domains (not personal email providers).
    """
    if domain in PERSONAL_DOMAINS:
        return False
    domain_name = domain.split(".")[0].lower()
    return any(pat in domain_name for pat in AGENCY_DOMAIN_PATTERNS)


def is_agency_managed(bio: str, email: str) -> bool:
    """Check if a creator appears to be agency-managed.

    Does NOT flag 'DM for collabs' or 'business email' — those are
    independent creators open to deals.
    """
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
    """Classify email domain as personal, agency, or unknown.

    Returns: "personal", "agency", or "unknown_domain"
    """
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
    """Persistent creator tracking across scraper runs."""

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
# Query generation (V6 strategy)
# ---------------------------------------------------------------------------

def generate_search_queries(keyword: str, limit: int = 200,
                            max_scroll: int = 80,
                            skip_keywords: Optional[set] = None) -> List[Dict]:
    """Generate diverse search queries across 5 categories.

    Categories:
    1. 제품 타입 (product type)
    2. 루틴/기법 (routine/technique)
    3. 브랜드명 (brand names)
    4. 트렌드 (trends)
    5. 니치 (niche)

    Each query is combined with sort_type × publish_time for maximum diversity.
    Returns list of dicts with keys: query, sort_type, publish_time, max_scroll
    """
    # --- 5 categories of keywords ---
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

    # Also include the base keyword variations
    base = [
        keyword,
        f"{keyword} tutorial",
        f"{keyword} tips",
        f"{keyword} routine",
        f"{keyword} review",
    ]

    all_keywords = base + product_type + routine_technique + brand_names + trends + niche

    # Filter out already-used keywords
    if skip_keywords:
        all_keywords = [k for k in all_keywords if k not in skip_keywords]
        logger.info(f"Skipping {len(skip_keywords)} used keywords, {len(all_keywords)} remaining")

    # Shuffle within each category for variety but keep categories grouped
    random.shuffle(product_type)
    random.shuffle(routine_technique)
    random.shuffle(brand_names)
    random.shuffle(trends)
    random.shuffle(niche)

    queries = []

    # Strategy 1: All keywords with relevance sort (broadest)
    for v in all_keywords:
        queries.append({"query": v, "sort_type": 0, "publish_time": None})

    # Strategy 2: All keywords with latest sort (finds newer/smaller creators)
    for v in all_keywords:
        queries.append({"query": v, "sort_type": 1, "publish_time": None})

    # Strategy 3: Top keywords with time filters
    top_keywords = base + product_type[:5] + brand_names[:5] + trends[:3]
    for v in top_keywords:
        for t in [7, 30]:
            queries.append({"query": v, "sort_type": 0, "publish_time": t})

    # Strategy 4: Latest + time filters for niche
    for v in niche[:5]:
        for t in [7, 30]:
            queries.append({"query": v, "sort_type": 1, "publish_time": t})

    # Deduplicate (same query+sort+time combo)
    seen = set()
    unique_queries = []
    for q in queries:
        key = (q["query"], q["sort_type"], q.get("publish_time"))
        if key not in seen:
            seen.add(key)
            unique_queries.append(q)

    # Estimate how many queries we need
    # Real-world yield: ~12 unique creators per query (from test data)
    avg_per_query = 12
    needed = max(6, limit // avg_per_query + 2)
    result = unique_queries[:needed]

    for q in result:
        q["max_scroll"] = max_scroll

    logger.info(
        f"Generated {len(result)} search queries "
        f"(from {len(unique_queries)} possible, {len(all_keywords)} keywords)"
    )
    return result


def build_search_url(query: str, sort_type: int = 0,
                     publish_time: Optional[int] = None) -> str:
    """Build a TikTok search URL with sort/time filters."""
    url = f"https://www.tiktok.com/search/video?q={quote(query)}"
    if sort_type == 1:
        url += "&sort_type=1"
    if publish_time is not None:
        url += f"&publish_time={publish_time}"
    return url


# ---------------------------------------------------------------------------
# V7 Scraper
# ---------------------------------------------------------------------------

class ScraperV7:
    """Selenium hybrid scraper with V7 upgrades."""

    def __init__(
        self,
        cookies_file: str = "tiktok_cookies.json",
        creator_db_file: str = "scraped_creators.json",
        headless: bool = True,
        max_scroll: int = 150,
        min_scroll: int = 50,
        delay_min: float = 1.5,
        delay_max: float = 3.0,
    ):
        self.cookies_file = cookies_file
        self.headless = headless
        self.max_scroll = max_scroll
        self.min_scroll = min_scroll
        self.delay_min = delay_min
        self.delay_max = delay_max
        self.creator_db = CreatorDatabase(creator_db_file)
        self.email_extractor = EmailExtractor()

        # Stats
        self.stats = {
            "queries_executed": 0,
            "videos_found": 0,
            "api_extracted": 0,
            "api_emails_found": 0,
            "truncated_bios": 0,
            "truncated_visits": 0,
            "profiles_visited": 0,
            "new_creators": 0,
            "known_skipped": 0,
            "agency_excluded": 0,
            "no_email": 0,
            "emails_collected": 0,
            "priority_high": 0,
            "priority_medium": 0,
            "priority_low": 0,
            "flag_personal": 0,
            "flag_agency": 0,
            "flag_unknown_domain": 0,
        }

        # Selenium components (initialized in run())
        self.search_scraper: Optional[TikTokSearchScraper] = None
        self.profile_scraper: Optional[ProfileScraper] = None

    def _init_browser(self, force_visible: bool = False):
        """Initialize Selenium browser + profile scraper.

        Args:
            force_visible: True이면 headless 설정을 무시하고 브라우저 표시
        """
        headless = False if force_visible else self.headless
        cookie_manager = CookieManager(self.cookies_file)

        self.search_scraper = TikTokSearchScraper(
            cookie_manager=cookie_manager,
            headless=headless,
            delay_min=self.delay_min,
            delay_max=self.delay_max,
            use_undetected=True,
        )

        driver = self.search_scraper.setup_driver()

        self.profile_scraper = ProfileScraper(
            driver=driver,
            delay_min=self.delay_min,
            delay_max=self.delay_max,
        )

        mode = "headless" if headless else "browser"
        logger.info(f"Browser initialized ({mode} mode)")

    def _close_browser(self):
        """Shut down browser and kill lingering chromedriver processes."""
        if self.search_scraper:
            self.search_scraper.close()
            self.search_scraper = None
            self.profile_scraper = None
        # Kill any lingering chromedriver processes to prevent stale sessions
        import subprocess
        for proc_name in ["chromedriver", "undetected_chromedriver"]:
            try:
                subprocess.run(
                    ["pkill", "-f", proc_name],
                    capture_output=True, timeout=5,
                )
            except Exception:
                pass

    # ---- Scroll helpers (5 patterns from scraper.py:651-749) ----

    def _scroll_by_amount(self, amount: int):
        """일정량 스크롤."""
        self.search_scraper.driver.execute_script(f"window.scrollBy(0, {amount});")

    def _scroll_to_position(self):
        """특정 위치로 스크롤 (60-90%)."""
        try:
            driver = self.search_scraper.driver
            total_height = driver.execute_script("return document.body.scrollHeight")
            target = int(total_height * random.uniform(0.6, 0.9))
            driver.execute_script(f"window.scrollTo(0, {target});")
        except Exception:
            self._scroll_by_amount(600)

    def _scroll_smoothly(self):
        """부드러운 스크롤 (작은 단위 × 여러 번)."""
        try:
            amount = random.randint(200, 400)
            steps = random.randint(3, 6)
            for _ in range(steps):
                self.search_scraper.driver.execute_script(
                    f"window.scrollBy(0, {amount // steps});"
                )
                time.sleep(random.uniform(0.1, 0.3))
        except Exception:
            self._scroll_by_amount(400)

    def _scroll_to_position_aggressive(self):
        """공격적 위치 스크롤 (70-95%)."""
        try:
            driver = self.search_scraper.driver
            total_height = driver.execute_script("return document.body.scrollHeight")
            target = int(total_height * random.uniform(0.7, 0.95))
            driver.execute_script(f"window.scrollTo(0, {target});")
        except Exception:
            self._scroll_by_amount(1000)

    def _scroll_smoothly_aggressive(self):
        """빠른 부드러운 스크롤 (큰 양 × 적은 단계)."""
        try:
            amount = random.randint(600, 1000)
            steps = random.randint(2, 4)
            for _ in range(steps):
                self.search_scraper.driver.execute_script(
                    f"window.scrollBy(0, {amount // steps});"
                )
                time.sleep(random.uniform(0.05, 0.15))
        except Exception:
            self._scroll_by_amount(800)

    def _scroll_random(self):
        """5가지 패턴 중 랜덤 선택 (scraper.py:651-749)."""
        patterns = [
            lambda: self._scroll_by_amount(random.randint(800, 1500)),
            lambda: self._scroll_to_position(),
            lambda: self._scroll_smoothly(),
            lambda: self._scroll_to_position_aggressive(),
            lambda: self._scroll_smoothly_aggressive(),
        ]
        random.choice(patterns)()

    # ---- API response extraction (JS interceptor + SW bypass) ----

    def _inject_fetch_interceptor(self):
        """검색 API 응답을 캡처하는 JS fetch/XHR 인터셉터 주입.

        TikTok은 Service Worker가 대부분의 API 요청을 가로채기 때문에
        SW 해제 + CDP 우회도 함께 수행한다.
        현재 TikTok 아키텍처에서는 API 캡처가 0건일 수 있으며,
        이 경우 DOM 추출 + Phase 2 프로필 방문이 기본 경로가 된다.
        """
        driver = self.search_scraper.driver

        # 1. CDP로 Service Worker 우회 시도
        try:
            driver.execute_cdp_cmd("Network.enable", {})
            driver.execute_cdp_cmd(
                "Network.setBypassServiceWorker", {"bypass": True}
            )
            logger.debug("CDP Service Worker bypass enabled")
        except Exception:
            pass

        # 2. JS로 Service Worker 해제
        try:
            driver.execute_script("""
                if (navigator.serviceWorker) {
                    navigator.serviceWorker.getRegistrations().then(regs => {
                        for (const r of regs) r.unregister();
                    });
                }
            """)
        except Exception:
            pass

        # 3. fetch/XHR 인터셉터 주입 (넓은 URL 패턴)
        script = """
        window.__tiktok_api_responses = [];

        // fetch 인터셉트
        const origFetch = window.fetch;
        window.fetch = async function(...args) {
            const response = await origFetch.apply(this, args);
            const url = typeof args[0] === 'string' ? args[0] : (args[0]?.url || '');
            if (url.includes('/api/search') || url.includes('/api/recommend')
                || url.includes('/api/creator') || url.includes('item_list')
                || (url.includes('tiktok.com') && url.includes('search'))) {
                try {
                    const clone = response.clone();
                    const body = await clone.text();
                    if (body.length > 200) {
                        window.__tiktok_api_responses.push({url: url, body: body});
                    }
                } catch(e) {}
            }
            return response;
        };

        // XHR 인터셉트
        const origXHROpen = XMLHttpRequest.prototype.open;
        const origXHRSend = XMLHttpRequest.prototype.send;
        XMLHttpRequest.prototype.open = function(method, url, ...rest) {
            this._url = url;
            return origXHROpen.call(this, method, url, ...rest);
        };
        XMLHttpRequest.prototype.send = function(...args) {
            this.addEventListener('load', function() {
                if (this._url && (this._url.includes('/api/search') || this._url.includes('/api/recommend')
                    || this._url.includes('/api/creator') || this._url.includes('item_list')
                    || (this._url.includes('tiktok.com') && this._url.includes('search')))) {
                    try {
                        if (this.responseText && this.responseText.length > 200) {
                            window.__tiktok_api_responses.push({url: this._url, body: this.responseText});
                        }
                    } catch(e) {}
                }
            });
            return origXHRSend.apply(this, args);
        };
        """
        try:
            driver.execute_script(script)
            logger.debug("Fetch interceptor injected")
        except Exception as e:
            logger.warning(f"Fetch interceptor 주입 실패: {e}")

    def _extract_creators_from_api_logs(self) -> Dict[str, Dict]:
        """JS 인터셉터가 캡처한 검색 API 응답에서 크리에이터 데이터 추출."""
        driver = self.search_scraper.driver
        try:
            responses = driver.execute_script(
                "return window.__tiktok_api_responses || [];"
            )
        except Exception as e:
            logger.warning(f"API 응답 조회 실패: {e}")
            return {}

        creators: Dict[str, Dict] = {}

        for resp in responses:
            try:
                data = json.loads(resp.get("body", ""))
            except (json.JSONDecodeError, TypeError):
                continue

            # item_list 추출 (다양한 API 응답 구조 대응)
            items = None
            if "item_list" in data:
                items = data["item_list"]
            elif "data" in data and isinstance(data["data"], list):
                items = data["data"]
            elif "data" in data and isinstance(data["data"], dict):
                for key in ["item_list", "data", "items"]:
                    if key in data["data"] and isinstance(data["data"][key], list):
                        items = data["data"][key]
                        break
            if not items:
                continue

            for item_wrapper in items:
                actual = item_wrapper.get("item", item_wrapper)
                author = actual.get("author", {})
                username = author.get("uniqueId", "")
                if not username or username in creators:
                    continue

                stats = actual.get("authorStats", {})
                creators[username] = {
                    "nickname": author.get("nickname", ""),
                    "bio": author.get("signature", ""),
                    "follower_count": stats.get("followerCount", 0),
                    "heart_count": stats.get("heartCount", 0),
                    "video_count": stats.get("videoCount", 0),
                }

        # 캡처 데이터 초기화 (메모리 관리)
        try:
            driver.execute_script("window.__tiktok_api_responses = [];")
        except Exception:
            pass

        if creators:
            logger.info(f"  JS 인터셉터에서 {len(creators)}명 크리에이터 추출")
        return creators

    def _is_bio_truncated(self, bio: str, meta: Dict) -> bool:
        """API에서 받은 bio가 잘렸는지 판단."""
        if not bio:
            return False  # 빈 바이오 → 방문해도 이메일 없을 가능성 높음
        # 1. 길이 기반: API bio가 80자 이상이면 잘렸을 가능성
        if len(bio) >= 80:
            return True
        # 2. 이메일 힌트 키워드 있지만 실제 이메일 없음
        email_hints = ["@", "email", "mail", "contact", "inquir", "collab", "business"]
        bio_lower = bio.lower()
        has_hint = any(h in bio_lower for h in email_hints)
        has_email = bool(EmailExtractor.extract_emails(bio))
        if has_hint and not has_email:
            return True
        return False

    # ---- Search phase: collect usernames via scrolling ----

    def _search_one_query(self, query_config: Dict) -> Dict[str, Dict]:
        """Run one search query and return {username: metadata} dict.

        JS fetch 인터셉터에서 크리에이터 메타데이터(bio, follower_count 등)를 추출하고,
        DOM에서만 발견된 유저네임은 빈 dict로 추가(Phase 2 프로필 방문 대상).

        Includes:
        1. 스크롤 중 CAPTCHA 감지/복구
        2. 적응형 스크롤 대기 시간
        3. 스크롤 패턴 5종 랜덤화
        4. 페이지 끝 3중 감지
        5. JS fetch 인터셉터에서 크리에이터 데이터 추출
        """
        query = query_config["query"]
        sort_type = query_config.get("sort_type", 0)
        publish_time = query_config.get("publish_time")
        scroll_limit = query_config.get("max_scroll", self.max_scroll)

        url = build_search_url(query, sort_type, publish_time)

        desc_parts = [f"'{query}'"]
        if sort_type == 1:
            desc_parts.append("latest")
        if publish_time:
            desc_parts.append(f"{publish_time}d")
        desc = " | ".join(desc_parts)

        logger.info(f"Searching: {desc}")

        driver = self.search_scraper.driver

        # 페이지 로딩 (타임아웃 시 부분 로드된 상태로 계속 진행)
        try:
            driver.get(url)
        except Exception as e:
            if "timeout" in str(e).lower():
                logger.warning(f"Page load timeout — proceeding with partial load")
                # 로딩 중단하고 현재 상태로 진행
                try:
                    driver.execute_script("window.stop();")
                except Exception:
                    pass
            else:
                raise
        time.sleep(random.uniform(2.5, 4.0))

        # Initial CAPTCHA check
        if self.search_scraper._check_captcha():
            logger.warning("CAPTCHA detected on search page load")
            self.search_scraper._handle_captcha()
            try:
                driver.get(url)
            except Exception as e:
                if "timeout" in str(e).lower():
                    logger.warning(f"Page reload timeout — proceeding with partial load")
                    try:
                        driver.execute_script("window.stop();")
                    except Exception:
                        pass
                else:
                    raise
            time.sleep(random.uniform(3.0, 5.0))

        # JS fetch/XHR 인터셉터 주입 (검색 API 응답 캡처용)
        self._inject_fetch_interceptor()

        # --- Scroll loop with all 5 upgrades ---
        usernames = set()
        scroll_attempts = 0
        no_new_count = 0
        heights_unchanged_count = 0
        session_dead = False
        scroll_back_retries = 0
        max_scroll_back_retries = 2  # scroll-back-up 재시도 최대 2회
        min_scroll_runs = self.min_scroll  # CLI --min-scroll로 설정
        max_heights_unchanged = 20
        max_no_new = 30

        last_height = driver.execute_script("return document.body.scrollHeight")

        # [3] 적응형 대기 시간
        fast_wait = (0.8, 1.5)
        normal_wait = (1.5, 2.5)
        slow_wait = (2.5, 3.5)

        while scroll_attempts < scroll_limit:
            try:
                # [1] 스크롤 중 CAPTCHA 감지/복구
                if self.search_scraper._check_captcha():
                    logger.warning("CAPTCHA detected during scroll")
                    self.search_scraper._handle_captcha()
                    time.sleep(random.uniform(2.5, 4.0))

                    try:
                        logger.info("Reloading search page after CAPTCHA")
                        driver.get(url)
                        time.sleep(random.uniform(3.0, 5.0))
                    except Exception as e:
                        logger.warning(f"Page reload error: {e}")

                    # 카운터 리셋 후 계속
                    heights_unchanged_count = 0
                    no_new_count = 0
                    last_height = driver.execute_script(
                        "return document.body.scrollHeight"
                    )
                    continue

                # Find video elements and extract usernames
                video_elements = self.search_scraper._find_video_elements()

                new_found = 0
                for elem in video_elements:
                    username = self._extract_username_from_element(elem)
                    if username and username not in usernames:
                        usernames.add(username)
                        new_found += 1

                if new_found == 0:
                    no_new_count += 1
                else:
                    no_new_count = 0

                # [4] 스크롤 패턴 5종 랜덤화
                self._scroll_random()
                scroll_attempts += 1

                # [5] 페이지 끝 3중 감지
                current_height = driver.execute_script(
                    "return document.body.scrollHeight"
                )
                current_scroll_top = driver.execute_script(
                    "return window.pageYOffset"
                )
                window_height = driver.get_window_size()["height"]

                # 방법 1: 높이 변화 감지
                height_unchanged = current_height == last_height

                # 방법 2: 스크롤 위치가 페이지 끝 근처인지
                near_bottom = (
                    current_scroll_top + window_height * 1.5
                ) >= current_height

                if height_unchanged:
                    heights_unchanged_count += 1
                else:
                    heights_unchanged_count = 0
                    last_height = current_height

                # 종합 판단: 높이 불변 + 연속 미발견 둘 다 충족해야 중단
                reached_end = (
                    heights_unchanged_count >= max_heights_unchanged
                    and no_new_count >= max_no_new
                )

                if reached_end and scroll_attempts >= min_scroll_runs:
                    # Scroll-back-up retry: 위로 올렸다 다시 내려서 추가 로딩 유도
                    if scroll_back_retries < max_scroll_back_retries:
                        scroll_back_retries += 1
                        logger.info(
                            f"  Scroll-back retry {scroll_back_retries}/"
                            f"{max_scroll_back_retries} at scroll {scroll_attempts}"
                        )
                        driver.execute_script(
                            "window.scrollTo(0, document.body.scrollHeight * 0.3)"
                        )
                        time.sleep(random.uniform(2.0, 3.0))
                        driver.execute_script(
                            "window.scrollTo(0, document.body.scrollHeight)"
                        )
                        time.sleep(random.uniform(3.0, 5.0))
                        # Reset counters to give it another chance
                        heights_unchanged_count = 0
                        no_new_count = 0
                        last_height = driver.execute_script(
                            "return document.body.scrollHeight"
                        )
                        continue

                    logger.info(
                        f"  Page end reached "
                        f"(height:{heights_unchanged_count}/{max_heights_unchanged}, "
                        f"no_new:{no_new_count}/{max_no_new}, "
                        f"scrolls:{scroll_attempts})"
                    )
                    break

                # [3] 적응형 대기 시간
                if new_found > 0:
                    wait_time = random.uniform(*fast_wait)
                elif no_new_count > 5:
                    wait_time = random.uniform(*slow_wait)
                else:
                    wait_time = random.uniform(*normal_wait)

                time.sleep(wait_time)

            except Exception as e:
                err_msg = str(e).lower()
                if "invalid session" in err_msg or "session deleted" in err_msg:
                    logger.warning("Browser session lost during scroll — aborting query")
                    session_dead = True
                    break
                logger.error(f"Scroll error: {e}")
                scroll_attempts += 1
                time.sleep(3)

        self.stats["queries_executed"] += 1
        self.stats["videos_found"] += len(usernames)

        if session_dead:
            raise RuntimeError("Browser session lost during search scroll")

        # JS 인터셉터에서 크리에이터 메타데이터 추출
        api_creators = self._extract_creators_from_api_logs()
        self.stats["api_extracted"] += len(api_creators)

        # DOM에서만 발견된 유저네임은 빈 dict로 추가 (Phase 2 프로필 방문 대상)
        dom_only_count = 0
        for username in usernames:
            if username not in api_creators:
                api_creators[username] = {}
                dom_only_count += 1

        logger.info(
            f"  Found {len(api_creators)} unique creators from: {desc} "
            f"(API: {len(api_creators) - dom_only_count}, DOM-only: {dom_only_count})"
        )

        return api_creators

    def _extract_username_from_element(self, element) -> Optional[str]:
        """Extract creator username from a video DOM element."""
        from selenium.webdriver.common.by import By

        try:
            if element.tag_name == "a":
                href = element.get_attribute("href")
            else:
                try:
                    link = element.find_element(By.CSS_SELECTOR, "a[href*='/video/']")
                    href = link.get_attribute("href")
                except Exception:
                    return None

            if href and "/@" in href and "/video/" in href:
                return href.split("/@")[1].split("/video/")[0]
        except Exception:
            pass
        return None

    # ---- Profile phase: visit each creator page ----

    def _visit_profile(self, username: str) -> Optional[Dict]:
        """Visit a creator profile and extract email + follower count.

        Returns a row dict or None.
        """
        self.stats["profiles_visited"] += 1

        profile_data = self.profile_scraper.fetch_creator_profile(username)

        if not profile_data.get("success"):
            # Check if it was a session error — raise so run() can recover
            err = profile_data.get("error", "").lower()
            if "invalid session" in err or "session deleted" in err:
                raise RuntimeError(profile_data["error"])
            return None

        bio = profile_data.get("bio", "")
        emails = profile_data.get("emails", [])
        email = EmailExtractor.get_primary_email(emails)

        # Skip if no real email
        if not email or email == "example@example.com":
            self.stats["no_email"] += 1
            return None

        # Agency filter
        if is_agency_managed(bio, email):
            self.stats["agency_excluded"] += 1
            logger.info(f"  Agency-managed, skipped: @{username}")
            return None

        follower_count = profile_data.get("follower_count", 0)

        # Priority
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

        nickname = profile_data.get("nickname", "")
        email_flag = classify_email_domain(email)
        self.stats[f"flag_{email_flag}"] += 1

        return {
            "creator_username": username,
            "creator_nickname": nickname,
            "creator_email": email,
            "follower_count": follower_count,
            "priority": priority,
            "email_flag": email_flag,
            "bio_text": bio,
            "video_url": f"https://www.tiktok.com/@{username}",
            "profile_url": f"https://www.tiktok.com/@{username}",
        }

    # ---- Main entry point ----

    def _build_row_from_api(self, username: str, meta: Dict,
                            keyword: str, today: str) -> Optional[Dict]:
        """API 메타데이터에서 CSV row를 생성. 이메일 없거나 에이전시면 None."""
        bio = meta.get("bio", "")
        emails = EmailExtractor.extract_emails(bio)
        email = EmailExtractor.get_primary_email(emails)

        if not email or email == "example@example.com":
            return None

        # Agency filter
        if is_agency_managed(bio, email):
            self.stats["agency_excluded"] += 1
            logger.info(f"  Agency-managed, skipped: @{username}")
            return None

        follower_count = meta.get("follower_count", 0)

        # Priority
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
        self.stats["api_emails_found"] += 1
        self.stats[f"priority_{priority}"] += 1

        nickname = meta.get("nickname", "")
        email_flag = classify_email_domain(email)
        self.stats[f"flag_{email_flag}"] += 1

        return {
            "keyword": keyword,
            "creator_username": username,
            "creator_nickname": nickname,
            "creator_email": email,
            "follower_count": follower_count,
            "priority": priority,
            "email_flag": email_flag,
            "bio_text": bio,
            "video_url": f"https://www.tiktok.com/@{username}",
            "profile_url": f"https://www.tiktok.com/@{username}",
            "scraped_date": today,
        }

    def run(self, keyword: str, limit: int = 200,
            queries: Optional[List[Dict]] = None,
            skip_keywords: Optional[set] = None) -> List[Dict]:
        """Execute the full scraping pipeline (JS intercept + DOM extraction).

        Phase 1: Search + API 로그 추출 (프로필 방문 없음)
          - 검색 스크롤 중 CDP 로그에서 bio/follower 등 메타데이터 추출
          - API bio에서 이메일 추출 → CSV row 생성
          - Bio가 잘린 것으로 판단되면 truncated_list에 추가

        Phase 2: Truncated bio만 프로필 방문
          - Phase 1에서 이메일 힌트가 있지만 bio가 잘려 이메일을 못 찾은 크리에이터만 방문
          - 전체 프로필 방문량을 80-90% 절감
        """
        logger.info(f"=== V7 Scraper starting: keyword='{keyword}', target={limit} ===")

        self._init_browser()

        try:
            # --- Search query generation ---
            if queries is None:
                queries = generate_search_queries(
                    keyword, limit, self.max_scroll, skip_keywords=skip_keywords
                )

            # --- Phase 1: Search + JS 인터셉터에서 크리에이터 데이터 추출 ---
            logger.info("\n=== Phase 1: Search + API 로그 추출 ===")

            all_creators: Dict[str, Dict] = {}  # username → metadata
            search_session_retries = 0
            max_search_retries = 3
            rows = []
            truncated_list = []  # Phase 2 대상 (bio 잘린 크리에이터)
            today = datetime.now().strftime("%Y-%m-%d")

            i = 0
            while i < len(queries):
                if len(rows) >= limit:
                    logger.info(f"Target {limit} reached, stopping search phase")
                    break

                qc = queries[i]
                logger.info(f"\n--- Query {i + 1}/{len(queries)} ---")

                try:
                    creators_data = self._search_one_query(qc)

                    # 각 크리에이터를 즉시 처리 (이메일 추출/분류)
                    for username, meta in creators_data.items():
                        if username in all_creators:
                            continue  # 이미 처리한 크리에이터
                        all_creators[username] = meta

                        if self.creator_db.is_known(username):
                            self.stats["known_skipped"] += 1
                            continue

                        if len(rows) >= limit:
                            break

                        # API 데이터가 있는 경우 (bio, follower_count 등)
                        if meta.get("bio") is not None and meta:
                            bio = meta.get("bio", "")
                            emails = EmailExtractor.extract_emails(bio)
                            email = EmailExtractor.get_primary_email(emails)

                            if email and email != "example@example.com":
                                # 이메일 발견 → row 생성 시도
                                row = self._build_row_from_api(
                                    username, meta, keyword, today
                                )
                                if row:
                                    rows.append(row)
                                    logger.info(
                                        f"  [API] @{username} → {email} "
                                        f"({meta.get('follower_count', 0):,} followers)"
                                    )
                            elif self._is_bio_truncated(bio, meta):
                                # Bio 잘림 → Phase 2 대상
                                truncated_list.append(username)
                                self.stats["truncated_bios"] += 1
                            else:
                                self.stats["no_email"] += 1
                        else:
                            # DOM에서만 발견 (API 데이터 없음) → Phase 2 대상
                            truncated_list.append(username)
                            self.stats["truncated_bios"] += 1

                    i += 1

                except CaptchaDetectedException:
                    if self.headless:
                        logger.warning(
                            "CAPTCHA in headless mode — restarting in browser mode"
                        )
                        self._close_browser()
                        self._init_browser(force_visible=True)
                    else:
                        logger.error("CAPTCHA in browser mode — skipping query")
                        i += 1

                except Exception as e:
                    err_msg = str(e).lower()
                    if "invalid session" in err_msg or "session deleted" in err_msg:
                        if search_session_retries < max_search_retries:
                            search_session_retries += 1
                            logger.warning(
                                f"Session lost during search "
                                f"(retry {search_session_retries}/{max_search_retries})"
                                " — reinitializing browser"
                            )
                            self._close_browser()
                            time.sleep(5)
                            for init_attempt in range(3):
                                try:
                                    self._init_browser(force_visible=True)
                                    break
                                except Exception as init_err:
                                    logger.warning(
                                        f"Browser init failed (attempt {init_attempt + 1}/3): {init_err}"
                                    )
                                    self._close_browser()
                                    time.sleep(5 * (init_attempt + 1))
                            else:
                                logger.error("All browser init attempts failed — stopping")
                                break
                        else:
                            logger.error(
                                "Max search retries reached — stopping search phase"
                            )
                            break
                    else:
                        logger.error(f"Query error: {e}")
                        i += 1

                # Save creator DB periodically
                if i % 5 == 0:
                    self.creator_db.save()

            logger.info(
                f"\nPhase 1 complete: {len(rows)} emails from API, "
                f"{len(truncated_list)} truncated bios for Phase 2"
            )

            # --- Phase 2: Truncated bio만 프로필 방문 ---
            if truncated_list and len(rows) < limit:
                logger.info(f"\n=== Phase 2: Visiting {len(truncated_list)} truncated profiles ===")

                # Ensure browser is alive
                if not self.search_scraper:
                    logger.info("Browser not available — reinitializing for Phase 2")
                    for init_attempt in range(3):
                        try:
                            self._init_browser(force_visible=True)
                            break
                        except Exception as init_err:
                            logger.warning(
                                f"Browser init failed (attempt {init_attempt + 1}/3): {init_err}"
                            )
                            self._close_browser()
                            time.sleep(5 * (init_attempt + 1))
                    else:
                        logger.error("Cannot initialize browser — skipping Phase 2")
                        truncated_list = []

                session_retries = 0
                max_session_retries = 3

                for idx, username in enumerate(truncated_list):
                    if len(rows) >= limit:
                        logger.info(f"Target {limit} reached, stopping Phase 2")
                        break

                    logger.info(
                        f"  [Phase 2] [{idx + 1}/{len(truncated_list)}] Visiting @{username}"
                    )
                    self.stats["truncated_visits"] += 1

                    try:
                        row = self._visit_profile(username)
                    except Exception as e:
                        err_msg = str(e).lower()
                        if "invalid session" in err_msg or "session deleted" in err_msg:
                            if session_retries < max_session_retries:
                                session_retries += 1
                                logger.warning(
                                    f"Browser session lost (retry {session_retries}/{max_session_retries})"
                                    " — reinitializing browser"
                                )
                                self._close_browser()
                                time.sleep(5)
                                browser_ok = False
                                for init_attempt in range(3):
                                    try:
                                        self._init_browser(force_visible=True)
                                        browser_ok = True
                                        break
                                    except Exception as init_err:
                                        logger.warning(
                                            f"Browser init failed (attempt {init_attempt + 1}/3): {init_err}"
                                        )
                                        self._close_browser()
                                        time.sleep(5 * (init_attempt + 1))
                                if not browser_ok:
                                    logger.error("All browser init attempts failed — stopping Phase 2")
                                    break
                                try:
                                    row = self._visit_profile(username)
                                except Exception:
                                    logger.error(f"  Retry failed for @{username}")
                                    row = None
                            else:
                                logger.error(
                                    "Max session retries reached — stopping Phase 2"
                                )
                                break
                        else:
                            logger.error(f"  Profile error for @{username}: {e}")
                            row = None

                    if row:
                        row["keyword"] = keyword
                        row["scraped_date"] = today
                        rows.append(row)

                    if (idx + 1) % 20 == 0:
                        self.creator_db.save()

            # Sort by follower count ascending (smallest first)
            rows.sort(key=lambda r: r["follower_count"])

            # Final save
            self.creator_db.save()

            return rows

        finally:
            self._close_browser()

    def print_summary(self, output_file: str):
        s = self.stats
        total_emails = s['emails_collected']
        api_pct = (
            f"{s['api_emails_found'] / total_emails * 100:.0f}%"
            if total_emails > 0 else "N/A"
        )
        print(f"""
========== SCRAPER V7 RUN SUMMARY ==========
Search queries executed: {s['queries_executed']}
Unique creators from search: {s['videos_found']}

[Phase 1] API log extraction:
  Creators extracted from API intercept: {s['api_extracted']}
  Emails found from API bio: {s['api_emails_found']}
  Truncated bios (Phase 2 candidates): {s['truncated_bios']}

[Phase 2] Profile visits (truncated only):
  Profiles visited: {s['profiles_visited']}
  Truncated visits attempted: {s['truncated_visits']}

Results:
  New creators found: {s['new_creators']}
  Already known (skipped): {s['known_skipped']}
  No email in bio: {s['no_email']}
  Agency-managed (excluded): {s['agency_excluded']}
  Emails collected: {total_emails} (API: {api_pct})
    - High priority (under 10K): {s['priority_high']}
    - Medium priority (10K-50K): {s['priority_medium']}
    - Low priority (50K+): {s['priority_low']}
  Email domain classification:
    - Personal (gmail, etc.): {s['flag_personal']}
    - Agency/management: {s['flag_agency']}
    - Unknown domain: {s['flag_unknown_domain']}

Output saved to: {output_file}
Creator database: {self.creator_db.filepath} ({self.creator_db.total} total)
=================================================================
""")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="TikTok Creator Scraper V7 (Selenium)")
    parser.add_argument("-k", "--keyword", required=True, help="Search keyword")
    parser.add_argument("-l", "--limit", type=int, default=200, help="Target email count")
    parser.add_argument("--cookies", default="data/tiktok_cookies.json", help="Cookie file")
    parser.add_argument("--creator-db", default="scraped_creators.json", help="Creator DB file")
    parser.add_argument("--max-scroll", type=int, default=150, help="Max scrolls per query")
    parser.add_argument("--min-scroll", type=int, default=50, help="Min scrolls before allowing early stop")
    parser.add_argument("--headless", action="store_true", help="Run headless (no browser window)")
    parser.add_argument("--test", action="store_true", help="Test mode: 2 queries, 15 scrolls")
    parser.add_argument("--skip-keywords", nargs="*", default=None,
                        help="Keywords already scraped (skip these)")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    max_scroll = 15 if args.test else args.max_scroll
    limit = 10 if args.test else args.limit

    min_scroll = 5 if args.test else args.min_scroll

    scraper = ScraperV7(
        cookies_file=args.cookies,
        creator_db_file=args.creator_db,
        headless=args.headless,
        max_scroll=max_scroll,
        min_scroll=min_scroll,
    )

    # In test mode: only 2 queries
    queries = None
    if args.test:
        queries = [
            {"query": args.keyword, "sort_type": 0, "publish_time": None, "max_scroll": max_scroll},
            {"query": args.keyword, "sort_type": 1, "publish_time": None, "max_scroll": max_scroll},
        ]
        logger.info(f"TEST MODE: 2 queries, {max_scroll} scrolls each, limit {limit}")

    skip_kw = set(args.skip_keywords) if args.skip_keywords else None
    rows = scraper.run(args.keyword, limit, queries=queries, skip_keywords=skip_kw)

    # Save CSV
    output_file = f"results/{args.keyword}_v7.csv"
    os.makedirs("results", exist_ok=True)

    fieldnames = [
        "keyword", "creator_username", "creator_nickname", "creator_email",
        "follower_count", "priority", "email_flag", "bio_text", "video_url",
        "profile_url", "scraped_date",
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
