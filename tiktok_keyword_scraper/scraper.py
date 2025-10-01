#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Main scraper module for TikTok keyword search
Includes Phase 2 improvements: undetected-chromedriver, retry logic, CAPTCHA handling
"""

import time
import random
import logging
from typing import List, Optional
from urllib.parse import quote

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

try:
    import undetected_chromedriver as uc
    UNDETECTED_AVAILABLE = True
except ImportError:
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from webdriver_manager.chrome import ChromeDriverManager
    UNDETECTED_AVAILABLE = False

from .models import VideoResult
from .cookie import CookieManager
from .utils import parse_count, extract_hashtags, random_delay, get_random_user_agent, retry_on_failure

logger = logging.getLogger(__name__)


class TikTokSearchScraper:
    """TikTok 키워드 검색 스크래퍼 (Phase 2 개선 포함)"""

    def __init__(self, cookie_manager: CookieManager, headless: bool = True,
                 delay_min: float = 1.5, delay_max: float = 3.0,
                 use_undetected: bool = True):
        """
        Initialize search scraper

        Args:
            cookie_manager: 쿠키 관리자
            headless: 헤드리스 모드 여부
            delay_min: 최소 지연 시간
            delay_max: 최대 지연 시간
            use_undetected: undetected-chromedriver 사용 여부
        """
        self.cookie_manager = cookie_manager
        self.headless = headless
        self.delay_min = delay_min
        self.delay_max = delay_max
        self.use_undetected = use_undetected and UNDETECTED_AVAILABLE
        self.driver = None

        if not UNDETECTED_AVAILABLE and use_undetected:
            logger.warning("⚠️  undetected-chromedriver가 설치되지 않음. 일반 chromedriver 사용")

    def setup_driver(self):
        """
        Selenium 드라이버 초기화
        Phase 2: undetected-chromedriver 사용 및 봇 감지 회피 강화
        """
        try:
            if self.use_undetected:
                # undetected-chromedriver 사용 (봇 감지 회피)
                options = uc.ChromeOptions()

                if self.headless:
                    options.add_argument("--headless=new")

                options.add_argument("--disable-blink-features=AutomationControlled")
                options.add_argument("--disable-notifications")
                options.add_argument("--disable-popup-blocking")
                options.add_argument("--disable-dev-shm-usage")
                options.add_argument("--no-sandbox")

                # 랜덤 User-Agent
                user_agent = get_random_user_agent()
                options.add_argument(f"user-agent={user_agent}")

                self.driver = uc.Chrome(options=options, version_main=None)

            else:
                # 일반 chromedriver
                options = Options()

                user_agent = get_random_user_agent()
                options.add_argument(f"user-agent={user_agent}")
                options.add_argument("--disable-blink-features=AutomationControlled")
                options.add_experimental_option('excludeSwitches', ['enable-automation'])
                options.add_experimental_option('useAutomationExtension', False)
                options.add_argument("--disable-notifications")
                options.add_argument("--disable-popup-blocking")

                if self.headless:
                    options.add_argument("--headless=new")

                service = Service(ChromeDriverManager().install())
                self.driver = webdriver.Chrome(service=service, options=options)

            # 타임아웃 설정
            self.driver.set_page_load_timeout(30)

            # 초기 페이지 로드
            self.driver.get("https://www.tiktok.com")
            random_delay(self.delay_min, self.delay_max)

            # 봇 감지 우회 스크립트
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

            # 쿠키 추가
            selenium_cookies = self.cookie_manager.format_for_selenium()
            for cookie in selenium_cookies:
                try:
                    self.driver.add_cookie(cookie)
                except Exception as e:
                    logger.debug(f"쿠키 추가 실패 ({cookie['name']}): {str(e)}")

            # 페이지 새로고침으로 쿠키 적용
            self.driver.refresh()
            random_delay(self.delay_min, self.delay_max)

            logger.info("✅ Selenium 드라이버 초기화 완료")
            return self.driver

        except Exception as e:
            logger.error(f"❌ 드라이버 설정 중 오류 발생: {str(e)}")
            raise

    @retry_on_failure(max_retries=3, delay=5)
    def search_videos_by_keyword(self, keyword: str, limit: int = 100) -> List[VideoResult]:
        """
        키워드로 비디오 검색
        Phase 2: 재시도 로직, CAPTCHA 처리 포함

        Args:
            keyword: 검색 키워드
            limit: 수집할 비디오 수

        Returns:
            List[VideoResult]: 비디오 결과 리스트
        """
        logger.info(f"🔍 키워드 '{keyword}' 검색 시작 (목표: {limit}개)")

        if not self.driver:
            self.setup_driver()

        # TikTok 검색 페이지 접속
        search_url = f"https://www.tiktok.com/search/video?q={quote(keyword)}"
        logger.info(f"검색 URL: {search_url}")
        self.driver.get(search_url)
        time.sleep(random.uniform(2, 4))

        # Phase 2: CAPTCHA 처리
        if self._check_captcha():
            self._handle_captcha()

        # 디버그: 스크린샷 저장
        try:
            self.driver.save_screenshot("debug_search_page.png")
            logger.debug("📸 스크린샷 저장: debug_search_page.png")
        except Exception:
            pass

        videos = []
        scroll_attempts = 0
        max_scroll_attempts = 30
        last_height = self.driver.execute_script("return document.body.scrollHeight")

        while len(videos) < limit and scroll_attempts < max_scroll_attempts:
            try:
                # Phase 2: 향상된 셀렉터 전략 (여러 셀렉터 시도)
                video_elements = self._find_video_elements()

                if not video_elements:
                    logger.warning(f"  ⚠️  비디오 요소를 찾을 수 없음 (시도 {scroll_attempts + 1}/{max_scroll_attempts})")
                    scroll_attempts += 1
                    self._scroll_page()
                    continue

                logger.debug(f"발견된 요소 수: {len(video_elements)}")

                for element in video_elements:
                    if len(videos) >= limit:
                        break

                    video_data = self._extract_video_data(element)
                    if video_data and not self._is_duplicate(videos, video_data):
                        videos.append(video_data)
                        logger.info(f"  ✓ [{len(videos)}/{limit}] @{video_data.creator_username} - 조회수: {video_data.view_count:,}")

                # 스크롤
                self._scroll_page()
                scroll_attempts += 1

                # 스크롤 끝 감지
                new_height = self.driver.execute_script("return document.body.scrollHeight")
                if new_height == last_height:
                    scroll_attempts += 1
                else:
                    last_height = new_height

            except Exception as e:
                logger.error(f"검색 중 오류: {str(e)}")
                scroll_attempts += 1
                time.sleep(2)

        logger.info(f"✅ 총 {len(videos)}개 비디오 수집 완료")
        return videos

    def _find_video_elements(self) -> list:
        """
        Phase 2: 향상된 셀렉터 전략 - 여러 셀렉터 시도
        """
        selectors = [
            "div[data-e2e='search_top-item']",
            "div[data-e2e='search-video-item']",
            "div[class*='video-feed']",
            "a[href*='/@'][href*='/video/']",
            "div[class*='DivItemContainer']",
        ]

        for selector in selectors:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    logger.debug(f"✓ 셀렉터 성공: {selector} ({len(elements)}개)")
                    return elements
            except Exception as e:
                logger.debug(f"✗ 셀렉터 실패: {selector} - {e}")
                continue

        logger.warning("⚠️  모든 셀렉터 실패")
        return []

    def _extract_video_data(self, element) -> Optional[VideoResult]:
        """
        비디오 데이터 추출
        Phase 3: 향상된 데이터 수집 (해시태그, 설명 등)
        """
        try:
            # 비디오 URL 추출
            if element.tag_name == 'a':
                video_url = element.get_attribute('href')
            else:
                try:
                    video_link_elem = element.find_element(By.CSS_SELECTOR, "a[href*='/@']")
                    video_url = video_link_elem.get_attribute('href')
                except NoSuchElementException:
                    return None

            if not video_url or '/@' not in video_url:
                return None

            # URL 파싱
            parts = video_url.split('/@')
            if len(parts) < 2:
                return None

            creator_part = parts[1].split('/video/')[0]
            video_id = parts[1].split('/video/')[-1].split('?')[0] if '/video/' in parts[1] else ""

            if not video_id:
                return None

            # 조회수 추출
            view_count = 0
            try:
                view_elem = element.find_element(By.CSS_SELECTOR, "strong[data-e2e='search-card-video-view-count']")
                view_count = parse_count(view_elem.text)
            except NoSuchElementException:
                pass

            # Phase 3: 비디오 설명 추출
            video_desc = ""
            try:
                desc_elem = element.find_element(By.CSS_SELECTOR, "div[data-e2e='search-card-desc']")
                video_desc = desc_elem.text
            except NoSuchElementException:
                pass

            # Phase 3: 해시태그 추출
            hashtags = extract_hashtags(video_desc) if video_desc else []

            return VideoResult(
                video_id=video_id,
                video_url=video_url,
                creator_id=creator_part,
                creator_username=creator_part,
                view_count=view_count,
                video_desc=video_desc,
                hashtags=hashtags
            )

        except Exception as e:
            logger.debug(f"비디오 데이터 추출 실패: {e}")
            return None

    def _is_duplicate(self, videos: List[VideoResult], new_video: VideoResult) -> bool:
        """중복 체크"""
        return any(v.video_id == new_video.video_id for v in videos)

    def _scroll_page(self):
        """페이지 스크롤 (인간스러운 패턴)"""
        try:
            scroll_amount = random.randint(500, 1000)
            self.driver.execute_script(f"window.scrollBy(0, {scroll_amount});")
            random_delay(1.0, 2.0)
        except Exception as e:
            logger.debug(f"스크롤 실패: {e}")

    def _check_captcha(self) -> bool:
        """CAPTCHA 존재 확인"""
        try:
            # CAPTCHA 관련 요소 확인
            captcha_selectors = [
                "#captcha",
                ".captcha",
                "[class*='captcha']",
                "[id*='captcha']",
            ]

            for selector in captcha_selectors:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    logger.warning("⚠️  CAPTCHA 감지됨")
                    return True

            return False

        except Exception:
            return False

    def _handle_captcha(self):
        """
        Phase 2: CAPTCHA 처리
        수동 해결 대기 (headless가 아닐 때만)
        """
        if not self.headless:
            try:
                logger.warning("⚠️  CAPTCHA가 감지되었습니다. 수동으로 해결 후 Enter를 눌러주세요...")
                input()
                logger.info("✅ 계속 진행합니다.")
            except EOFError:
                logger.warning("⚠️  비인터랙티브 모드에서 실행 중, CAPTCHA 무시")
        else:
            logger.warning("⚠️  헤드리스 모드에서 CAPTCHA 감지됨. 드라이버 재시작 권장")
            time.sleep(5)

    def close(self):
        """드라이버 종료"""
        if self.driver:
            try:
                self.driver.quit()
                logger.info("✅ 드라이버 종료 완료")
            except Exception:
                pass
