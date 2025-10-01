#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Configuration management for TikTok keyword scraper
Phase 1: Config file support with CLI override
"""

import os
import yaml
import logging
from typing import Dict, Any, List
from pathlib import Path

from .models import ScraperConfig

logger = logging.getLogger(__name__)


class ConfigManager:
    """설정 관리자"""

    DEFAULT_CONFIG_FILE = "config.yaml"

    def __init__(self, config_file: str = None):
        """
        Initialize config manager

        Args:
            config_file: 설정 파일 경로
        """
        self.config_file = config_file or self.DEFAULT_CONFIG_FILE
        self.config_data = {}
        self._load_config()

    def _load_config(self):
        """설정 파일 로드"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    self.config_data = yaml.safe_load(f) or {}
                logger.debug(f"✅ 설정 파일 로드: {self.config_file}")
            else:
                logger.warning(f"⚠️  설정 파일 없음: {self.config_file}, 기본값 사용")
                self.config_data = self._get_default_config()

        except Exception as e:
            logger.error(f"❌ 설정 파일 로드 실패: {e}, 기본값 사용")
            self.config_data = self._get_default_config()

    def _get_default_config(self) -> Dict[str, Any]:
        """기본 설정 반환"""
        return {
            "defaults": {
                "keywords": [],
                "limit": 50,
                "output_file": "output.csv",
                "output_format": "csv",
                "cookies_file": "cookies.json",
                "delay_min": 1.5,
                "delay_max": 3.0,
                "headless": True,
                "use_browser": False,
                "use_undetected": True,
            },
            "retry": {
                "max_retries": 3,
                "retry_delay": 5,
            },
            "filters": {
                "min_followers": 0,
                "min_views": 0,
                "email_required": False,
            },
            "incremental": {
                "enabled": False,
                "skip_existing": False,
            },
            "performance": {
                "parallel": False,
                "max_workers": 3,
                "cache_enabled": True,
                "cache_ttl": 3600,
            },
            "logging": {
                "level": "INFO",
                "console_level": "INFO",
                "file_level": "DEBUG",
                "log_file": "tiktok_keyword_scraper.log",
            }
        }

    def get(self, key: str, default: Any = None) -> Any:
        """
        설정값 조회

        Args:
            key: 설정 키 (점으로 구분, 예: "defaults.limit")
            default: 기본값

        Returns:
            Any: 설정값
        """
        keys = key.split('.')
        value = self.config_data

        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default

        return value if value is not None else default

    def create_scraper_config(self, cli_args: Dict[str, Any]) -> ScraperConfig:
        """
        CLI 인자와 설정 파일을 병합하여 ScraperConfig 생성
        우선순위: CLI > config.yaml > defaults

        Args:
            cli_args: CLI 인자 딕셔너리

        Returns:
            ScraperConfig: 스크래퍼 설정
        """
        # 기본값
        defaults = self.config_data.get("defaults", {})
        retry = self.config_data.get("retry", {})
        filters = self.config_data.get("filters", {})
        incremental = self.config_data.get("incremental", {})
        performance = self.config_data.get("performance", {})

        # CLI 인자 우선, 없으면 config, 없으면 모델 기본값
        return ScraperConfig(
            keywords=cli_args.get("keywords") or defaults.get("keywords", []),
            limit=cli_args.get("limit") or defaults.get("limit", 50),
            output_file=cli_args.get("output_file") or defaults.get("output_file", "output.csv"),
            output_format=cli_args.get("output_format") or defaults.get("output_format", "csv"),
            cookies_file=cli_args.get("cookies_file") or defaults.get("cookies_file", "cookies.json"),
            delay_min=cli_args.get("delay_min") or defaults.get("delay_min", 1.5),
            delay_max=cli_args.get("delay_max") or defaults.get("delay_max", 3.0),
            headless=cli_args.get("headless") if cli_args.get("headless") is not None else defaults.get("headless", True),
            use_browser=cli_args.get("use_browser") if cli_args.get("use_browser") is not None else defaults.get("use_browser", False),
            max_retries=retry.get("max_retries", 3),
            retry_delay=retry.get("retry_delay", 5),
            min_followers=cli_args.get("min_followers") or filters.get("min_followers", 0),
            min_views=cli_args.get("min_views") or filters.get("min_views", 0),
            email_required=cli_args.get("email_required") if cli_args.get("email_required") is not None else filters.get("email_required", False),
            incremental=cli_args.get("incremental") if cli_args.get("incremental") is not None else incremental.get("enabled", False),
            skip_existing=cli_args.get("skip_existing") if cli_args.get("skip_existing") is not None else incremental.get("skip_existing", False),
            parallel=cli_args.get("parallel") if cli_args.get("parallel") is not None else performance.get("parallel", False),
            max_workers=cli_args.get("max_workers") or performance.get("max_workers", 3),
            cache_enabled=performance.get("cache_enabled", True),
            cache_ttl=performance.get("cache_ttl", 3600),
        )

    def get_logging_config(self) -> Dict[str, str]:
        """로깅 설정 반환"""
        return self.config_data.get("logging", {
            "level": "INFO",
            "console_level": "INFO",
            "file_level": "DEBUG",
            "log_file": "tiktok_keyword_scraper.log",
        })
