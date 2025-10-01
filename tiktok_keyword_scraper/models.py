#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Data models for TikTok keyword scraper
"""

from dataclasses import dataclass, field, asdict
from typing import List, Optional
from datetime import datetime


@dataclass
class VideoResult:
    """검색 결과 비디오 정보"""
    video_id: str
    video_url: str
    creator_id: str
    creator_username: str
    view_count: int = 0
    like_count: int = 0
    comment_count: int = 0
    share_count: int = 0
    video_desc: str = ""
    hashtags: List[str] = field(default_factory=list)
    posted_date: Optional[str] = None

    def to_dict(self):
        """Convert to dictionary"""
        return asdict(self)


@dataclass
class CreatorProfile:
    """크리에이터 프로필 정보 (CSV 출력용)"""
    keyword: str
    video_id: str
    video_url: str
    creator_id: str
    creator_username: str
    creator_email: str
    follower_count: int
    view_count: int = 0
    like_count: int = 0
    comment_count: int = 0
    hashtags: str = ""
    video_desc: str = ""
    posted_date: str = ""
    source_api: str = "page_dom"
    extraction_method: str = "profile_dom"
    scraped_at: str = field(default_factory=lambda: datetime.now().isoformat())
    notes: str = ""

    def to_dict(self):
        """Convert to dictionary"""
        return asdict(self)


@dataclass
class ScraperConfig:
    """스크래퍼 설정"""
    keywords: List[str]
    limit: int = 50
    output_file: str = "output.csv"
    output_format: str = "csv"  # csv, xlsx
    cookies_file: str = "cookies.json"
    delay_min: float = 1.5
    delay_max: float = 3.0
    headless: bool = True
    use_browser: bool = False

    # Phase 2: Retry settings
    max_retries: int = 3
    retry_delay: int = 5

    # Phase 3: Filtering options
    min_followers: int = 0
    min_views: int = 0
    email_required: bool = False

    # Phase 3: Incremental scraping
    incremental: bool = False
    skip_existing: bool = False

    # Phase 4: Performance
    parallel: bool = False
    max_workers: int = 3
    cache_enabled: bool = True
    cache_ttl: int = 3600  # seconds

    def to_dict(self):
        """Convert to dictionary"""
        return asdict(self)
