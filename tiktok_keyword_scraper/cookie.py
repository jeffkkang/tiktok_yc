#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cookie management module for TikTok keyword scraper
"""

import os
import json
import logging
from typing import Dict, List, Any

logger = logging.getLogger(__name__)


class CookieManager:
    """쿠키 관리자"""

    def __init__(self, cookies_file: str):
        """
        Initialize cookie manager

        Args:
            cookies_file: 쿠키 파일 경로
        """
        self.cookies_file = cookies_file
        self.cookies_dict = {}
        self.cookies_list = []
        self._load_cookies()

    def _load_cookies(self):
        """쿠키 파일 로드"""
        try:
            if not os.path.exists(self.cookies_file):
                logger.warning(f"⚠️  쿠키 파일 {self.cookies_file}을 찾을 수 없음")
                return

            with open(self.cookies_file, 'r', encoding='utf-8') as f:
                cookie_objects = json.load(f)

                if isinstance(cookie_objects, list):
                    # cookies.json 형식 (list of objects with name/value pairs)
                    self.cookies_list = cookie_objects
                    for cookie in cookie_objects:
                        if "name" in cookie and "value" in cookie:
                            self.cookies_dict[cookie["name"]] = cookie["value"]

                    logger.info(f"✅ {len(self.cookies_dict)}개 쿠키 로드 완료")

                elif isinstance(cookie_objects, dict):
                    # Simple key-value format
                    self.cookies_dict = cookie_objects
                    logger.info(f"✅ {len(self.cookies_dict)}개 쿠키 로드 완료")

                else:
                    logger.error(f"❌ 지원하지 않는 쿠키 형식")

        except json.JSONDecodeError as e:
            logger.error(f"❌ 쿠키 파일 JSON 파싱 실패: {e}")
        except Exception as e:
            logger.error(f"❌ 쿠키 로드 실패: {e}")

    def get_cookies(self) -> Dict[str, str]:
        """
        쿠키 딕셔너리 반환

        Returns:
            Dict[str, str]: 쿠키 딕셔너리
        """
        return self.cookies_dict

    def format_for_selenium(self) -> List[Dict[str, Any]]:
        """
        Selenium 형식으로 쿠키 변환

        Returns:
            List[Dict[str, Any]]: Selenium 쿠키 리스트
        """
        if self.cookies_list:
            # 원본 쿠키 리스트 사용 (도메인, path 등 포함)
            return self.cookies_list

        # 딕셔너리에서 변환
        result = []
        for name, value in self.cookies_dict.items():
            result.append({
                "name": name,
                "value": value,
                "domain": ".tiktok.com",
                "path": "/",
                "secure": True,
                "httpOnly": False
            })
        return result

    def save_cookies(self, cookies: List[Dict[str, Any]]):
        """
        쿠키 저장

        Args:
            cookies: 쿠키 리스트
        """
        try:
            with open(self.cookies_file, 'w', encoding='utf-8') as f:
                json.dump(cookies, f, indent=2, ensure_ascii=False)
            logger.info(f"✅ {len(cookies)}개 쿠키 저장 완료: {self.cookies_file}")

        except Exception as e:
            logger.error(f"❌ 쿠키 저장 실패: {e}")

    def is_empty(self) -> bool:
        """
        쿠키가 비어있는지 확인

        Returns:
            bool: 비어있으면 True
        """
        return len(self.cookies_dict) == 0

    def reload(self):
        """쿠키 재로드"""
        logger.info("🔄 쿠키 재로드 중...")
        self.cookies_dict = {}
        self.cookies_list = []
        self._load_cookies()
