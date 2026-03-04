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
    UNDETECTED_AVAILABLE = False

# 항상 import
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager


class CaptchaDetectedException(Exception):
    """CAPTCHA 감지 예외"""
    pass

from .models import VideoResult
from .cookie import CookieManager
from .utils import parse_count, extract_hashtags, random_delay, get_random_user_agent, retry_on_failure

import subprocess
import psutil

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

    def _cleanup_zombie_processes(self):
        """좀비 Chrome/ChromeDriver 프로세스 정리"""
        try:
            zombie_count = 0
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    name = proc.info['name'].lower()
                    cmdline = ' '.join(proc.info['cmdline'] or []).lower()
                    
                    # ChromeDriver 프로세스 찾기 (automation 관련만)
                    if 'chromedriver' in name and ('--port=' in cmdline or 'test-type' in cmdline):
                        proc.kill()
                        zombie_count += 1
                        logger.debug(f"좀비 ChromeDriver 제거: PID={proc.info['pid']}")
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            
            if zombie_count > 0:
                logger.info(f"✅ {zombie_count}개 좀비 프로세스 정리 완료")
                time.sleep(1)  # 정리 대기
        except Exception as e:
            logger.warning(f"⚠️ 프로세스 정리 중 오류 (무시함): {e}")

    def setup_driver(self):
        """
        Selenium 드라이버 초기화
        Phase 2: undetected-chromedriver 사용 및 봇 감지 회피 강화
        """
        # 좀비 Chrome 프로세스 정리
        self._cleanup_zombie_processes()
        
        try:
            # 일반 ChromeDriver 우선 사용 (undetected는 불안정)
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
                options.add_argument("--disable-gpu")
                options.add_argument("--window-size=1920,1080")

                # 랜덤 User-Agent
                user_agent = get_random_user_agent()
                options.add_argument(f"user-agent={user_agent}")

                # Phase 2: 크롬 버전 자동 감지
                try:
                    import subprocess
                    chrome_ver = subprocess.check_output(
                        ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "--version"],
                        text=True
                    ).strip().split()[-1].split(".")[0]
                    logger.info(f"Chrome version detected: {chrome_ver}")
                    self.driver = uc.Chrome(options=options, version_main=int(chrome_ver))
                except Exception as e:
                    logger.warning(f"⚠️  undetected-chromedriver 초기화 실패: {e}")
                    logger.info("🔄 일반 ChromeDriver로 폴백 시도...")

                    # 폴백: 일반 ChromeDriver 사용
                    chrome_options = Options()
                    chrome_options.add_argument(f"user-agent={user_agent}")
                    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
                    chrome_options.add_experimental_option('excludeSwitches', ['enable-automation'])
                    chrome_options.add_experimental_option('useAutomationExtension', False)
                    chrome_options.add_argument("--disable-notifications")
                    chrome_options.add_argument("--disable-popup-blocking")
                    chrome_options.add_argument("--disable-dev-shm-usage")
                    chrome_options.add_argument("--no-sandbox")
                    chrome_options.add_argument("--disable-gpu")
                    chrome_options.add_argument("--window-size=1920,1080")

                    if self.headless:
                        chrome_options.add_argument("--headless=new")

                    service = Service(ChromeDriverManager().install())
                    self.driver = webdriver.Chrome(service=service, options=chrome_options)

            else:
                # 일반 chromedriver
                options = Options()

                user_agent = get_random_user_agent()
                options.add_argument(f"user-agent={user_agent}")
                options.add_argument("--disable-blink-features=AutomationControlled")
                options.add_experimental_option('excludeSwitches', ['enable-automation', 'enable-logging'])
                options.add_experimental_option('useAutomationExtension', False)
                options.add_argument("--disable-notifications")
                options.add_argument("--disable-popup-blocking")
                options.add_argument("--disable-dev-shm-usage")
                options.add_argument("--no-sandbox")
                options.add_argument("--disable-gpu")
                options.add_argument("--disable-software-rasterizer")
                options.add_argument("--window-size=1920,1080")
                # 동적 포트 할당 (충돌 방지)
                import random
                debug_port = random.randint(9222, 9999)
                options.add_argument(f"--remote-debugging-port={debug_port}")
                options.add_argument("--log-level=3")  # 로그 레벨 최소화
                logger.debug(f"Remote debugging port: {debug_port}")

                if self.headless:
                    options.add_argument("--headless=new")

                service = Service(ChromeDriverManager().install())
                self.driver = webdriver.Chrome(service=service, options=options)

            # 타임아웃 설정 (60초)
            self.driver.set_page_load_timeout(60)

            # 초기 페이지 로드 (타임아웃 시 about:blank으로 대체)
            initial_load_ok = False
            try:
                self.driver.get("https://www.tiktok.com")
                initial_load_ok = True
            except Exception as e:
                if "timeout" in str(e).lower():
                    logger.warning("초기 페이지 로드 타임아웃 — about:blank으로 대체")
                    try:
                        self.driver.execute_script("window.stop();")
                    except Exception:
                        pass
                    # 렌더러가 응답하지 않을 수 있으므로 about:blank으로 리셋
                    try:
                        self.driver.get("about:blank")
                        time.sleep(1)
                        initial_load_ok = True
                    except Exception:
                        logger.warning("about:blank 로드도 실패 — 계속 진행")
                else:
                    raise
            random_delay(self.delay_min, self.delay_max)

            # 봇 감지 우회 스크립트
            try:
                self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            except Exception as e:
                logger.warning(f"봇 감지 우회 스크립트 실패: {e}")

            # 쿠키 추가
            if initial_load_ok:
                try:
                    # 쿠키 추가를 위해 tiktok.com 도메인 필요
                    if "tiktok.com" not in self.driver.current_url:
                        self.driver.get("https://www.tiktok.com")
                except Exception:
                    pass

            selenium_cookies = self.cookie_manager.format_for_selenium()
            for cookie in selenium_cookies:
                try:
                    self.driver.add_cookie(cookie)
                except Exception as e:
                    logger.debug(f"쿠키 추가 실패 ({cookie['name']}): {str(e)}")

            # 페이지 새로고침으로 쿠키 적용
            try:
                self.driver.refresh()
            except Exception as e:
                if "timeout" in str(e).lower():
                    logger.warning("페이지 새로고침 타임아웃 — 계속 진행")
                    try:
                        self.driver.execute_script("window.stop();")
                    except Exception:
                        pass
                else:
                    logger.warning(f"페이지 새로고침 실패: {e}")
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

        return self._scrape_videos(limit)

    @retry_on_failure(max_retries=3, delay=5)
    def search_videos_by_tag(self, tag: str, limit: int = 100) -> List[VideoResult]:
        """
        태그로 비디오 검색

        Args:
            tag: 태그 이름 (예: 'tiktokgrowthtips' 또는 URL)
            limit: 수집할 비디오 수

        Returns:
            List[VideoResult]: 비디오 결과 리스트
        """
        # URL에서 태그 이름 추출
        if tag.startswith('http'):
            tag = tag.split('/tag/')[-1].split('?')[0]

        logger.info(f"🏷️  태그 '#{tag}' 검색 시작 (목표: {limit}개)")

        if not self.driver:
            self.setup_driver()

        # TikTok 태그 페이지 접속
        tag_url = f"https://www.tiktok.com/tag/{tag}"
        logger.info(f"태그 URL: {tag_url}")
        self.driver.get(tag_url)
        time.sleep(random.uniform(2, 4))

        # CAPTCHA 처리
        if self._check_captcha():
            self._handle_captcha()

        # 디버그: 스크린샷 저장
        try:
            self.driver.save_screenshot("debug_tag_page.png")
            logger.debug("📸 스크린샷 저장: debug_tag_page.png")
        except Exception:
            pass

        return self._scrape_videos(limit)

    def _scrape_videos(self, limit: int) -> List[VideoResult]:
        """
        공통 비디오 스크래핑 로직 - 개선된 속도 + 안정성

        Args:
            limit: 수집할 비디오 수

        Returns:
            List[VideoResult]: 비디오 결과 리스트
        """
        videos = []
        scroll_attempts = 0
        max_scroll_attempts = 200  # 최대 스크롤 시도 증가 (120 → 200)
        consecutive_no_new_videos = 0
        max_consecutive_no_new = 20  # 새 비디오 미발견 허용 증가 (12 → 20)
        heights_unchanged_count = 0
        max_heights_unchanged = 10  # 높이 불변 허용 증가 (6 → 10)
        min_scroll_runs = 25  # 최소 스크롤 횟수 증가 (15 → 25)
        search_url = self.driver.current_url

        # 적응형 대기 시간 제어
        fast_wait = (0.8, 1.5)  # 새 비디오 발견 시 빠른 대기
        normal_wait = (1.5, 2.5)  # 보통 대기
        slow_wait = (2.5, 3.5)  # 로딩 대기가 필요할 때

        # 초기 높이 저장
        last_height = self.driver.execute_script("return document.body.scrollHeight")

        while len(videos) < limit and scroll_attempts < max_scroll_attempts:
            try:
                # CAPTCHA가 다시 나타난 경우 수동 해결을 대기하고 페이지를 재로딩한다
                if self._check_captcha():
                    logger.warning("⚠️  스크롤 중 CAPTCHA가 감지되었습니다. 해결 후 Enter 키를 눌러주세요.")
                    self._handle_captcha()
                    time.sleep(random.uniform(2.5, 4.0))

                    try:
                        logger.info("🔁 CAPTCHA 해제 후 검색 페이지를 다시 로드합니다.")
                        self.driver.get(search_url)
                        time.sleep(random.uniform(3.0, 5.0))
                    except Exception as reload_error:
                        logger.warning(f"⚠️  페이지 재로딩 중 오류: {reload_error}")

                    # 상태 초기화 후 다음 루프로 이동
                    heights_unchanged_count = 0
                    consecutive_no_new_videos = 0
                    last_height = self.driver.execute_script("return document.body.scrollHeight")
                    continue

                # Phase 2: 향상된 셀렉터 전략 (여러 셀렉터 시도)
                video_elements = self._find_video_elements()

                if not video_elements:
                    logger.warning(f"  ⚠️  비디오 요소를 찾을 수 없음 (시도 {scroll_attempts + 1}/{max_scroll_attempts})")
                    scroll_attempts += 1
                    self._scroll_page()
                    time.sleep(random.uniform(2.5, 3.5))  # 스크롤 후 더 충분히 대기
                    continue

                logger.debug(f"발견된 요소 수: {len(video_elements)}")
                new_videos_found = 0

                for element in video_elements:
                    if len(videos) >= limit:
                        break

                    video_data = self._extract_video_data(element)
                    if video_data and not self._is_duplicate(videos, video_data):
                        videos.append(video_data)
                        new_videos_found += 1
                        logger.info(f"  ✓ [{len(videos)}/{limit}] @{video_data.creator_username} - 조회수: {video_data.view_count:,}")

                # 새 비디오 발견 여부 체크
                if new_videos_found == 0:
                    consecutive_no_new_videos += 1
                    logger.debug(f"새 비디오 미발견 (연속 {consecutive_no_new_videos}/{max_consecutive_no_new})")
                else:
                    consecutive_no_new_videos = 0  # 리셋
                    logger.debug(f"새 비디오 발견: {new_videos_found}개")

                # 🚀 개선된 스크롤 (더 빠르고 공격적)
                self._scroll_page_aggressive()
                scroll_attempts += 1

                # 향상된 스크롤 끝 감지 (여러 방법 사용)
                current_height = self.driver.execute_script("return document.body.scrollHeight")
                current_scroll_top = self.driver.execute_script("return window.pageYOffset")

                # 방법 1: 높이 변화 감지
                height_unchanged = (current_height == last_height)

                # 방법 2: 스크롤 위치와 페이지 높이 비교 (페이지 끝 근처인지 확인)
                near_bottom = (current_scroll_top + self.driver.get_window_size()['height'] * 1.5) >= current_height

                # 방법 3: 문서 높이와 스크롤 가능한 높이 비교
                scroll_height = self.driver.execute_script("return Math.max(document.body.scrollHeight, document.documentElement.scrollHeight)")
                client_height = self.driver.execute_script("return Math.max(document.body.clientHeight, document.documentElement.clientHeight)")

                # 종합적인 판단
                if height_unchanged:
                    heights_unchanged_count += 1
                else:
                    heights_unchanged_count = 0
                    last_height = current_height

                # 페이지 끝 도달 조건들 (더 관대하게 변경)
                reached_end = (
                    heights_unchanged_count >= max_heights_unchanged and consecutive_no_new_videos >= max_consecutive_no_new  # 둘 다 만족해야 중단
                )

                if reached_end and scroll_attempts >= min_scroll_runs:
                    logger.info(f"📍 페이지 끝 도달 감지 (높이:{heights_unchanged_count}/{max_heights_unchanged}, 새비디오:{consecutive_no_new_videos}/{max_consecutive_no_new})")
                    if len(videos) < limit:
                        logger.info(f"⚠️ 목표 개수({limit})에 미달하지만 페이지 끝 도달로 중단")
                    break

                # 🎯 적응형 대기 시간 (새 비디오 발견 시 빠르게, 미발견 시 더 대기)
                completion_rate = len(videos) / limit if limit > 0 else 0

                if new_videos_found > 0:
                    # 새 비디오 발견: 빠른 대기
                    wait_time = random.uniform(*fast_wait)
                elif completion_rate > 0.9:
                    # 목표에 거의 도달 (90% 이상): 조금 더 대기하고 더 찾아봄
                    wait_time = random.uniform(*slow_wait)
                    logger.debug(f"🎯 목표 {completion_rate:.0%} 달성, 추가 수집 시도 중...")
                elif consecutive_no_new_videos > 5:
                    # 계속 못 찾고 있음: 느린 대기 (로딩 시간 확보)
                    wait_time = random.uniform(*slow_wait)
                else:
                    # 보통 상황: 일반 대기
                    wait_time = random.uniform(*normal_wait)

                time.sleep(wait_time)

                # 🔄 목표 근처에서 추가 스크롤 트리거
                if completion_rate > 0.85 and consecutive_no_new_videos < 5:
                    # 85% 이상 달성했고 최근에 비디오를 발견했다면 한 번 더 스크롤
                    self._scroll_by_amount(random.randint(500, 1000))
                    time.sleep(random.uniform(0.5, 1.0))

            except Exception as e:
                logger.error(f"검색 중 오류: {str(e)}")
                scroll_attempts += 1
                time.sleep(3)  # 오류 발생 시 더 긴 대기

        logger.info(f"✅ 총 {len(videos)}개 비디오 수집 완료 (스크롤 시도: {scroll_attempts}/{max_scroll_attempts})")
        return videos

    def _find_video_elements(self) -> list:
        """
        Phase 2: 향상된 셀렉터 전략 - 여러 셀렉터 시도 및 대안 탐색
        """
        # 기본 셀렉터들 (우선순위별로 정렬)
        selectors = [
            # 최우선 셀렉터들 (TikTok 2025 구조)
            "div[class*='Item']",
            "div[data-e2e='search_top-item']",
            "div[data-e2e='search-video-item']",
            "div[class*='video-feed']",
            "div[class*='DivItemContainer']",

            # 보조 셀렉터들
            "a[href*='/@'][href*='/video/']",
            "div[class*='VideoContainer']",
            "div[class*='video-item']",
            "article[class*='video']",

            # 광범위한 셀렉터들
            "div[class*='item']",
            "div[class*='card']",
            "div[class*='post']",
        ]

        all_elements = []

        # 1단계: 기본 셀렉터들 시도
        for selector in selectors:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if elements and len(elements) > 0:
                    # 비디오 관련 요소인지 검증
                    valid_elements = self._validate_video_elements(elements)
                    if valid_elements:
                        logger.debug(f"✓ 셀렉터 성공: {selector} ({len(valid_elements)}개 유효)")
                        all_elements.extend(valid_elements)
                        if len(all_elements) >= 10:  # 충분한 요소 발견시 조기 반환
                            return all_elements
            except Exception as e:
                logger.debug(f"✗ 셀렉터 실패: {selector} - {e}")
                continue

        # 2단계: XPath를 이용한 대안 탐색
        if len(all_elements) < 5:  # 기본 셀렉터로 충분하지 않으면
            xpath_selectors = [
                "//div[contains(@class, 'Item')]",
                "//div[contains(@data-e2e, 'search')]",
                "//a[contains(@href, '/video/')]",
                "//div[contains(@class, 'video')]",
                "//article[contains(@class, 'video')]",
            ]

            for xpath in xpath_selectors:
                try:
                    elements = self.driver.find_elements(By.XPATH, xpath)
                    if elements and len(elements) > 0:
                        valid_elements = self._validate_video_elements(elements)
                        if valid_elements:
                            logger.debug(f"✓ XPath 성공: {xpath} ({len(valid_elements)}개 유효)")
                            all_elements.extend(valid_elements)
                            if len(all_elements) >= 10:
                                break
                except Exception as e:
                    logger.debug(f"✗ XPath 실패: {xpath} - {e}")
                    continue

        # 3단계: 발견된 요소들 중 중복 제거 및 검증
        if all_elements:
            # URL 기반으로 중복 제거 (더 정확한 방법)
            seen_urls = set()
            unique_elements = []

            for elem in all_elements:
                try:
                    if elem.tag_name == 'a':
                        href = elem.get_attribute('href')
                    else:
                        # div 내부의 a 태그 찾기
                        try:
                            link_elem = elem.find_element(By.CSS_SELECTOR, "a[href*='/video/']")
                            href = link_elem.get_attribute('href')
                        except:
                            continue

                    if href and '/video/' in href and href not in seen_urls:
                        seen_urls.add(href)
                        unique_elements.append(elem)

                except Exception:
                    continue

            logger.debug(f"📊 총 발견 요소: {len(all_elements)}개, 중복제거 후: {len(unique_elements)}개")
            return unique_elements[:20]  # 너무 많아지지 않도록 제한

        logger.warning("⚠️  모든 셀렉터 및 XPath 실패")
        return []

    def _validate_video_elements(self, elements) -> list:
        """
        발견된 요소들이 실제 비디오 요소인지 검증
        """
        valid_elements = []

        for elem in elements:
            try:
                # 1. 비디오 URL이 포함되어 있는지 확인
                if elem.tag_name == 'a':
                    href = elem.get_attribute('href')
                    if href and '/video/' in href:
                        valid_elements.append(elem)
                else:
                    # div 내부에 비디오 링크가 있는지 확인
                    try:
                        link_elem = elem.find_element(By.CSS_SELECTOR, "a[href*='/video/']")
                        if link_elem:
                            valid_elements.append(elem)
                    except:
                        pass

                # 2. 너무 작거나 보이지 않는 요소 제외 (화면 밖 요소 제외)
                try:
                    rect = elem.rect
                    if rect['width'] < 100 or rect['height'] < 100:  # 너무 작은 요소 제외
                        continue
                    if rect['y'] > self.driver.get_window_size()['height'] * 2:  # 화면 아래쪽 요소 제외
                        continue
                except:
                    pass

            except Exception:
                continue

        return valid_elements

    def _extract_video_data(self, element) -> Optional[VideoResult]:
        """
        비디오 데이터 추출
        Phase 3: 향상된 데이터 수집 (해시태그, 설명 등)
        Updated 2025: New TikTok page structure
        """
        try:
            # 비디오 URL 추출
            if element.tag_name == 'a':
                video_url = element.get_attribute('href')
            else:
                try:
                    video_link_elem = element.find_element(By.CSS_SELECTOR, "a[href*='/video/']")
                    video_url = video_link_elem.get_attribute('href')
                except NoSuchElementException:
                    return None

            if not video_url or '/video/' not in video_url:
                return None

            # URL 파싱
            parts = video_url.split('/@')
            if len(parts) < 2:
                return None

            creator_part = parts[1].split('/video/')[0]
            video_id = parts[1].split('/video/')[-1].split('?')[0] if '/video/' in parts[1] else ""

            if not video_id:
                return None

            # 조회수 추출 (Updated 2025: 첫 번째 strong 태그)
            view_count = 0
            try:
                # 새로운 방법: 첫 번째 strong 태그
                strong_elems = element.find_elements(By.TAG_NAME, "strong")
                if strong_elems and strong_elems[0].text.strip():
                    view_count = parse_count(strong_elems[0].text.strip())
                    logger.debug(f"조회수 추출: {strong_elems[0].text.strip()} -> {view_count}")
            except Exception as e:
                logger.debug(f"조회수 추출 실패: {e}")

            # Phase 3: 비디오 설명 추출 (Updated 2025: 텍스트에서 추출)
            video_desc = ""
            try:
                # 전체 텍스트에서 설명 추출
                full_text = element.text
                lines = [l.strip() for l in full_text.split('\n') if l.strip()]
                # 일반적으로 두 번째 줄이 설명
                if len(lines) >= 2:
                    video_desc = lines[1]
                    logger.debug(f"설명 추출: {video_desc[:50]}...")
            except Exception as e:
                logger.debug(f"설명 추출 실패: {e}")

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
            # 다양한 스크롤 패턴 사용
            scroll_patterns = [
                lambda: self._scroll_by_amount(random.randint(400, 800)),
                lambda: self._scroll_to_position(),
                lambda: self._scroll_smoothly()
            ]

            # 랜덤하게 스크롤 패턴 선택
            scroll_func = random.choice(scroll_patterns)
            scroll_func()

            # 스크롤 후 충분한 대기 시간
            random_delay(1.5, 3.0)

        except Exception as e:
            logger.debug(f"스크롤 실패: {e}")

    def _scroll_page_aggressive(self):
        """🚀 개선된 공격적 스크롤 (더 빠르고 더 많이)"""
        try:
            # 더 큰 스크롤 양 (800-1500px로 증가)
            scroll_patterns = [
                lambda: self._scroll_by_amount(random.randint(800, 1500)),  # 2배 증가
                lambda: self._scroll_to_position_aggressive(),
                lambda: self._scroll_smoothly_aggressive()
            ]

            # 랜덤하게 스크롤 패턴 선택
            scroll_func = random.choice(scroll_patterns)
            scroll_func()

            # 짧은 대기 시간 (스크롤 후 즉시 처리)
            time.sleep(random.uniform(0.3, 0.6))

        except Exception as e:
            logger.debug(f"공격적 스크롤 실패: {e}")

    def _scroll_by_amount(self, amount):
        """일정량 스크롤"""
        self.driver.execute_script(f"window.scrollBy(0, {amount});")

    def _scroll_to_position(self):
        """특정 위치로 스크롤"""
        try:
            # 현재 스크롤 위치
            current_scroll = self.driver.execute_script("return window.pageYOffset")
            # 전체 높이의 60-90% 지점으로 스크롤
            total_height = self.driver.execute_script("return document.body.scrollHeight")
            target_position = int(total_height * random.uniform(0.6, 0.9))

            self.driver.execute_script(f"window.scrollTo(0, {target_position});")
        except:
            # 실패시 기본 스크롤
            self._scroll_by_amount(600)

    def _scroll_smoothly(self):
        """부드러운 스크롤"""
        try:
            # 작은 단위로 여러 번 스크롤하여 자연스러운 움직임 시뮬레이션
            scroll_amount = random.randint(200, 400)
            steps = random.randint(3, 6)

            for _ in range(steps):
                self.driver.execute_script(f"window.scrollBy(0, {scroll_amount // steps});")
                time.sleep(random.uniform(0.1, 0.3))
        except:
            # 실패시 기본 스크롤
            self._scroll_by_amount(400)

    def _scroll_to_position_aggressive(self):
        """🚀 공격적인 위치 스크롤 (더 큰 점프)"""
        try:
            # 현재 스크롤 위치
            current_scroll = self.driver.execute_script("return window.pageYOffset")
            # 전체 높이의 70-95% 지점으로 더 큰 점프
            total_height = self.driver.execute_script("return document.body.scrollHeight")
            target_position = int(total_height * random.uniform(0.7, 0.95))

            self.driver.execute_script(f"window.scrollTo(0, {target_position});")
        except:
            # 실패시 기본 스크롤
            self._scroll_by_amount(1000)

    def _scroll_smoothly_aggressive(self):
        """🚀 빠른 부드러운 스크롤 (더 큰 양을 빠르게)"""
        try:
            # 더 큰 스크롤 양을 빠르게 처리
            scroll_amount = random.randint(600, 1000)
            steps = random.randint(2, 4)  # 단계 수 줄임

            for _ in range(steps):
                self.driver.execute_script(f"window.scrollBy(0, {scroll_amount // steps});")
                time.sleep(random.uniform(0.05, 0.15))  # 더 짧은 대기
        except:
            # 실패시 기본 스크롤
            self._scroll_by_amount(800)

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
                    logger.warning("⚠️  CAPTCHA 감지: selector=%s, elements=%d", selector, len(elements))
                    return True

            return False

        except Exception:
            return False

    def _handle_captcha(self):
        """
        Phase 2: CAPTCHA 처리
        수동 해결 대기 (headless가 아닐 때만)
        헤드리스 모드에서는 자동으로 브라우저 모드로 전환 요청
        """
        if not self.headless:
            wait_seconds = 15
            logger.warning(f"⚠️  CAPTCHA가 감지되었습니다. {wait_seconds}초 동안 수동으로 해결해주세요...")
            time.sleep(wait_seconds)
            logger.info("✅ 대기 시간이 종료되었습니다. 계속 진행합니다.")
        else:
            logger.warning("⚠️  헤드리스 모드에서 CAPTCHA 감지됨. 브라우저 모드로 전환 필요")
            # 헤드리스 모드에서 CAPTCHA가 감지되면 예외 발생
            raise CaptchaDetectedException("헤드리스 모드에서 CAPTCHA 감지됨 - 브라우저 모드로 재시작 필요")

    def close(self):
        """드라이버 종료"""
        if self.driver:
            try:
                self.driver.quit()
                logger.info("✅ 드라이버 종료 완료")
            except Exception:
                pass
