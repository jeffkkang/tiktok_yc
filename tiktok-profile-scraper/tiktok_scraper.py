#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
통합 TikTok 스크래퍼:
1. 해시태그 기반 인플루언서 검색
2. 프로필 정보 수집
"""

import re
import os
import time
import json
import random
import logging
import asyncio
import datetime
from typing import List, Dict, Any, Optional, Set, Tuple
from pathlib import Path
from dataclasses import dataclass, asdict, field
from config import Config

# Selenium 관련 임포트
import undetected_chromedriver as uc
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# 로깅 설정
logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL),
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(Config.LOG_DIR / "tiktok_scraper.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class HashtagResult:
    """해시태그 검색 결과를 저장하는 데이터 클래스"""
    hashtag: str
    usernames: List[str] = field(default_factory=list)
    last_updated: str = field(default_factory=lambda: datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    total_collected: int = 0

@dataclass
class TikTokProfile:
    """틱톡 프로필 정보를 저장하는 데이터 클래스"""
    username: str
    emails: List[str] = field(default_factory=list)
    bio: str = ""
    follower_count: int = 0
    following_count: int = 0
    likes_count: int = 0
    video_count: int = 0
    social_links: Dict[str, str] = field(default_factory=dict)
    region: str = ""
    geo: str = ""
    scraped_at: str = field(default_factory=lambda: datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    success: bool = False
    error: str = ""

class TikTokScraper:
    def __init__(self):
        self.config = Config
        self.setup_driver()
        self.collected_data = self.load_collected_data()
    
    def setup_driver(self):
        """크롬 드라이버 설정"""
        options = uc.ChromeOptions()
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--lang=en")
        options.add_argument("--start-maximized")
        
        if self.config.DEBUG:
            options.add_argument("--auto-open-devtools-for-tabs")
        else:
            options.add_argument("--headless=new")
        
        self.driver = uc.Chrome(options=options)
        self.wait = WebDriverWait(self.driver, 20)
        
        # 쿠키 설정
        self.apply_cookies()
    
    def apply_cookies(self):
        """쿠키 적용"""
        try:
            self.driver.get("https://www.tiktok.com")
            time.sleep(3)
            
            cookies = self.config.get_cookies()
            if not cookies:
                raise ValueError("쿠키가 설정되지 않았습니다.")
            
            for cookie in cookies:
                if all(k in cookie for k in ["name", "value", "domain"]):
                    self.driver.add_cookie(cookie)
            
            self.driver.refresh()
            time.sleep(3)
            logger.info("쿠키 적용 완료")
            
        except Exception as e:
            logger.error(f"쿠키 적용 실패: {str(e)}")
            raise
    
    def load_collected_data(self) -> Dict[str, Any]:
        """수집된 데이터 로드"""
        data_file = self.config.OUTPUT_DIR / "collected_data.json"
        try:
            if data_file.exists():
                with open(data_file, "r", encoding='utf-8') as f:
                    return json.load(f)
            return {"hashtags": {}}
        except Exception as e:
            logger.error(f"데이터 로드 실패: {str(e)}")
            return {"hashtags": {}}
    
    def save_collected_data(self):
        """수집된 데이터 저장"""
        data_file = self.config.OUTPUT_DIR / "collected_data.json"
        try:
            with open(data_file, "w", encoding='utf-8') as f:
                json.dump(self.collected_data, f, ensure_ascii=False, indent=2)
            logger.info("데이터 저장 완료")
        except Exception as e:
            logger.error(f"데이터 저장 실패: {str(e)}")
    
    async def search_hashtag(self, hashtag: str, max_users: int = 100) -> HashtagResult:
        """해시태그 검색 및 유저네임 수집"""
        result = HashtagResult(hashtag=hashtag)
        
        if hashtag in self.collected_data["hashtags"]:
            existing_data = self.collected_data["hashtags"][hashtag]
            result.usernames = existing_data.get("usernames", [])
            logger.info(f"기존 수집 데이터 발견: {len(result.usernames)}개")
        
        try:
            self.driver.get(f"https://www.tiktok.com/tag/{hashtag}")
            await asyncio.sleep(5)
            
            new_usernames = set()
            last_height = self.driver.execute_script("return document.body.scrollHeight")
            scroll_attempts = 0
            max_scroll_attempts = 20
            
            while scroll_attempts < max_scroll_attempts:
                try:
                    video_containers = self.wait.until(EC.presence_of_all_elements_located(
                        (By.CSS_SELECTOR, "div[data-e2e='challenge-item-list'] > div")))
                    
                    for container in video_containers:
                        try:
                            author_element = container.find_element(By.CSS_SELECTOR, "a[href*='/@']")
                            username = author_element.get_attribute("href").split("/@")[-1].split("?")[0]
                            
                            if username and username not in result.usernames:
                                new_usernames.add(username)
                                logger.info(f"새로운 유저네임 발견: {username}")
                        except Exception:
                            continue
                    
                    self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    await asyncio.sleep(random.uniform(*self.config.get_request_delay()))
                    
                    new_height = self.driver.execute_script("return document.body.scrollHeight")
                    if new_height == last_height:
                        scroll_attempts += 1
                    else:
                        scroll_attempts = 0
                        last_height = new_height
                    
                    if len(new_usernames) + len(result.usernames) >= max_users:
                        break
                        
                except Exception as e:
                    logger.error(f"스크롤 중 오류: {str(e)}")
                    scroll_attempts += 1
                    continue
            
            # 새로운 유저네임 추가
            result.usernames.extend(list(new_usernames))
            result.total_collected = len(result.usernames)
            
            # 데이터 저장
            self.collected_data["hashtags"][hashtag] = asdict(result)
            self.save_collected_data()
            
            return result
            
        except Exception as e:
            logger.error(f"해시태그 검색 실패: {str(e)}")
            return result

    async def scrape_profile(self, username: str) -> TikTokProfile:
        """프로필 정보 수집"""
        profile = TikTokProfile(username=username)
        
        for retry in range(self.config.MAX_RETRIES):
            try:
                url = f"https://www.tiktok.com/@{username}"
                self.driver.get(url)
                await asyncio.sleep(random.uniform(*self.config.get_request_delay()))
                
                # 페이지 로드 확인
                if "Page Not Found" in self.driver.title:
                    profile.error = f"사용자를 찾을 수 없음: @{username}"
                    return profile
                
                # 프로필 정보 추출
                try:
                    # 프로필 설명
                    bio_elements = self.driver.find_elements(By.CSS_SELECTOR, "[data-e2e='user-bio'], [data-e2e='user-page-header']")
                    if bio_elements:
                        profile.bio = " ".join([el.text for el in bio_elements])
                    
                    # 팔로워 수
                    follower_element = self.driver.find_element(By.CSS_SELECTOR, "[data-e2e='followers-count']")
                    profile.follower_count = self.parse_count(follower_element.text)
                    
                    # 팔로잉 수
                    following_element = self.driver.find_element(By.CSS_SELECTOR, "[data-e2e='following-count']")
                    profile.following_count = self.parse_count(following_element.text)
                    
                    # 좋아요 수
                    likes_element = self.driver.find_element(By.CSS_SELECTOR, "[data-e2e='likes-count']")
                    profile.likes_count = self.parse_count(likes_element.text)
                    
                    # 이메일 추출
                    if profile.bio:
                        profile.emails = self.extract_emails(profile.bio)
                    
                    profile.success = True
                    logger.info(f"프로필 수집 성공: @{username}")
                    break
                    
                except Exception as e:
                    logger.error(f"프로필 정보 추출 실패: {str(e)}")
                    if retry < self.config.MAX_RETRIES - 1:
                        await asyncio.sleep(random.uniform(1, 3))
                    continue
                
            except Exception as e:
                profile.error = f"프로필 수집 실패: {str(e)}"
                logger.error(f"프로필 수집 오류: {str(e)}")
                if retry < self.config.MAX_RETRIES - 1:
                    await asyncio.sleep(random.uniform(1, 3))
                continue
        
        return profile

    @staticmethod
    def parse_count(count_text: str) -> int:
        """숫자 형식 파싱"""
        if not count_text:
            return 0
        
        count_text = count_text.strip().upper()
        if 'K' in count_text:
            return int(float(count_text.replace('K', '')) * 1000)
        elif 'M' in count_text:
            return int(float(count_text.replace('M', '')) * 1000000)
        elif 'B' in count_text:
            return int(float(count_text.replace('B', '')) * 1000000000)
        else:
            return int(count_text.replace(',', '').replace('.', ''))

    @staticmethod
    def extract_emails(text: str) -> List[str]:
        """이메일 주소 추출"""
        email_pattern = r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"
        emails = re.findall(email_pattern, text)
        return list(set(emails))

    async def process_hashtags(self, hashtags: List[str], max_users_per_tag: int = 100):
        """여러 해시태그 처리"""
        for hashtag in hashtags:
            logger.info(f"\n해시태그 처리 시작: #{hashtag}")
            result = await self.search_hashtag(hashtag, max_users_per_tag)
            logger.info(f"해시태그 #{hashtag} 처리 완료: {result.total_collected}개 유저네임 수집")
    
    async def process_profiles(self, usernames: List[str]):
        """여러 프로필 처리"""
        results_file = self.config.OUTPUT_DIR / "profile_results.json"
        
        for i in range(0, len(usernames), self.config.BATCH_SIZE):
            batch = usernames[i:i + self.config.BATCH_SIZE]
            logger.info(f"\n배치 처리 시작: {i+1}-{i+len(batch)}/{len(usernames)}")
            
            for username in batch:
                profile = await self.scrape_profile(username)
                
                # 결과 저장
                try:
                    if results_file.exists():
                        with open(results_file, 'r', encoding='utf-8') as f:
                            results = json.load(f)
                    else:
                        results = []
                    
                    results.append(asdict(profile))
                    
                    with open(results_file, 'w', encoding='utf-8') as f:
                        json.dump(results, f, ensure_ascii=False, indent=2)
                    
                except Exception as e:
                    logger.error(f"결과 저장 실패: {str(e)}")
            
            # 배치 간 딜레이
            if i + self.config.BATCH_SIZE < len(usernames):
                await asyncio.sleep(random.uniform(3, 5))
    
    def close(self):
        """드라이버 종료"""
        if hasattr(self, 'driver'):
            self.driver.quit()

async def main():
    scraper = TikTokScraper()
    try:
        # 환경 변수에서 해시태그 로드
        hashtags_str = os.getenv('HASHTAGS', 'beauty,skincare,makeup')
        hashtags = [tag.strip() for tag in hashtags_str.split(',') if tag.strip()]
        logger.info(f"처리할 해시태그: {hashtags}")
        
        # 해시태그 처리
        await scraper.process_hashtags(hashtags)
        
        # 수집된 모든 유저네임 추출
        all_usernames = set()
        for hashtag_data in scraper.collected_data["hashtags"].values():
            all_usernames.update(hashtag_data.get("usernames", []))
        
        logger.info(f"총 {len(all_usernames)}개의 유니크한 유저네임 수집됨")
        
        # 프로필 수집
        await scraper.process_profiles(list(all_usernames))
        
    except Exception as e:
        logger.error(f"실행 중 오류 발생: {str(e)}")
    finally:
        scraper.close()

if __name__ == "__main__":
    asyncio.run(main()) 