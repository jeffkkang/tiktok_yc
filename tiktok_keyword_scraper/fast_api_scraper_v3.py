#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fast TikTok API Scraper V3 - Production Ready
Priority 1 개선사항 적용:
- Retry 로직
- Exponential backoff
- 향상된 에러 핸들링
- Response 검증
- 동적 Rate Limiting
"""

import requests
import json
import logging
import time
import re
import random
from typing import List, Dict, Optional
from urllib.parse import urlparse, parse_qs

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

    def on_success(self):
        """성공 시 호출 - 점진적으로 빨라짐"""
        self.consecutive_success += 1
        self.consecutive_failures = 0

        if self.consecutive_success > 10:
            self.delay = max(0.5, self.delay * 0.95)
            logger.debug(f"Rate limit 완화: {self.delay:.2f}초")

    def on_error(self, status_code: int):
        """오류 시 호출 - 급격히 느려짐"""
        self.consecutive_failures += 1
        self.consecutive_success = 0

        if status_code == 429:  # Rate limit
            self.delay = min(10, self.delay * 2)
            logger.warning(f"Rate limit 감지! 대기 시간 증가: {self.delay:.2f}초")
        else:
            self.delay = min(5, self.delay * 1.5)

    def wait(self):
        """대기 실행"""
        time.sleep(self.delay)


class FastTikTokAPIScraperV3:
    """Production-ready TikTok API 스크래퍼"""

    def __init__(self, cookies_file: str = 'tiktok_cookies.json',
                 endpoints_file: str = 'tiktok_api_endpoints.json',
                 max_retries: int = 3):
        """
        Args:
            cookies_file: 쿠키 파일 경로
            endpoints_file: API 엔드포인트 파일 경로
            max_retries: 최대 재시도 횟수
        """
        self.max_retries = max_retries
        self.cookies = self._load_cookies(cookies_file)
        self.base_params = self._load_base_params(endpoints_file)
        self.headers = self._load_headers(endpoints_file)

        # Rate limiter
        self.rate_limiter = AdaptiveRateLimiter()

        # requests 세션
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Accept': 'application/json',
            'Referer': 'https://www.tiktok.com/'
        })

        if self.cookies:
            self.session.cookies.update(self.cookies)

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
        """
        응답 검증

        Raises:
            CaptchaError: CAPTCHA 감지 시
            APIError: API 오류 시
        """
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
        """
        Retry 로직이 포함된 API 요청

        Args:
            url: API URL
            params: 요청 파라미터

        Returns:
            Response 또는 None
        """
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
                logger.error("⚠️  CAPTCHA 감지! 쿠키 갱신 필요")
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
        """
        Exponential backoff 계산

        Args:
            attempt: 시도 횟수 (0부터 시작)
            base_delay: 기본 지연 시간

        Returns:
            대기 시간 (초)
        """
        delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
        return min(delay, 30)  # 최대 30초

    def _generate_query_variations(self, keyword: str, target_count: int = 200) -> List[str]:
        """
        검색어 변형 생성

        Args:
            keyword: 기본 키워드
            target_count: 목표 수집 개수

        Returns:
            검색어 변형 리스트
        """
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

        # 목표량에 따라 변형 개수 조절
        needed = min(len(variations), max(10, int(target_count / 9.7) + 2))
        return variations[:needed]

    def search_with_variations(self, keyword: str, limit: int = 200) -> List[Dict]:
        """
        검색어 변형으로 대량 수집

        Args:
            keyword: 기본 검색 키워드
            limit: 목표 개수

        Returns:
            비디오 리스트
        """
        logger.info(f"🚀 검색어 변형 수집 시작: {keyword} (목표: {limit}개)")

        query_variations = self._generate_query_variations(keyword, limit)
        logger.info(f"   생성된 변형: {len(query_variations)}개")

        all_videos = []
        video_ids_seen = set()
        usernames_seen = set()
        failed_queries = []

        for i, query in enumerate(query_variations, 1):
            if len(all_videos) >= limit:
                logger.info(f"   ✅ 목표 달성! 수집 중단")
                break

            params = self.base_params.copy()
            params['keyword'] = query
            params['offset'] = 0

            # Retry 로직 포함 요청
            response = self._api_request_with_retry(
                'https://www.tiktok.com/api/search/general/full/',
                params
            )

            if not response:
                failed_queries.append(query)
                logger.warning(f"   [{i}/{len(query_variations)}] '{query}': 실패")
                continue

            try:
                data = response.json()
                videos = data.get('data', [])

                # 중복 제거
                new_count = 0
                for video in videos:
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

                logger.info(f"   [{i}/{len(query_variations)}] '{query}': "
                           f"{len(videos)}개 → +{new_count}개 (총: {len(all_videos)}개)")

            except Exception as e:
                logger.error(f"   [{i}/{len(query_variations)}] '{query}': 파싱 오류 - {e}")
                failed_queries.append(query)
                continue

            # Rate limiting
            self.rate_limiter.wait()

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

    parser = argparse.ArgumentParser(description='Fast TikTok API Scraper V3')
    parser.add_argument('-k', '--keyword', required=True, help='검색 키워드')
    parser.add_argument('-l', '--limit', type=int, default=200, help='수집할 개수')
    parser.add_argument('--max-retries', type=int, default=3, help='최대 재시도 횟수')

    args = parser.parse_args()

    # 로깅 설정
    logging.basicConfig(
        level=logging.INFO,
        format='[%(asctime)s] %(levelname)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # 스크래퍼 실행
    scraper = FastTikTokAPIScraperV3(max_retries=args.max_retries)
    videos = scraper.search_with_variations(args.keyword, args.limit)

    # 결과 저장
    output_file = f"results/{args.keyword}_api_v3.csv"
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
                    'source_api': 'tiktok_api_v3_production',
                    'scraped_at': datetime.now().isoformat()
                })
                saved_count += 1

    logger.info(f"💾 저장 완료: {output_file} ({saved_count}개)")
    print(f"\n✅ 완료: {output_file} ({saved_count}개)")
