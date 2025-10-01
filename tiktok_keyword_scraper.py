#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TikTok 키워드 검색 → 크리에이터 프로필 CSV Exporter
기존 tiktok-profile-scraper의 함수들을 재사용하여 구현
"""

import re
import os
import sys
import time
import json
import csv
import random
import logging
import asyncio
import argparse
import datetime
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from urllib.parse import quote

# Selenium 관련 임포트
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager

# 기존 스크래퍼 코드 경로 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'tiktok-profile-scraper'))

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler('tiktok_keyword_scraper.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


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
    source_api: str
    extraction_method: str
    scraped_at: str
    notes: str = ""


class EmailExtractor:
    """이메일 추출기 (기존 코드 재사용)"""

    @staticmethod
    def extract_emails(text: str) -> List[str]:
        """텍스트에서 이메일 추출"""
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b'
        emails = re.findall(email_pattern, text)

        # 중복 제거 및 정제
        clean_emails = []
        for email in emails:
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


def parse_count(count_text: str) -> int:
    """숫자 형식 파싱 ('1.2K', '1.2M' 등) - 기존 코드 재사용"""
    if not count_text:
        return 0

    count_text = str(count_text).strip().upper()
    count_text = count_text.replace(',', '')

    if 'K' in count_text:
        return int(float(count_text.replace('K', '')) * 1000)
    elif 'M' in count_text:
        return int(float(count_text.replace('M', '')) * 1000000)
    elif 'B' in count_text:
        return int(float(count_text.replace('B', '')) * 1000000000)
    else:
        try:
            return int(count_text.replace('.', ''))
        except ValueError:
            return 0


class CookieManager:
    """쿠키 관리자 (기존 코드 재사용)"""

    def __init__(self, cookies_file: str):
        self.cookies_file = cookies_file
        self.cookies_dict = {}
        self._load_cookies()

    def _load_cookies(self):
        """쿠키 파일 로드"""
        try:
            if os.path.exists(self.cookies_file):
                with open(self.cookies_file, 'r') as f:
                    cookie_objects = json.load(f)
                    if isinstance(cookie_objects, list):
                        # cookies.json 형식 (list of objects with name/value pairs)
                        for cookie in cookie_objects:
                            if "name" in cookie and "value" in cookie:
                                self.cookies_dict[cookie["name"]] = cookie["value"]
                        logger.info(f"✅ {len(self.cookies_dict)}개 쿠키 로드 완료")
                    else:
                        self.cookies_dict = cookie_objects
                        logger.info(f"✅ {len(self.cookies_dict)}개 쿠키 로드 완료")
            else:
                logger.warning(f"⚠️  쿠키 파일 {self.cookies_file}을 찾을 수 없음")
        except Exception as e:
            logger.error(f"❌ 쿠키 로드 실패: {e}")

    def get_cookies(self) -> Dict[str, str]:
        """쿠키 딕셔너리 반환"""
        return self.cookies_dict

    def format_for_selenium(self) -> List[Dict[str, Any]]:
        """Selenium 형식으로 쿠키 변환"""
        result = []
        for name, value in self.cookies_dict.items():
            result.append({
                "name": name,
                "value": value,
                "domain": ".tiktok.com"
            })
        return result


class TikTokKeywordScraper:
    """TikTok 키워드 검색 및 크리에이터 프로필 수집 스크래퍼"""

    def __init__(self, cookies_file: str, headless: bool = True, delay_min: float = 0.5, delay_max: float = 1.5):
        self.cookie_manager = CookieManager(cookies_file)
        self.headless = headless
        self.delay_min = delay_min
        self.delay_max = delay_max
        self.driver = None

    def setup_driver(self):
        """Selenium 드라이버 초기화 (기존 코드 패턴 재사용)"""
        options = Options()
        options.add_argument("--disable-blink-features=AutomationControlled")

        # User-Agent 설정
        user_agents = [
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36",
        ]
        user_agent = random.choice(user_agents)
        options.add_argument(f"user-agent={user_agent}")

        # 봇 감지 우회 옵션
        options.add_experimental_option('excludeSwitches', ['enable-automation'])
        options.add_experimental_option('useAutomationExtension', False)
        options.add_argument("--disable-notifications")
        options.add_argument("--disable-popup-blocking")

        # 헤드리스 모드
        if self.headless:
            options.add_argument("--headless=new")

        try:
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=options)
            self.driver.set_page_load_timeout(30)

            # 초기 페이지 로드
            self.driver.get("https://www.tiktok.com")
            time.sleep(random.uniform(self.delay_min, self.delay_max))

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
            time.sleep(random.uniform(self.delay_min, self.delay_max))

            logger.info("✅ Selenium 드라이버 초기화 완료")
            return self.driver
        except Exception as e:
            logger.error(f"❌ 드라이버 설정 중 오류 발생: {str(e)}")
            raise

    def search_videos_by_keyword(self, keyword: str, limit: int = 100) -> List[VideoResult]:
        """키워드로 비디오 검색"""
        logger.info(f"🔍 키워드 '{keyword}' 검색 시작 (목표: {limit}개)")

        if not self.driver:
            self.setup_driver()

        # TikTok 검색 페이지 접속
        search_url = f"https://www.tiktok.com/search/video?q={quote(keyword)}"
        logger.info(f"검색 URL: {search_url}")
        self.driver.get(search_url)
        time.sleep(random.uniform(2, 4))

        # 캡챠 확인 (헤드리스가 아닐 때만)
        if not self.headless:
            try:
                input("⚠️  캡챠나 팝업이 있다면 수동으로 해결 후 Enter를 눌러주세요...")
            except EOFError:
                logger.warning("⚠️  비인터랙티브 모드에서 실행 중, 자동 진행합니다.")

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
                # 비디오 컨테이너 찾기 (여러 셀렉터 시도)
                video_elements = self.driver.find_elements(By.CSS_SELECTOR, "div[data-e2e='search_top-item']")

                if not video_elements:
                    video_elements = self.driver.find_elements(By.CSS_SELECTOR, "div[data-e2e='search-video-item']")

                if not video_elements:
                    # 다른 셀렉터 시도
                    video_elements = self.driver.find_elements(By.CSS_SELECTOR, "div[class*='video-feed']")

                if not video_elements:
                    # 가장 일반적인 링크 찾기
                    video_elements = self.driver.find_elements(By.CSS_SELECTOR, "a[href*='/@'][href*='/video/']")
                    logger.debug(f"대체 셀렉터 사용: {len(video_elements)}개 링크 발견")

                logger.debug(f"발견된 요소 수: {len(video_elements)}")

                for element in video_elements:
                    try:
                        # 비디오 링크 추출
                        if element.tag_name == 'a':
                            # 요소 자체가 링크인 경우
                            video_url = element.get_attribute('href')
                        else:
                            # 하위 요소에서 링크 찾기
                            video_link_elem = element.find_element(By.CSS_SELECTOR, "a[href*='/@']")
                            video_url = video_link_elem.get_attribute('href')

                        if not video_url or '/video/' not in video_url:
                            continue

                        # URL 파싱: https://www.tiktok.com/@username/video/1234567890
                        parts = video_url.split('/@')
                        if len(parts) < 2:
                            continue

                        username_and_video = parts[1].split('/video/')
                        if len(username_and_video) < 2:
                            continue

                        creator_username = username_and_video[0]
                        video_id = username_and_video[1].split('?')[0]

                        # 중복 체크
                        if any(v.video_id == video_id for v in videos):
                            continue

                        # 조회수 추출 시도
                        view_count = 0
                        try:
                            view_elem = element.find_element(By.CSS_SELECTOR, "[data-e2e='video-views'], strong[data-e2e='search-video-views']")
                            view_count = parse_count(view_elem.text)
                        except NoSuchElementException:
                            pass

                        # 비디오 설명 추출
                        video_desc = ""
                        try:
                            desc_elem = element.find_element(By.CSS_SELECTOR, "[data-e2e='search-video-desc'], [data-e2e='video-desc']")
                            video_desc = desc_elem.text
                        except NoSuchElementException:
                            pass

                        video = VideoResult(
                            video_id=video_id,
                            video_url=video_url,
                            creator_id=creator_username,  # 일단 username을 ID로 사용
                            creator_username=creator_username,
                            view_count=view_count,
                            video_desc=video_desc
                        )

                        videos.append(video)
                        logger.info(f"  ✓ [{len(videos)}/{limit}] @{creator_username} - 조회수: {view_count:,}")

                        if len(videos) >= limit:
                            break

                    except Exception as e:
                        logger.debug(f"비디오 파싱 중 오류: {str(e)}")
                        continue

                # 스크롤 다운
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(random.uniform(1, 2))

                # 스크롤 높이 변화 확인
                new_height = self.driver.execute_script("return document.body.scrollHeight")
                if new_height == last_height:
                    scroll_attempts += 1
                    logger.debug(f"스크롤 시도 {scroll_attempts}/{max_scroll_attempts}")
                else:
                    scroll_attempts = 0
                    last_height = new_height

            except Exception as e:
                logger.error(f"검색 중 오류: {str(e)}")
                scroll_attempts += 1
                time.sleep(2)

        logger.info(f"✅ 총 {len(videos)}개 비디오 수집 완료")
        return videos

    def fetch_creator_profile(self, username: str) -> Dict[str, Any]:
        """크리에이터 프로필 조회 (기존 코드 패턴 재사용)"""
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
            url = f"https://www.tiktok.com/@{username}"
            self.driver.get(url)
            time.sleep(random.uniform(self.delay_min, self.delay_max))

            # 페이지 존재 확인
            page_title = self.driver.title
            if "Page Not Found" in page_title or "찾을 수 없음" in page_title:
                profile_data["error"] = "User not found"
                return profile_data

            # 인간스러운 스크롤
            for i in range(2):
                scroll_height = random.randint(100, 300)
                self.driver.execute_script(f"window.scrollTo(0, {scroll_height});")
                time.sleep(random.uniform(0.3, 0.8))

            # 팔로워 수 추출
            try:
                follower_element = self.driver.find_element(By.CSS_SELECTOR, "[data-e2e='followers-count']")
                profile_data["follower_count"] = parse_count(follower_element.text)
            except NoSuchElementException:
                logger.debug(f"  ⚠️  팔로워 수를 찾을 수 없음: @{username}")

            # 프로필 설명 추출
            try:
                WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "[data-e2e='user-bio'], [data-e2e='user-page-header']"))
                )
                bio_elements = self.driver.find_elements(By.CSS_SELECTOR, "[data-e2e='user-bio'], [data-e2e='user-page-header']")
                if bio_elements:
                    bio_text = " ".join([el.text for el in bio_elements])
                    profile_data["bio"] = bio_text
            except TimeoutException:
                pass

            # 이메일 추출 - 방법 1: 프로필 텍스트에서
            if profile_data["bio"]:
                bio_emails = EmailExtractor.extract_emails(profile_data["bio"])
                profile_data["emails"].extend(bio_emails)

            # 방법 2: mailto 링크에서
            mailto_links = self.driver.find_elements(By.CSS_SELECTOR, "a[href*='mailto:']")
            for link in mailto_links:
                href = link.get_attribute('href')
                if href and 'mailto:' in href:
                    email = href.replace('mailto:', '')
                    if email not in profile_data["emails"]:
                        profile_data["emails"].append(email)

            # 방법 3: 페이지 소스에서
            page_source = self.driver.page_source
            source_emails = EmailExtractor.extract_emails(page_source)
            for email in source_emails:
                if email not in profile_data["emails"]:
                    profile_data["emails"].append(email)

            # 최종 이메일 정제
            profile_data["emails"] = [email for email in profile_data["emails"] if EmailExtractor.is_valid_email(email)]

            profile_data["success"] = True
            logger.info(f"  ✅ @{username}: 팔로워 {profile_data['follower_count']:,}, 이메일 {len(profile_data['emails'])}개")

        except Exception as e:
            profile_data["error"] = str(e)
            logger.error(f"  ❌ 프로필 조회 실패 (@{username}): {str(e)}")

        return profile_data

    def close(self):
        """드라이버 종료"""
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass


def save_to_csv(profiles: List[CreatorProfile], output_file: str):
    """결과를 CSV로 저장"""
    logger.info(f"💾 CSV 저장 중: {output_file}")

    try:
        # 파일 존재 여부 확인
        file_exists = os.path.exists(output_file)

        with open(output_file, 'a' if file_exists else 'w', newline='', encoding='utf-8') as f:
            fieldnames = [
                'keyword', 'video_id', 'video_url', 'creator_id', 'creator_username',
                'creator_email', 'follower_count', 'source_api', 'extraction_method',
                'scraped_at', 'notes'
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames)

            # 헤더 작성 (파일이 없을 경우에만)
            if not file_exists:
                writer.writeheader()

            # 데이터 작성
            for profile in profiles:
                writer.writerow(asdict(profile))

        logger.info(f"✅ {len(profiles)}개 항목이 {output_file}에 저장되었습니다.")
    except Exception as e:
        logger.error(f"❌ CSV 저장 실패: {str(e)}")


def main():
    parser = argparse.ArgumentParser(description="TikTok 키워드 검색 → 크리에이터 프로필 CSV Exporter")
    parser.add_argument("--keyword", "-k", required=True, help="검색 키워드")
    parser.add_argument("--limit", "-l", type=int, default=100, help="수집할 최대 비디오 수 (기본: 100)")
    parser.add_argument("--out", "-o", default="creators.csv", help="출력 CSV 파일 경로 (기본: creators.csv)")
    parser.add_argument("--cookies-file", "-c", default="tiktok-hashtag-scraper/cookies.json", help="쿠키 JSON 파일 경로")
    parser.add_argument("--concurrency", type=int, default=1, help="병렬 처리 수 (현재는 미지원, 향후 구현 예정)")
    parser.add_argument("--use-browser", action="store_true", help="헤드리스 모드 비활성화 (브라우저 표시)")
    parser.add_argument("--delay-min", type=float, default=0.5, help="최소 지연 시간 (초)")
    parser.add_argument("--delay-max", type=float, default=1.5, help="최대 지연 시간 (초)")
    parser.add_argument("--debug", action="store_true", help="디버그 모드 (스크린샷 저장)")

    args = parser.parse_args()

    # 디버그 모드 설정
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.setLevel(logging.DEBUG)

    # 쿠키 파일 경로 확인
    if not os.path.exists(args.cookies_file):
        logger.error(f"❌ 쿠키 파일을 찾을 수 없습니다: {args.cookies_file}")
        return

    logger.info("=" * 60)
    logger.info("🚀 TikTok 키워드 검색 스크래퍼 시작")
    logger.info(f"   키워드: {args.keyword}")
    logger.info(f"   목표 비디오 수: {args.limit}")
    logger.info(f"   출력 파일: {args.out}")
    logger.info("=" * 60)

    # 스크래퍼 초기화
    scraper = TikTokKeywordScraper(
        cookies_file=args.cookies_file,
        headless=not args.use_browser,
        delay_min=args.delay_min,
        delay_max=args.delay_max
    )

    try:
        # 1. 키워드로 비디오 검색
        videos = scraper.search_videos_by_keyword(args.keyword, args.limit)

        if not videos:
            logger.warning("⚠️  검색 결과가 없습니다.")
            return

        # 2. 조회수 기준 정렬
        logger.info("📊 조회수 기준으로 정렬 중...")
        videos.sort(key=lambda v: v.view_count, reverse=True)

        # 3. 각 비디오의 크리에이터 프로필 조회 및 CSV 저장
        profiles = []
        processed_creators = set()  # 중복 방지용 (원본 요구사항: 각 영상별로 크리에이터 정보 추출, 중복 허용)

        logger.info(f"\n👤 크리에이터 프로필 조회 시작 ({len(videos)}개)...")

        for idx, video in enumerate(videos, 1):
            logger.info(f"\n[{idx}/{len(videos)}] 처리 중...")

            # 프로필 조회
            profile_data = scraper.fetch_creator_profile(video.creator_username)

            # CSV 행 생성
            profile = CreatorProfile(
                keyword=args.keyword,
                video_id=video.video_id,
                video_url=video.video_url,
                creator_id=video.creator_id,
                creator_username=video.creator_username,
                creator_email=profile_data['emails'][0] if profile_data['emails'] else "",
                follower_count=profile_data['follower_count'],
                source_api="page_dom",
                extraction_method="profile_dom",
                scraped_at=datetime.datetime.now().isoformat(),
                notes=profile_data.get('error', '')
            )

            profiles.append(profile)

            # 배치 저장 (10개마다)
            if len(profiles) >= 10:
                save_to_csv(profiles, args.out)
                profiles = []

            # 요청 간 지연
            time.sleep(random.uniform(args.delay_min, args.delay_max))

        # 남은 프로필 저장
        if profiles:
            save_to_csv(profiles, args.out)

        logger.info("\n" + "=" * 60)
        logger.info(f"✅ 스크래핑 완료!")
        logger.info(f"   처리된 비디오: {len(videos)}개")
        logger.info(f"   출력 파일: {args.out}")
        logger.info("=" * 60)

    except KeyboardInterrupt:
        logger.info("\n⚠️  사용자에 의해 중단되었습니다.")
    except Exception as e:
        logger.error(f"\n❌ 예상치 못한 오류: {str(e)}")
        import traceback
        logger.debug(traceback.format_exc())
    finally:
        scraper.close()


if __name__ == "__main__":
    main()
