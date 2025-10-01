#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Profile scraping module for TikTok keyword scraper
Handles creator profile extraction and email discovery
"""

import time
import random
import logging
from typing import Dict, Any, List
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from .email import EmailExtractor
from .utils import parse_count, random_delay, retry_on_failure

logger = logging.getLogger(__name__)


class ProfileScraper:
    """TikTok 크리에이터 프로필 스크래퍼"""

    def __init__(self, driver, delay_min: float = 1.5, delay_max: float = 3.0):
        """
        Initialize profile scraper

        Args:
            driver: Selenium WebDriver 인스턴스
            delay_min: 최소 지연 시간
            delay_max: 최대 지연 시간
        """
        self.driver = driver
        self.delay_min = delay_min
        self.delay_max = delay_max
        self.email_extractor = EmailExtractor()

    @retry_on_failure(max_retries=2, delay=3)
    def fetch_creator_profile(self, username: str) -> Dict[str, Any]:
        """
        크리에이터 프로필 조회

        Args:
            username: TikTok 사용자명

        Returns:
            Dict[str, Any]: 프로필 데이터
        """
        logger.info(f"  📥 프로필 조회: @{username}")

        profile_data = {
            "username": username,
            "emails": [],
            "follower_count": 0,
            "bio": "",
            "success": False,
            "error": ""
        }

        try:
            # 프로필 페이지 접속
            url = f"https://www.tiktok.com/@{username}"
            self.driver.get(url)
            random_delay(self.delay_min, self.delay_max)

            # 페이지 존재 확인
            page_title = self.driver.title
            if "Page Not Found" in page_title or "찾을 수 없음" in page_title:
                profile_data["error"] = "User not found"
                logger.warning(f"  ⚠️  사용자를 찾을 수 없음: @{username}")
                return profile_data

            # 인간스러운 스크롤 (봇 감지 회피)
            self._human_like_scroll()

            # 데이터 추출
            profile_data["follower_count"] = self._extract_follower_count()
            profile_data["bio"] = self._extract_bio()
            profile_data["emails"] = self._extract_emails(profile_data["bio"])

            profile_data["success"] = True
            logger.info(f"  ✅ @{username}: 팔로워 {profile_data['follower_count']:,}, 이메일 {len(profile_data['emails'])}개")

        except Exception as e:
            profile_data["error"] = str(e)
            logger.error(f"  ❌ 프로필 조회 실패 (@{username}): {str(e)}")

        return profile_data

    def _human_like_scroll(self):
        """인간스러운 스크롤 패턴 (봇 감지 회피)"""
        try:
            # 랜덤한 스크롤 패턴
            for _ in range(random.randint(2, 4)):
                scroll_height = random.randint(100, 400)
                self.driver.execute_script(f"window.scrollTo(0, {scroll_height});")
                time.sleep(random.uniform(0.3, 0.8))

            # 가끔 위로 스크롤 (더 인간적)
            if random.random() < 0.3:
                self.driver.execute_script("window.scrollTo(0, 0);")
                time.sleep(random.uniform(0.2, 0.5))

        except Exception as e:
            logger.debug(f"스크롤 중 오류 (무시): {e}")

    def _extract_follower_count(self) -> int:
        """
        팔로워 수 추출 (여러 셀렉터 시도)

        Returns:
            int: 팔로워 수
        """
        selectors = [
            "[data-e2e='followers-count']",
            "[data-e2e='follower-count']",
            "[title*='Followers']",
            "strong[data-e2e='followers-count']",
        ]

        for selector in selectors:
            try:
                element = self.driver.find_element(By.CSS_SELECTOR, selector)
                count = parse_count(element.text)
                if count > 0:
                    return count
            except NoSuchElementException:
                continue

        logger.debug(f"  ⚠️  팔로워 수를 찾을 수 없음")
        return 0

    def _extract_bio(self) -> str:
        """
        프로필 설명(Bio) 추출

        Returns:
            str: Bio 텍스트
        """
        selectors = [
            "[data-e2e='user-bio']",
            "[data-e2e='user-page-header']",
            ".tiktok-bio",
            "h2[data-e2e='user-subtitle']",
        ]

        bio_text = ""

        try:
            # 대기 후 추출
            WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, selectors[0]))
            )
        except TimeoutException:
            pass

        # 여러 셀렉터 시도
        for selector in selectors:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    bio_text += " ".join([el.text for el in elements if el.text])
            except Exception:
                continue

        return bio_text.strip()

    def _extract_emails(self, bio_text: str) -> List[str]:
        """
        이메일 추출 (여러 방법 시도)

        Args:
            bio_text: Bio 텍스트

        Returns:
            List[str]: 이메일 리스트
        """
        emails = []

        # 방법 1: Bio 텍스트에서 추출
        if bio_text:
            bio_emails = self.email_extractor.extract_emails(bio_text)
            emails.extend(bio_emails)

        # 방법 2: mailto 링크에서 추출
        try:
            mailto_links = self.driver.find_elements(By.CSS_SELECTOR, "a[href*='mailto:']")
            for link in mailto_links:
                href = link.get_attribute('href')
                if href and 'mailto:' in href:
                    email = href.replace('mailto:', '').strip()
                    if self.email_extractor.is_valid_email(email) and email not in emails:
                        emails.append(email)
        except Exception as e:
            logger.debug(f"mailto 링크 추출 실패: {e}")

        # 방법 3: 페이지 소스에서 추출 (마지막 수단)
        try:
            page_source = self.driver.page_source
            source_emails = self.email_extractor.extract_emails(page_source)
            for email in source_emails[:5]:  # 최대 5개만 (노이즈 방지)
                if email not in emails:
                    emails.append(email)
        except Exception as e:
            logger.debug(f"페이지 소스 추출 실패: {e}")

        # 최종 정제 및 중복 제거
        unique_emails = []
        for email in emails:
            if self.email_extractor.is_valid_email(email) and email not in unique_emails:
                unique_emails.append(email)

        return unique_emails
