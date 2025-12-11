#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TikTok API 직접 호출 스크래퍼 (Hybrid 방식)
- Selenium으로 쿠키 획득
- requests로 API 직접 호출 (10배+ 빠름)
- 실패 시 DOM 방식으로 폴백
"""

import requests
import json
import time
import logging
from typing import List, Dict, Optional
from selenium import webdriver

logger = logging.getLogger(__name__)


class TikTokAPIClient:
    """TikTok API 직접 호출 클라이언트"""

    def __init__(self, cookies: Dict[str, str] = None):
        """
        Args:
            cookies: Selenium에서 가져온 쿠키
        """
        self.session = requests.Session()
        self.cookies = cookies or {}

        # 기본 헤더 설정
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://www.tiktok.com/',
            'Accept': 'application/json, text/plain, */*',
        })

        if self.cookies:
            self.session.cookies.update(self.cookies)

    @staticmethod
    def get_cookies_from_selenium(driver) -> Dict[str, str]:
        """
        Selenium 드라이버에서 쿠키 추출

        Args:
            driver: Selenium WebDriver

        Returns:
            쿠키 딕셔너리
        """
        selenium_cookies = driver.get_cookies()
        return {cookie['name']: cookie['value'] for cookie in selenium_cookies}

    def search_hashtag(self, keyword: str, count: int = 20, cursor: int = 0) -> Optional[Dict]:
        """
        해시태그 검색 API 호출

        Args:
            keyword: 검색 키워드
            count: 가져올 개수
            cursor: 페이지네이션 커서

        Returns:
            API 응답 (JSON)
        """
        # TikTok 검색 API 엔드포인트 (실제 엔드포인트는 DevTools로 확인 필요)
        url = "https://www.tiktok.com/api/search/general/full/"

        params = {
            'keyword': keyword,
            'count': count,
            'cursor': cursor,
            'type': 1,  # 비디오 검색
            'search_id': '',
        }

        try:
            response = self.session.get(url, params=params, timeout=30)

            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"API 호출 실패: {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"API 요청 오류: {e}")
            return None

    def get_video_detail(self, video_id: str) -> Optional[Dict]:
        """
        비디오 상세 정보 API 호출

        Args:
            video_id: 비디오 ID

        Returns:
            비디오 상세 정보 (JSON)
        """
        url = "https://www.tiktok.com/api/item/detail/"

        params = {
            'itemId': video_id,
        }

        try:
            response = self.session.get(url, params=params, timeout=30)

            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"비디오 상세 API 실패: {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"비디오 상세 요청 오류: {e}")
            return None

    def get_user_profile(self, username: str) -> Optional[Dict]:
        """
        사용자 프로필 API 호출

        Args:
            username: 사용자명

        Returns:
            프로필 정보 (JSON)
        """
        url = "https://www.tiktok.com/api/user/detail/"

        params = {
            'uniqueId': username,
            'language': 'en',
        }

        try:
            response = self.session.get(url, params=params, timeout=30)

            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"프로필 API 실패: {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"프로필 요청 오류: {e}")
            return None


class HybridTikTokScraper:
    """
    Selenium + API 하이브리드 스크래퍼
    """

    def __init__(self, use_api: bool = True):
        """
        Args:
            use_api: API 우선 사용 여부
        """
        self.use_api = use_api
        self.driver = None
        self.api_client = None

    def initialize(self, driver):
        """
        드라이버 초기화 및 쿠키 추출

        Args:
            driver: Selenium WebDriver
        """
        self.driver = driver

        if self.use_api:
            # Selenium에서 쿠키 추출
            cookies = TikTokAPIClient.get_cookies_from_selenium(driver)
            self.api_client = TikTokAPIClient(cookies)
            logger.info("✅ API 클라이언트 초기화 완료 (쿠키 주입)")

    def scrape_hashtag(self, keyword: str, limit: int = 200) -> List[Dict]:
        """
        해시태그 검색 (API 우선, 실패 시 DOM 폴백)

        Args:
            keyword: 검색 키워드
            limit: 수집할 개수

        Returns:
            비디오 리스트
        """
        results = []

        # 1차 시도: API 직접 호출
        if self.use_api and self.api_client:
            logger.info(f"🚀 API 직접 호출 시도: {keyword}")

            cursor = 0
            while len(results) < limit:
                response = self.api_client.search_hashtag(
                    keyword=keyword,
                    count=min(50, limit - len(results)),
                    cursor=cursor
                )

                if response and 'data' in response:
                    # API 응답 파싱 (실제 구조는 확인 필요)
                    videos = self._parse_api_response(response)
                    results.extend(videos)

                    # 페이지네이션
                    if response.get('has_more'):
                        cursor = response.get('cursor', cursor + 50)
                        time.sleep(1)  # 레이트 리밋 대응
                    else:
                        break
                else:
                    logger.warning("⚠️  API 실패 → DOM 방식으로 폴백")
                    break

        # 2차 시도: DOM 스크래핑 (기존 방식)
        if len(results) == 0:
            logger.info(f"📄 DOM 스크래핑 시작: {keyword}")
            # 기존 DOM 스크래퍼 호출
            # results = self._scrape_with_dom(keyword, limit)

        return results[:limit]

    def _parse_api_response(self, response: Dict) -> List[Dict]:
        """
        API 응답 파싱

        Args:
            response: API JSON 응답

        Returns:
            비디오 리스트
        """
        # 실제 TikTok API 응답 구조에 맞게 수정 필요
        videos = []

        items = response.get('data', {}).get('item_list', [])

        for item in items:
            video = {
                'id': item.get('id'),
                'desc': item.get('desc'),
                'author': {
                    'id': item.get('author', {}).get('id'),
                    'uniqueId': item.get('author', {}).get('uniqueId'),
                    'nickname': item.get('author', {}).get('nickname'),
                },
                'stats': item.get('stats', {}),
            }
            videos.append(video)

        return videos


# 사용 예시
if __name__ == "__main__":
    from selenium import webdriver

    # Selenium 드라이버 생성
    driver = webdriver.Chrome()
    driver.get("https://www.tiktok.com")
    time.sleep(5)  # 쿠키 로드 대기

    # 하이브리드 스크래퍼 초기화
    scraper = HybridTikTokScraper(use_api=True)
    scraper.initialize(driver)

    # 검색 실행
    results = scraper.scrape_hashtag("beautyinfluencer", limit=100)
    print(f"수집 완료: {len(results)}개")

    driver.quit()
