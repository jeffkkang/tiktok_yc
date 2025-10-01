#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
비동기 틱톡 프로필 스크래퍼
"""

import re
import os
import time
import json
import random
import logging
import asyncio
import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from concurrent.futures import ThreadPoolExecutor

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("tiktok_scraper.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class TikTokProfile:
    """틱톡 프로필 정보를 저장하는 데이터 클래스"""
    username: str
    emails: List[str] = None
    follower_count: int = 0
    success: bool = False
    error: str = ""

    def __post_init__(self):
        if self.emails is None:
            self.emails = []

class EmailExtractor:
    """이메일 추출기"""
    
    @staticmethod
    def extract_emails(text: str) -> List[str]:
        """텍스트에서 이메일 추출"""
        email_pattern = r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"
        emails = re.findall(email_pattern, text)
        return list(set(emails))

    @staticmethod
    def is_valid_email(email: str) -> bool:
        """이메일 유효성 검사"""
        pattern = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
        return bool(re.match(pattern, email))

class AsyncTikTokScraper:
    def __init__(self, max_workers: int = 5, headless: bool = True):
        self.max_workers = max_workers
        self.headless = headless
        self.semaphore = asyncio.Semaphore(max_workers)
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.loop = asyncio.get_event_loop()
        
    async def setup_driver(self) -> webdriver.Chrome:
        """크롬 드라이버 설정"""
    options = Options()
        if self.headless:
            options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        driver.set_page_load_timeout(30)
        
        # 쿠키 로드 및 적용
        await self.load_cookies(driver)
        return driver
        
    async def load_cookies(self, driver: webdriver.Chrome):
        """쿠키 로드 및 적용"""
        try:
            await self.loop.run_in_executor(self.executor, driver.get, "https://www.tiktok.com")
            await asyncio.sleep(2)
            
            if os.path.exists("cookies.json"):
                with open("cookies.json", "r") as f:
                    cookies = json.load(f)
                    
                for cookie in cookies:
                    try:
                        await self.loop.run_in_executor(self.executor, driver.add_cookie, cookie)
                    except Exception:
                        continue
                
                await self.loop.run_in_executor(self.executor, driver.refresh)
                await asyncio.sleep(2)
            else:
                logger.error("cookies.json 파일을 찾을 수 없습니다.")
    except Exception as e:
            logger.error(f"쿠키 로드 중 오류: {str(e)}")

    def parse_count(self, count_text: str) -> int:
        """숫자 형식 파싱"""
        if not count_text:
            return 0
        
        count_text = count_text.strip().upper()
        multiplier = 1
        
        if 'K' in count_text:
            multiplier = 1000
            count_text = count_text.replace('K', '')
        elif 'M' in count_text:
            multiplier = 1000000
            count_text = count_text.replace('M', '')
        elif 'B' in count_text:
            multiplier = 1000000000
            count_text = count_text.replace('B', '')
            
        try:
            return int(float(count_text) * multiplier)
        except ValueError:
            return 0

    async def scrape_profile(self, username: str) -> TikTokProfile:
        """프로필 정보 스크래핑"""
    profile = TikTokProfile(username=username)
    driver = None
    
        try:
            async with self.semaphore:
                driver = await self.setup_driver()
            url = f"https://www.tiktok.com/@{username}"
                await self.loop.run_in_executor(self.executor, driver.get, url)
                await asyncio.sleep(random.uniform(1, 2))
            
                wait = WebDriverWait(driver, 10)
                
                # 팔로워 수 추출
                try:
                    follower_element = await self.loop.run_in_executor(
                        self.executor,
                        wait.until,
                        EC.presence_of_element_located((By.CSS_SELECTOR, "[data-e2e='followers-count']"))
                    )
                    profile.follower_count = self.parse_count(follower_element.text)
                except (TimeoutException, NoSuchElementException):
                    logger.warning(f"팔로워 수를 찾을 수 없음: @{username}")
                
                # 이메일 추출
                try:
                    # 프로필 설명에서 이메일 추출
                    bio_elements = await self.loop.run_in_executor(
                        self.executor,
                        driver.find_elements,
                        By.CSS_SELECTOR,
                        "[data-e2e='user-bio'], [data-e2e='user-page-header']"
                    )
                    
                    for element in bio_elements:
                        emails = EmailExtractor.extract_emails(element.text)
                        profile.emails.extend(emails)
                    
                    # 페이지 소스에서 이메일 추출
                    page_source = await self.loop.run_in_executor(self.executor, lambda: driver.page_source)
                    emails = EmailExtractor.extract_emails(page_source)
                    profile.emails.extend(emails)
                
                    # 중복 제거 및 유효성 검사
                    profile.emails = list(set([
                        email for email in profile.emails 
                        if EmailExtractor.is_valid_email(email)
                    ]))
                except Exception as e:
                    logger.warning(f"이메일 추출 중 오류: {str(e)}")
                
                profile.success = True
                
        except Exception as e:
            profile.error = str(e)
            logger.error(f"프로필 스크래핑 중 오류 (@{username}): {str(e)}")
        finally:
            if driver:
                await self.loop.run_in_executor(self.executor, driver.quit)
    
    return profile

async def save_results(profiles: List[TikTokProfile], output_file: str = "results.json"):
    """결과 저장"""
    try:
        # 기존 결과 로드 또는 새 리스트 생성
        results = []
        if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
            try:
                with open(output_file, 'r', encoding='utf-8') as f:
                    results = json.load(f)
                except json.JSONDecodeError:
                logger.warning(f"{output_file} 파일이 손상되었습니다. 새로 시작합니다.")
                results = []
            
        # 새로운 결과 추가
        for profile in profiles:
            results.append({
                "username": profile.username,
                "emails": profile.emails,
                "follower_count": profile.follower_count,
                "success": profile.success,
                "error": profile.error
            })
            
        # 파일 저장
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
            
        logger.info(f"결과가 {output_file}에 저장되었습니다.")
    except Exception as e:
        logger.error(f"결과 저장 중 오류: {str(e)}")

async def main():
    # 유저네임 로드
    if not os.path.exists("usernames.txt"):
        logger.error("usernames.txt 파일을 찾을 수 없습니다.")
        return
        
    with open("usernames.txt", "r", encoding='utf-8') as f:
            usernames = [line.strip() for line in f if line.strip()]
    
    if not usernames:
        logger.error("처리할 유저네임이 없습니다.")
        return
    
    logger.info(f"총 {len(usernames)}개의 유저네임을 처리합니다.")
    
    # 스크래퍼 초기화
    scraper = AsyncTikTokScraper(max_workers=5, headless=True)
    profiles = []
    batch_size = 10
    
    try:
    # 배치 단위로 처리
        for i in range(0, len(usernames), batch_size):
            batch = usernames[i:i+batch_size]
        logger.info(f"배치 처리 중: {i+1}-{i+len(batch)}/{len(usernames)}")
        
        # 배치 내 병렬 처리
            tasks = [scraper.scrape_profile(username) for username in batch]
            batch_results = await asyncio.gather(*tasks)
        
            # 결과 처리
            for profile in batch_results:
                profiles.append(profile)
            if profile.success:
                    logger.info(f"✓ @{profile.username}: 팔로워 {profile.follower_count:,}, 이메일 {len(profile.emails)}개")
            else:
                    logger.warning(f"✗ @{profile.username}: {profile.error}")
            
            # 배치 결과 저장
            await save_results(profiles)
            profiles = []
        
            # 배치 간 딜레이
            if i + batch_size < len(usernames):
                delay = random.uniform(2, 4)
            logger.info(f"다음 배치 전 {delay:.1f}초 대기 중...")
            await asyncio.sleep(delay)
    
    except KeyboardInterrupt:
        logger.info("\n사용자에 의해 중단되었습니다.")
    except Exception as e:
        logger.error(f"예상치 못한 오류: {str(e)}")
    finally:
        # 남은 결과 저장
        if profiles:
            await save_results(profiles)
        
        # 스레드 풀 종료
        scraper.executor.shutdown(wait=True)

if __name__ == "__main__":
    asyncio.run(main()) 