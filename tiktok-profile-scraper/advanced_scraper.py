#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
고급 틱톡 스크래퍼: 하루 1000개 계정 처리 가능
"""

import re
import os
import time
import json
import random
import logging
import asyncio
import datetime
import argparse
import traceback
import aiohttp
import aiofiles
from typing import List, Dict, Any, Optional, Set, Tuple
from pathlib import Path
from urllib.parse import urlparse
from dataclasses import dataclass, asdict, field
from concurrent.futures import ThreadPoolExecutor

# Selenium 관련 임포트
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager

# 프록시 서비스 연동 (여기에서는 예시로만 포함)
# pip install proxy-requests
try:
    from proxy_requests import ProxyRequests, ProxyList
    PROXY_AVAILABLE = True
except ImportError:
    PROXY_AVAILABLE = False

# 멀티프로세싱 도구
import multiprocessing
from multiprocessing import Pool, Manager

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

# 데이터 클래스 정의
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
    region: str = ""  # 사용자의 지역 (예: Singapore-Central)
    geo: str = ""     # 지리적 위치 (예: VGeo-ROW)
    scraped_at: str = field(default_factory=lambda: datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    success: bool = False
    error: str = ""

# 설정 클래스
@dataclass
class ScraperConfig:
    """스크래퍼 설정"""
    usernames_file: str = "usernames.txt"
    output_file: str = "tiktok_results.json"
    cookies_file: str = "cookies.json"
    proxy_file: str = "proxies.txt"
    concurrent_workers: int = 10
    request_delay: Tuple[float, float] = (1.0, 3.0)
    proxy_enabled: bool = False
    headless: bool = True
    debug: bool = False
    max_retries: int = 3
    batch_size: int = 100

class ProxyManager:
    """프록시 관리자"""
    
    def __init__(self, proxy_file: str):
        self.proxy_file = proxy_file
        self.proxies = []
        self.current_index = 0
        self.lock = asyncio.Lock()
        self._load_proxies()
    
    def _load_proxies(self):
        """프록시 목록 로드"""
        try:
            if os.path.exists(self.proxy_file):
                with open(self.proxy_file, 'r') as f:
                    self.proxies = [line.strip() for line in f if line.strip()]
                logger.info(f"{len(self.proxies)}개 프록시 로드 완료")
            else:
                logger.warning(f"프록시 파일 {self.proxy_file}을 찾을 수 없음. 프록시 없이 실행됩니다.")
        except Exception as e:
            logger.error(f"프록시 로드 실패: {e}")
    
    async def get_proxy(self) -> Optional[str]:
        """다음 프록시 가져오기"""
        if not self.proxies:
            return None
        
        async with self.lock:
            proxy = self.proxies[self.current_index]
            self.current_index = (self.current_index + 1) % len(self.proxies)
            return proxy
    
    def size(self) -> int:
        """프록시 개수 반환"""
        return len(self.proxies)

class CookieManager:
    """쿠키 관리자"""
    
    def __init__(self, cookies_file: str):
        self.cookies_file = cookies_file
        self.cookies_list = []
        self.current_index = 0
        self.lock = asyncio.Lock()
        self._load_cookies()
    
    def _load_cookies(self):
        """쿠키 파일 로드"""
        try:
            if os.path.exists(self.cookies_file):
                with open(self.cookies_file, 'r') as f:
                    cookie_objects = json.load(f)
                    if isinstance(cookie_objects, list):
                        # cookies.json 형식 (list of objects with name/value pairs)
                        cookies_dict = {}
                        for cookie in cookie_objects:
                            if "name" in cookie and "value" in cookie:
                                cookies_dict[cookie["name"]] = cookie["value"]
                        if cookies_dict:
                            self.cookies_list = [cookies_dict]
                        else:
                            logger.warning(f"{self.cookies_file}에서 유효한 쿠키를 찾을 수 없습니다. 기본 쿠키를 사용합니다.")
                            self._set_default_cookies()
                    else:
                        # 이전 형식 (dictionary of cookies)
                        self.cookies_list = [cookie_objects]
                logger.info(f"{len(self.cookies_list)}개 쿠키 세트 로드 완료")
            else:
                logger.warning(f"쿠키 파일 {self.cookies_file}을 찾을 수 없음. 기본 쿠키가 사용됩니다.")
                self._set_default_cookies()
        except Exception as e:
            logger.error(f"쿠키 로드 실패: {e}")
            self._set_default_cookies()
    
    def _set_default_cookies(self):
        """기본 쿠키 값 설정"""
        self.cookies_list = [{
            "sessionid": "a40d3c265d440d5daa789f1ab45d96f3",
            "sid_tt": "a40d3c265d440d5daa789f1ab45d96f3",
            "uid_tt": "aa57595c2a6adb9ddef2fc9543172166fb00ed24dff6beea68bbaf6665479142",
            "ttwid": "1%7CgnLiIg1QFIFQ1IqdTJ7wJgUipen71X6l2YxQqJ1JImA%7C1747483405%7C042c2d46aceacaa76fe864d1def93b6d4b88e48994f39afd287c193745e396b0"
        }]
    
    async def get_cookies(self) -> Dict[str, str]:
        """다음 쿠키 세트 가져오기"""
        if not self.cookies_list:
            return {}
        
        async with self.lock:
            cookies = self.cookies_list[self.current_index]
            self.current_index = (self.current_index + 1) % len(self.cookies_list)
            return cookies
    
    def format_for_selenium(self, cookies: Dict[str, str]) -> List[Dict[str, Any]]:
        """Selenium 형식으로 쿠키 변환"""
        result = []
        for name, value in cookies.items():
            result.append({
                "name": name,
                "value": value,
                "domain": ".tiktok.com"
            })
        return result

class EmailExtractor:
    """이메일 추출기"""
    
    @staticmethod
    def extract_emails(text: str) -> List[str]:
        """텍스트에서 이메일 추출"""
        email_pattern = r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"
        emails = re.findall(email_pattern, text)
        
        # 중복 제거 및 정제
        clean_emails = []
        for email in emails:
            # 점(.) 뒤에 붙은 추가 텍스트 제거 (예: email@domain.com.username)
            if email.count('.') > 1:
                parts = email.split('.')
                domain_parts = []
                for i, part in enumerate(parts):
                    domain_parts.append(part)
                    if i > 0 and len(part) >= 2 and len(part) <= 4:  # 일반적인 최상위 도메인 길이
                        clean_email = '.'.join(domain_parts)
                        if clean_email not in clean_emails and '@' in clean_email:
                            clean_emails.append(clean_email)
                        break
            
            # 'n'으로 시작하는 오류 수정 (예: nemail@domain.com -> email@domain.com)
            if email.startswith('n') and email.count('@') == 1 and email[1:] not in clean_emails:
                clean_emails.append(email[1:])
            
            # 원본 이메일 추가
            if email not in clean_emails and '@' in email:
                clean_emails.append(email)
        
        # 숨겨진 이메일 형식 추출 (예: user [at] domain [dot] com)
        obscured_pattern = r'\b[a-zA-Z0-9_.+-]+\s*[\[\(]at[\]\)]\s*[a-zA-Z0-9-]+\s*[\[\(]dot[\]\)]\s*[a-zA-Z0-9-.]+\b'
        obscured_matches = re.findall(obscured_pattern, text, re.IGNORECASE)
        
        for match in obscured_matches:
            clean_email = match.replace('[at]', '@').replace('(at)', '@').replace('[dot]', '.').replace('(dot)', '.')
            clean_email = re.sub(r'\s+', '', clean_email)
            if '@' in clean_email and '.' in clean_email and clean_email not in clean_emails:
                clean_emails.append(clean_email)
        
        return clean_emails

    @staticmethod
    def is_valid_email(email: str) -> bool:
        """이메일 유효성 검사"""
        pattern = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
        return bool(re.match(pattern, email))

async def setup_selenium_driver(config: ScraperConfig, cookie_manager: CookieManager, proxy: Optional[str] = None) -> webdriver.Chrome:
    """Selenium 드라이버 초기화"""
    options = Options()
    options.add_argument("--disable-blink-features=AutomationControlled")
    
    # 무작위 User-Agent 선택
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:94.0) Gecko/20100101 Firefox/94.0"
    ]
    user_agent = random.choice(user_agents)
    options.add_argument(f"user-agent={user_agent}")
    
    # 봇 감지 우회 옵션
    options.add_experimental_option('excludeSwitches', ['enable-automation'])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-popup-blocking")
    
    # 헤드리스 모드 (UI 없음)
    if config.headless:
        options.add_argument("--headless=new")
    
    # 프록시 설정
    if proxy:
        options.add_argument(f'--proxy-server={proxy}')
    
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        
        # 타임아웃 설정
        driver.set_page_load_timeout(30)
        
        # 초기 페이지 로드
        driver.get("https://www.tiktok.com")
        await asyncio.sleep(random.uniform(*config.request_delay))
        
        # 봇 감지 우회 스크립트
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        # 로컬 스토리지 항목 설정
        local_storage_items = {
            "SLARDARtiktok_webapp": "JTdCJTIydXNlcklkJTIyOiUyMjc0ODkwNzQ5MDM4NjI3NDA0OTclMjIsJTIyZGV2aWNlSWQlMjI6JTIyMjhkYWRjYjQtMDZlZi00ZjYwLTgxMWQtMzM1NDM3OTNiZmFmJTIyLCUyMmV4cGlyZXMlMjI6MTc1NTI0MjIxNDQ5NCU3RA==",
            "__tea_cache_tokens_1988": "{\"web_id\":\"7489074903862740497\",\"user_unique_id\":\"7489074903862740497\",\"timestamp\":1747466214846,\"_type_\":\"default\"}"
        }
        for key, value in local_storage_items.items():
            driver.execute_script(f"localStorage.setItem('{key}', '{value}');")
        
        # 쿠키 설정 전에 스토리지 초기화
        driver.execute_script("window.localStorage.clear()")
        driver.execute_script("window.sessionStorage.clear()")
        
        # 사람처럼 마우스 움직임
        driver.execute_script("document.body.dispatchEvent(new MouseEvent('mousemove', {'clientX': 100, 'clientY': 100}))")
        
        # 쿠키 추가
        cookies = await cookie_manager.get_cookies()
        selenium_cookies = cookie_manager.format_for_selenium(cookies)
        
        for cookie in selenium_cookies:
            try:
                driver.add_cookie(cookie)
            except Exception as e:
                logger.debug(f"쿠키 추가 실패 ({cookie['name']}): {str(e)}")
        
        # 페이지 새로고침으로 쿠키 적용
        driver.refresh()
        await asyncio.sleep(random.uniform(*config.request_delay))
        
        return driver
    except Exception as e:
        logger.error(f"드라이버 설정 중 오류 발생: {str(e)}")
        raise

async def scrape_profile_with_selenium(username: str, config: ScraperConfig, cookie_manager: CookieManager, proxy_manager: ProxyManager) -> TikTokProfile:
    """셀레니움을 사용한 프로필 스크래핑"""
    profile = TikTokProfile(username=username)
    driver = None
    
    for retry in range(config.max_retries):
        try:
            # 프록시 가져오기
            proxy = await proxy_manager.get_proxy() if config.proxy_enabled and proxy_manager.size() > 0 else None
            
            # 셀레니움 드라이버 초기화
            driver = await setup_selenium_driver(config, cookie_manager, proxy)
            
            # 프로필 페이지 접속
            url = f"https://www.tiktok.com/@{username}"
            logger.info(f"프로필 URL 접속 중: {url}")
            driver.get(url)
            await asyncio.sleep(random.uniform(*config.request_delay))
            
            # 페이지 로드 확인
            page_title = driver.title
            if "Page Not Found" in page_title or "찾을 수 없음" in page_title:
                profile.error = f"사용자를 찾을 수 없음: @{username}"
                logger.warning(profile.error)
                return profile
            
            # 접속 후 인간스러운 스크롤 동작
            for i in range(2):
                scroll_height = random.randint(100, 300)
                driver.execute_script(f"window.scrollTo(0, {scroll_height});")
                await asyncio.sleep(random.uniform(0.3, 0.8))
            
            # 프로필 정보 추출
            try:
                # 프로필 설명
                try:
                    WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "[data-e2e='user-bio'], [data-e2e='user-page-header']"))
                    )
                    bio_elements = driver.find_elements(By.CSS_SELECTOR, "[data-e2e='user-bio'], [data-e2e='user-page-header']")
                    if bio_elements:
                        bio_text = " ".join([el.text for el in bio_elements])
                        profile.bio = bio_text
                except TimeoutException:
                    pass
                
                # 팔로워 및 팔로잉 수
                try:
                    follower_element = driver.find_element(By.CSS_SELECTOR, "[data-e2e='followers-count']")
                    profile.follower_count = parse_count(follower_element.text)
                except NoSuchElementException:
                    pass
                
                try:
                    following_element = driver.find_element(By.CSS_SELECTOR, "[data-e2e='following-count']")
                    profile.following_count = parse_count(following_element.text)
                except NoSuchElementException:
                    pass
                
                # 좋아요 수
                try:
                    likes_element = driver.find_element(By.CSS_SELECTOR, "[data-e2e='likes-count']")
                    profile.likes_count = parse_count(likes_element.text)
                except NoSuchElementException:
                    pass
                
                # 비디오 수
                try:
                    video_element = driver.find_element(By.CSS_SELECTOR, "[data-e2e='video-count']")
                    profile.video_count = parse_count(video_element.text)
                except NoSuchElementException:
                    pass
                
                # 소셜 미디어 링크 추출
                social_links = driver.find_elements(By.CSS_SELECTOR, "a[href*='instagram.com'], a[href*='twitter.com'], a[href*='facebook.com']")
                for link in social_links:
                    href = link.get_attribute('href')
                    if href:
                        domain = urlparse(href).netloc.replace('www.', '')
                        platform = domain.split('.')[0]
                        profile.social_links[platform] = href
                
                # 이메일 추출 - 방법 1: 프로필 텍스트에서
                if profile.bio:
                    bio_emails = EmailExtractor.extract_emails(profile.bio)
                    profile.emails.extend(bio_emails)
                
                # 지역 정보 추출
                try:
                    region_script = driver.find_element(By.ID, "service-region")
                    if region_script:
                        region_data = json.loads(region_script.get_attribute('innerHTML'))
                        profile.region = region_data.get('vregion', '')
                        profile.geo = region_data.get('vgeo', '')
                        logger.info(f"지역 정보 추출: {profile.region}, {profile.geo}")
                except Exception as e:
                    logger.debug(f"지역 정보 추출 실패: {str(e)}")
                
                # 방법 2: mailto 링크에서
                mailto_links = driver.find_elements(By.CSS_SELECTOR, "a[href*='mailto:']")
                for link in mailto_links:
                    href = link.get_attribute('href')
                    if href and 'mailto:' in href:
                        email = href.replace('mailto:', '')
                        if email not in profile.emails:
                            profile.emails.append(email)
                
                # 방법 3: 페이지 소스에서
                page_source = driver.page_source
                source_emails = EmailExtractor.extract_emails(page_source)
                for email in source_emails:
                    if email not in profile.emails:
                        profile.emails.append(email)
                
                # 최종 이메일 정제
                profile.emails = [email for email in profile.emails if EmailExtractor.is_valid_email(email)]
                
                profile.success = True
                logger.info(f"✅ 프로필 스크래핑 성공: @{username}, 이메일: {profile.emails}")
                break
                
            except Exception as e:
                profile.error = f"프로필 정보 추출 실패: {str(e)}"
                logger.error(f"프로필 정보 추출 중 오류: {str(e)}")
                if retry < config.max_retries - 1:
                    logger.info(f"재시도 중... ({retry + 1}/{config.max_retries})")
                    await asyncio.sleep(random.uniform(1, 3))
                continue
                
        except Exception as e:
            profile.error = f"셀레니움 에러: {str(e)}"
            logger.error(f"셀레니움 에러: {str(e)}")
            if config.debug:
                logger.debug(traceback.format_exc())
            if retry < config.max_retries - 1:
                logger.info(f"재시도 중... ({retry + 1}/{config.max_retries})")
                await asyncio.sleep(random.uniform(1, 3))
            continue
            
        finally:
            if driver:
                try:
                    driver.quit()
                except Exception:
                    pass
    
    return profile

def parse_count(count_text: str) -> int:
    """숫자 형식 파싱 ('1.2K', '1.2M' 등)"""
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
        # 쉼표 제거 및 정수 변환
        return int(count_text.replace(',', '').replace('.', ''))

async def save_profile(profile: TikTokProfile, output_file: str):
    """프로필 정보 저장"""
    try:
        # 파일 존재 여부 확인
        file_exists = os.path.exists(output_file)
        
        # 파일 잠금을 위한 비동기 처리
        async with aiofiles.open(output_file, 'r+' if file_exists else 'w+') as f:
            if file_exists:
                content = await f.read()
                try:
                    data = json.loads(content) if content.strip() else []
                except json.JSONDecodeError:
                    logger.error(f"JSON 파싱 오류, 파일을 초기화합니다: {output_file}")
                    data = []
            else:
                data = []
            
            # 프로필 추가
            data.append(asdict(profile))
            
            # 파일 처음으로 되돌아가서 내용 덮어쓰기
            await f.seek(0)
            await f.write(json.dumps(data, indent=2, ensure_ascii=False))
            await f.truncate()
            
        logger.debug(f"프로필 저장 완료: @{profile.username}")
        return True
    except Exception as e:
        logger.error(f"프로필 저장 실패: {str(e)}")
        return False

async def process_batch(usernames: List[str], config: ScraperConfig, cookie_manager: CookieManager, proxy_manager: ProxyManager):
    """배치 작업 처리"""
    tasks = []
    results = []
    
    for username in usernames:
        # 사용자명 정제 (@ 기호 제거)
        username = username.strip('@').strip()
        if not username:
            continue
            
        # 스크래핑 작업 예약
        task = asyncio.create_task(scrape_profile_with_selenium(
            username, config, cookie_manager, proxy_manager
        ))
        tasks.append(task)
        
        # 요청 간격 주기 (방화벽 우회)
        await asyncio.sleep(random.uniform(0.1, 0.3))
    
    # 모든 작업 완료 대기
    for task in asyncio.as_completed(tasks):
        profile = await task
        results.append(profile)
        
        # 결과 저장
        await save_profile(profile, config.output_file)
    
    return results

async def run_scraper(config: ScraperConfig):
    """스크래퍼 실행"""
    logger.info(f"틱톡 스크래퍼 시작 (동시 작업자: {config.concurrent_workers})")
    
    # 관리자 초기화
    cookie_manager = CookieManager(config.cookies_file)
    proxy_manager = ProxyManager(config.proxy_file)
    
    # 사용자명 로드
    usernames = []
    try:
        with open(config.usernames_file, 'r') as f:
            usernames = [line.strip() for line in f if line.strip()]
        logger.info(f"{len(usernames)}개 사용자명 로드 완료")
    except Exception as e:
        logger.error(f"사용자명 파일 로드 실패: {str(e)}")
        return
    
    # 출력 파일 초기화
    if not os.path.exists(config.output_file):
        with open(config.output_file, 'w') as f:
            f.write('[]')
    
    # 배치 처리
    total_success = 0
    total_failed = 0
    
    # 배치 단위로 처리
    for i in range(0, len(usernames), config.batch_size):
        batch = usernames[i:i+config.batch_size]
        logger.info(f"배치 처리 중: {i+1}-{i+len(batch)}/{len(usernames)}")
        
        # 여러 작업 동시 실행 (세마포어 사용)
        semaphore = asyncio.Semaphore(config.concurrent_workers)
        
        async def bounded_process(username):
            async with semaphore:
                return await scrape_profile_with_selenium(username, config, cookie_manager, proxy_manager)
        
        # 배치 내 병렬 처리
        tasks = [bounded_process(username.strip('@').strip()) for username in batch if username.strip()]
        results = await asyncio.gather(*tasks)
        
        # 결과 저장 및 통계
        for profile in results:
            await save_profile(profile, config.output_file)
            if profile.success:
                total_success += 1
            else:
                total_failed += 1
        
        # 일부러 지연시간 추가 (너무 과도한 요청 방지)
        if i + config.batch_size < len(usernames):
            delay = random.uniform(3, 5)
            logger.info(f"다음 배치 전 {delay:.1f}초 대기 중...")
            await asyncio.sleep(delay)
    
    # 결과 요약
    logger.info("="*50)
    logger.info("스크래핑 완료!")
    logger.info(f"성공: {total_success}/{len(usernames)} ({total_success/len(usernames)*100:.1f}%)")
    logger.info(f"실패: {total_failed}/{len(usernames)} ({total_failed/len(usernames)*100:.1f}%)")
    logger.info("="*50)
    
    # 결과 파일 정리
    try:
        with open(config.output_file, 'r') as f:
            data = json.load(f)
        
        with open(config.output_file, 'w') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"결과가 {config.output_file}에 저장되었습니다.")
    except Exception as e:
        logger.error(f"결과 파일 정리 실패: {str(e)}")

def load_usernames_from_collected_data(filename="collected_data.json"):
    """collected_data.json에서 유저네임 추출"""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        usernames = set()
        for hashtag_data in data.get("hashtags", {}).values():
            for username in hashtag_data.get("usernames", []):
                # video/숫자 형식 제거
                clean_username = username.split("/video/")[0] if "/video/" in username else username
                usernames.add(clean_username)
                
        return list(usernames)
    except Exception as e:
        print(f"collected_data.json 로드 중 오류 발생: {str(e)}")
        return []

def save_usernames_to_file(usernames, filename="usernames.txt"):
    """유저네임을 파일에 저장"""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            for username in usernames:
                f.write(f"{username}\n")
        print(f"{len(usernames)}개의 유저네임이 {filename}에 저장되었습니다.")
    except Exception as e:
        print(f"유저네임 저장 중 오류 발생: {str(e)}")

def main():
    parser = argparse.ArgumentParser(description="대규모 틱톡 프로필 스크래퍼")
    parser.add_argument("-u", "--usernames", default="usernames.txt", help="사용자명 목록 파일")
    parser.add_argument("-o", "--output", default="tiktok_results.json", help="결과 저장 파일")
    parser.add_argument("-c", "--cookies", default="cookies.json", help="쿠키 파일")
    parser.add_argument("-p", "--proxies", default="proxies.txt", help="프록시 목록 파일")
    parser.add_argument("-w", "--workers", type=int, default=5, help="동시 작업자 수")
    parser.add_argument("-b", "--batch", type=int, default=100, help="배치 크기")
    parser.add_argument("--proxy", action="store_true", help="프록시 사용 여부")
    parser.add_argument("--headless", action="store_true", help="헤드리스 모드 사용 여부")
    parser.add_argument("--debug", action="store_true", help="디버그 모드")
    parser.add_argument("--use-collected", action="store_true", help="collected_data.json 파일에서 유저네임 로드")
    
    args = parser.parse_args()
    
    # collected_data.json에서 유저네임 로드
    if args.use_collected:
        print("collected_data.json에서 유저네임 로드 중...")
        usernames = load_usernames_from_collected_data()
        if usernames:
            print(f"{len(usernames)}개의 유저네임을 찾았습니다.")
            save_usernames_to_file(usernames, args.usernames)
        else:
            print("유저네임을 찾을 수 없습니다.")
            return
    
    # 설정 생성
    config = ScraperConfig(
        usernames_file=args.usernames,
        output_file=args.output,
        cookies_file=args.cookies,
        proxy_file=args.proxies,
        concurrent_workers=args.workers,
        proxy_enabled=args.proxy,
        headless=args.headless,
        debug=args.debug,
        batch_size=args.batch
    )
    
    # 스크래퍼 실행
    asyncio.run(run_scraper(config))

if __name__ == "__main__":
    multiprocessing.freeze_support()  # Windows 지원
    main() 