#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fast TikTok API Scraper V4 - Ultimate Performance
Priority 1 + Priority 2 개선사항 적용:
✅ Priority 1: Retry, Exponential backoff, Error Handling, Rate Limiting
✅ Priority 2: 병렬 처리 (ThreadPoolExecutor), 쿠키 자동 갱신
"""

import requests
import json
import logging
import time
import re
import random
from typing import List, Dict, Optional
from urllib.parse import urlparse, parse_qs
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

logger = logging.getLogger(__name__)


class CaptchaError(Exception):
    """CAPTCHA 감지 오류"""
    pass


class APIError(Exception):
    """API 응답 오류"""
    pass


class AdaptiveRateLimiter:
    """동적 Rate Limiter - 성공/실패에 따라 지연 시간 조절"""

    def __init__(self, initial_delay=1.0):
        self.delay = initial_delay
        self.consecutive_success = 0
        self.consecutive_failures = 0
        self.lock = Lock()  # Thread-safe

    def on_success(self):
        """성공 시 호출 - 점진적으로 빨라짐"""
        with self.lock:
            self.consecutive_success += 1
            self.consecutive_failures = 0

            if self.consecutive_success > 10:
                self.delay = max(0.5, self.delay * 0.95)
                logger.debug(f"Rate limit 완화: {self.delay:.2f}초")

    def on_error(self, status_code: int):
        """오류 시 호출 - 급격히 느려짐"""
        with self.lock:
            self.consecutive_failures += 1
            self.consecutive_success = 0

            if status_code == 429:  # Rate limit
                self.delay = min(10, self.delay * 2)
                logger.warning(f"Rate limit 감지! 대기 시간 증가: {self.delay:.2f}초")
            else:
                self.delay = min(5, self.delay * 1.5)

    def wait(self):
        """대기 실행"""
        with self.lock:
            delay = self.delay
        time.sleep(delay)


class AutoCookieManager:
    """자동 쿠키 갱신 매니저"""

    def __init__(self, refresh_interval: int = 100):
        """
        Args:
            refresh_interval: 쿠키 갱신 주기 (요청 횟수 기준)
        """
        self.refresh_interval = refresh_interval
        self.request_count = 0
        self.lock = Lock()
        logger.info(f"🍪 자동 쿠키 갱신 설정: {refresh_interval}회마다")

    def should_refresh(self) -> bool:
        """쿠키 갱신이 필요한지 확인"""
        with self.lock:
            self.request_count += 1
            if self.request_count % self.refresh_interval == 0:
                logger.info(f"🔄 쿠키 갱신 시점 도달 ({self.request_count}회)")
                return True
            return False

    def refresh_cookies(self, keyword: str = "makeup"):
        """Selenium으로 쿠키 갱신"""
        try:
            logger.info("🌐 브라우저로 쿠키 갱신 중...")
            from selenium import webdriver
            from selenium.webdriver.chrome.service import Service
            from selenium.webdriver.chrome.options import Options
            from webdriver_manager.chrome import ChromeDriverManager

            options = Options()
            options.add_argument("--headless=new")
            options.add_argument("--disable-blink-features=AutomationControlled")

            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=options)

            try:
                driver.get(f"https://www.tiktok.com/search?q={keyword}")
                time.sleep(5)

                # 쿠키 저장
                cookies = driver.get_cookies()
                with open('tiktok_cookies.json', 'w') as f:
                    json.dump(cookies, f)

                logger.info(f"✅ 쿠키 갱신 완료: {len(cookies)}개")
                return True

            finally:
                driver.quit()

        except Exception as e:
            logger.error(f"❌ 쿠키 갱신 실패: {e}")
            return False


class FastTikTokAPIScraperV4:
    """Ultimate Performance TikTok API 스크래퍼 (병렬 처리)"""

    def __init__(self, cookies_file: str = 'tiktok_cookies.json',
                 endpoints_file: str = 'tiktok_api_endpoints.json',
                 max_retries: int = 3,
                 max_workers: int = 3,
                 auto_refresh_cookies: bool = True,
                 cookie_refresh_interval: int = 100):
        """
        Args:
            cookies_file: 쿠키 파일 경로
            endpoints_file: API 엔드포인트 파일 경로
            max_retries: 최대 재시도 횟수
            max_workers: 병렬 처리 워커 수 (1-5 권장)
            auto_refresh_cookies: 자동 쿠키 갱신 여부
            cookie_refresh_interval: 쿠키 갱신 주기
        """
        self.max_retries = max_retries
        self.max_workers = max_workers
        self.cookies = self._load_cookies(cookies_file)
        self.base_params = self._load_base_params(endpoints_file)
        self.headers = self._load_headers(endpoints_file)

        # Rate limiter
        self.rate_limiter = AdaptiveRateLimiter()

        # 쿠키 자동 갱신
        if auto_refresh_cookies:
            self.cookie_manager = AutoCookieManager(cookie_refresh_interval)
        else:
            self.cookie_manager = None

        # requests 세션 (Thread-safe)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Accept': 'application/json',
            'Referer': 'https://www.tiktok.com/'
        })

        if self.cookies:
            self.session.cookies.update(self.cookies)

        logger.info(f"⚡ V4 스크래퍼 초기화 (병렬 워커: {max_workers}개)")

    def _load_cookies(self, cookies_file: str) -> Dict[str, str]:
        """쿠키 로드"""
        try:
            with open(cookies_file, 'r') as f:
                cookie_list = json.load(f)
            return {c['name']: c['value'] for c in cookie_list}
        except Exception as e:
            logger.warning(f"쿠키 로드 실패: {e}")
            return {}

    def _load_base_params(self, endpoints_file: str) -> Dict[str, str]:
        """기본 파라미터 로드"""
        try:
            with open(endpoints_file, 'r') as f:
                endpoints = json.load(f)

            search_api = None
            for endpoint in endpoints:
                if '/api/search/general/full/' in endpoint['url']:
                    search_api = endpoint
                    break

            if not search_api:
                logger.warning("검색 API를 찾을 수 없음")
                return {}

            parsed_url = urlparse(search_api['url'])
            params = parse_qs(parsed_url.query)

            params_clean = {
                k: v[0] if isinstance(v, list) else v
                for k, v in params.items()
                if k not in ['X-Bogus', 'X-Gnarly', 'msToken', 'keyword', 'offset']
            }

            return params_clean

        except Exception as e:
            logger.warning(f"파라미터 로드 실패: {e}")
            return {}

    def _load_headers(self, endpoints_file: str) -> Dict[str, str]:
        """헤더 로드"""
        try:
            with open(endpoints_file, 'r') as f:
                endpoints = json.load(f)

            for endpoint in endpoints:
                if '/api/search/general/full/' in endpoint['url']:
                    return endpoint.get('headers', {})

            return {}
        except:
            return {}

    def _validate_response(self, response: requests.Response) -> None:
        """응답 검증"""
        # CAPTCHA 체크
        if 'captcha' in response.text.lower():
            raise CaptchaError("CAPTCHA 감지됨")

        # JSON 파싱
        try:
            data = response.json()
        except json.JSONDecodeError:
            raise APIError(f"JSON 파싱 실패: {response.text[:200]}")

        # API 상태 코드 체크
        if data.get('statusCode') != 0 and data.get('status_code') != 0:
            raise APIError(f"API 오류: {data.get('statusMsg', 'Unknown')}")

    def _api_request_with_retry(self, url: str, params: Dict) -> Optional[requests.Response]:
        """Retry 로직이 포함된 API 요청"""
        # 쿠키 자동 갱신 체크
        if self.cookie_manager and self.cookie_manager.should_refresh():
            if self.cookie_manager.refresh_cookies():
                # 쿠키 재로드
                self.cookies = self._load_cookies('tiktok_cookies.json')
                self.session.cookies.update(self.cookies)

        for attempt in range(self.max_retries):
            try:
                response = self.session.get(
                    url,
                    params=params,
                    timeout=30
                )

                # 성공
                if response.status_code == 200:
                    self._validate_response(response)
                    self.rate_limiter.on_success()
                    return response

                # Rate limit
                elif response.status_code == 429:
                    self.rate_limiter.on_error(429)
                    backoff = self._exponential_backoff(attempt)
                    logger.warning(f"Rate limit! {backoff:.1f}초 대기 (시도 {attempt + 1}/{self.max_retries})")
                    time.sleep(backoff)

                # 기타 오류
                else:
                    self.rate_limiter.on_error(response.status_code)
                    logger.warning(f"HTTP {response.status_code} (시도 {attempt + 1}/{self.max_retries})")
                    time.sleep(2)

            except requests.Timeout:
                logger.warning(f"타임아웃 (시도 {attempt + 1}/{self.max_retries})")
                time.sleep(3)

            except requests.ConnectionError:
                logger.error(f"연결 오류 (시도 {attempt + 1}/{self.max_retries})")
                time.sleep(5)

            except CaptchaError:
                logger.error("⚠️  CAPTCHA 감지! 쿠키 갱신 시도")
                if self.cookie_manager:
                    self.cookie_manager.refresh_cookies()
                return None

            except APIError as e:
                logger.error(f"API 오류: {e}")
                return None

            except Exception as e:
                logger.error(f"예외 발생: {e} (시도 {attempt + 1}/{self.max_retries})")
                time.sleep(2)

        logger.error(f"최대 재시도 횟수 초과: {url}")
        return None

    def _exponential_backoff(self, attempt: int, base_delay: float = 2.0) -> float:
        """Exponential backoff 계산"""
        delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
        return min(delay, 30)

    def _generate_query_variations(self, keyword: str, target_count: int = 200) -> List[str]:
        """검색어 변형 생성"""
        variations = [
            keyword,
            f"#{keyword}",
            f"{keyword} tutorial",
            f"{keyword} tips",
            f"{keyword} hacks",
            f"{keyword} routine",
            f"{keyword} transformation",
            f"{keyword} look",
            f"daily {keyword}",
            f"easy {keyword}",
            f"best {keyword}",
            f"{keyword} ideas",
            f"{keyword} inspiration",
            f"{keyword} review",
            f"simple {keyword}",
            f"{keyword} guide",
            f"{keyword} products",
            f"natural {keyword}",
            f"{keyword} trends",
            f"quick {keyword}",
        ]

        needed = min(len(variations), max(10, int(target_count / 9.7) + 2))
        return variations[:needed]

    def _scrape_single_query(self, query: str, index: int, total: int) -> Dict:
        """단일 검색어 스크래핑 (병렬 처리용)"""
        params = self.base_params.copy()
        params['keyword'] = query
        params['offset'] = 0

        response = self._api_request_with_retry(
            'https://www.tiktok.com/api/search/general/full/',
            params
        )

        if not response:
            return {'query': query, 'videos': [], 'error': True}

        try:
            data = response.json()
            videos = data.get('data', [])

            logger.info(f"   [{index}/{total}] '{query}': {len(videos)}개 수집")

            self.rate_limiter.wait()

            return {'query': query, 'videos': videos, 'error': False}

        except Exception as e:
            logger.error(f"   [{index}/{total}] '{query}': 파싱 오류 - {e}")
            return {'query': query, 'videos': [], 'error': True}

    def search_with_variations_parallel(self, keyword: str, limit: int = 200) -> List[Dict]:
        """
        병렬 처리로 검색어 변형 수집

        Args:
            keyword: 기본 검색 키워드
            limit: 목표 개수

        Returns:
            비디오 리스트
        """
        logger.info(f"🚀 병렬 수집 시작: {keyword} (목표: {limit}개, 워커: {self.max_workers}개)")

        query_variations = self._generate_query_variations(keyword, limit)
        logger.info(f"   생성된 변형: {len(query_variations)}개")

        all_videos = []
        video_ids_seen = set()
        usernames_seen = set()
        failed_queries = []

        # 병렬 처리
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 작업 제출
            future_to_query = {
                executor.submit(self._scrape_single_query, query, i + 1, len(query_variations)): query
                for i, query in enumerate(query_variations)
            }

            # 완료된 작업 처리
            for future in as_completed(future_to_query):
                if len(all_videos) >= limit:
                    logger.info(f"   ✅ 목표 달성! 수집 중단")
                    break

                result = future.result()

                if result['error']:
                    failed_queries.append(result['query'])
                    continue

                # 중복 제거
                new_count = 0
                for video in result['videos']:
                    item = video.get('item', {})
                    author = item.get('author', {})

                    video_id = item.get('id')
                    username = author.get('uniqueId') or author.get('unique_id')

                    if video_id and video_id not in video_ids_seen:
                        all_videos.append(video)
                        video_ids_seen.add(video_id)
                        if username:
                            usernames_seen.add(username)
                        new_count += 1

        # 최종 로그
        if failed_queries:
            logger.warning(f"⚠️  실패한 검색어 ({len(failed_queries)}개): {', '.join(failed_queries[:5])}")

        logger.info(f"✅ 수집 완료: {len(all_videos)}개 (고유 크리에이터: {len(usernames_seen)}명)")
        logger.info(f"   성공률: {100 * (len(query_variations) - len(failed_queries)) / len(query_variations):.1f}%")

        return all_videos[:limit]

    def parse_video(self, video_data: Dict) -> Optional[Dict]:
        """비디오 데이터 파싱"""
        try:
            item = video_data.get('item', {})
            author = item.get('author', {})
            stats = item.get('stats', {})

            video_id = item.get('id', '')
            video_desc = item.get('desc', '')

            creator_id = author.get('id', '')
            creator_username = author.get('uniqueId') or author.get('unique_id', '')
            creator_nickname = author.get('nickname', '')

            creator_email = self._extract_email(author.get('signature', ''))

            follower_count = stats.get('followerCount', 0)
            following_count = stats.get('followingCount', 0)
            video_count = stats.get('videoCount', 0)
            heart_count = stats.get('heartCount', 0)

            hashtags = ','.join([
                tag.get('title', '')
                for tag in item.get('textExtra', [])
                if tag.get('hashtagName')
            ])

            create_time = item.get('createTime', '')

            return {
                'video_id': video_id,
                'video_url': f"https://www.tiktok.com/@{creator_username}/video/{video_id}",
                'creator_id': creator_id,
                'creator_username': creator_username,
                'creator_nickname': creator_nickname,
                'creator_email': creator_email,
                'follower_count': follower_count,
                'following_count': following_count,
                'video_count': video_count,
                'heart_count': heart_count,
                'video_desc': video_desc,
                'create_time': create_time,
                'hashtags': hashtags
            }

        except Exception as e:
            logger.error(f"비디오 파싱 실패: {e}")
            return None

    def _extract_email(self, text: str) -> str:
        """텍스트에서 이메일 추출"""
        if not text:
            return ""

        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        match = re.search(email_pattern, text)
        return match.group(0) if match else ""


# CLI 테스트
if __name__ == "__main__":
    import argparse
    import csv
    import os

    parser = argparse.ArgumentParser(description='Fast TikTok API Scraper V4')
    parser.add_argument('-k', '--keyword', required=True, help='검색 키워드')
    parser.add_argument('-l', '--limit', type=int, default=200, help='수집할 개수')
    parser.add_argument('--max-retries', type=int, default=3, help='최대 재시도 횟수')
    parser.add_argument('--max-workers', type=int, default=3, help='병렬 워커 수 (1-5)')
    parser.add_argument('--no-auto-refresh', action='store_true', help='자동 쿠키 갱신 비활성화')

    args = parser.parse_args()

    # 로깅 설정
    logging.basicConfig(
        level=logging.INFO,
        format='[%(asctime)s] %(levelname)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # 스크래퍼 실행
    scraper = FastTikTokAPIScraperV4(
        max_retries=args.max_retries,
        max_workers=args.max_workers,
        auto_refresh_cookies=not args.no_auto_refresh
    )
    videos = scraper.search_with_variations_parallel(args.keyword, args.limit)

    # 결과 저장
    output_file = f"results/{args.keyword}_api_v4.csv"
    os.makedirs('results', exist_ok=True)

    with open(output_file, 'w', newline='', encoding='utf-8-sig') as f:
        fieldnames = [
            'keyword', 'video_id', 'video_url', 'creator_id',
            'creator_username', 'creator_nickname', 'creator_email',
            'follower_count', 'following_count', 'video_count', 'heart_count',
            'video_desc', 'create_time', 'hashtags', 'source_api', 'scraped_at'
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        from datetime import datetime
        saved_count = 0

        for video in videos:
            parsed = scraper.parse_video(video)
            if parsed and parsed['creator_username']:
                writer.writerow({
                    'keyword': args.keyword,
                    'video_id': parsed['video_id'],
                    'video_url': parsed['video_url'],
                    'creator_id': parsed['creator_id'],
                    'creator_username': parsed['creator_username'],
                    'creator_nickname': parsed['creator_nickname'],
                    'creator_email': parsed['creator_email'] or '',
                    'follower_count': parsed['follower_count'],
                    'following_count': parsed['following_count'],
                    'video_count': parsed['video_count'],
                    'heart_count': parsed['heart_count'],
                    'video_desc': parsed['video_desc'],
                    'create_time': parsed['create_time'],
                    'hashtags': parsed['hashtags'],
                    'source_api': 'tiktok_api_v4_parallel',
                    'scraped_at': datetime.now().isoformat()
                })
                saved_count += 1

    logger.info(f"💾 저장 완료: {output_file} ({saved_count}개)")
    print(f"\n✅ 완료: {output_file} ({saved_count}개)")
