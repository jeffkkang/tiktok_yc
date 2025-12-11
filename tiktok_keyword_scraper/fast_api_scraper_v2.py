#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fast TikTok API Scraper V2 - Query Variations
검색어 변형 방식으로 200개 이상 수집 가능
"""

import requests
import json
import logging
import time
import re
from typing import List, Dict, Optional
from urllib.parse import urlparse, parse_qs

logger = logging.getLogger(__name__)


class FastTikTokAPIScraperV2:
    """검색어 변형 기반 고속 TikTok API 스크래퍼"""

    def __init__(self, cookies_file: str = 'tiktok_cookies.json',
                 endpoints_file: str = 'tiktok_api_endpoints.json'):
        """
        Args:
            cookies_file: 쿠키 파일 경로
            endpoints_file: API 엔드포인트 파일 경로
        """
        self.cookies = self._load_cookies(cookies_file)
        self.base_params = self._load_base_params(endpoints_file)
        self.headers = self._load_headers(endpoints_file)

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
        # 평균 9.7개/변형 기준
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

        for i, query in enumerate(query_variations, 1):
            if len(all_videos) >= limit:
                logger.info(f"   목표 달성! 수집 중단")
                break

            params = self.base_params.copy()
            params['keyword'] = query
            params['offset'] = 0

            try:
                response = self.session.get(
                    'https://www.tiktok.com/api/search/general/full/',
                    params=params,
                    timeout=30
                )

                if response.status_code != 200:
                    logger.warning(f"   [{i}/{len(query_variations)}] '{query}': 실패 ({response.status_code})")
                    continue

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

                # 레이트 리밋 대응
                time.sleep(1)

            except Exception as e:
                logger.error(f"   [{i}/{len(query_variations)}] '{query}': 에러 - {e}")
                continue

        logger.info(f"✅ 수집 완료: {len(all_videos)}개 (고유 크리에이터: {len(usernames_seen)}명)")
        return all_videos[:limit]

    def parse_video(self, video_data: Dict) -> Optional[Dict]:
        """
        비디오 데이터 파싱

        Args:
            video_data: API 응답의 비디오 데이터

        Returns:
            파싱된 비디오 정보
        """
        try:
            item = video_data.get('item', {})
            author = item.get('author', {})
            stats = item.get('stats', {})

            # 비디오 정보
            video_id = item.get('id', '')
            video_desc = item.get('desc', '')

            # 크리에이터 정보
            creator_id = author.get('id', '')
            creator_username = author.get('uniqueId') or author.get('unique_id', '')
            creator_nickname = author.get('nickname', '')

            # 이메일 추출
            creator_email = self._extract_email(author.get('signature', ''))

            # 통계
            follower_count = stats.get('followerCount', 0)
            following_count = stats.get('followingCount', 0)
            video_count = stats.get('videoCount', 0)
            heart_count = stats.get('heartCount', 0)

            # 해시태그 추출
            hashtags = ','.join([
                tag.get('title', '')
                for tag in item.get('textExtra', [])
                if tag.get('hashtagName')
            ])

            # 생성 시간
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

    parser = argparse.ArgumentParser(description='Fast TikTok API Scraper V2')
    parser.add_argument('-k', '--keyword', required=True, help='검색 키워드')
    parser.add_argument('-l', '--limit', type=int, default=200, help='수집할 개수')

    args = parser.parse_args()

    # 로깅 설정
    logging.basicConfig(
        level=logging.INFO,
        format='[%(asctime)s] %(levelname)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # 스크래퍼 실행
    scraper = FastTikTokAPIScraperV2()
    videos = scraper.search_with_variations(args.keyword, args.limit)

    # 결과 저장
    output_file = f"results/{args.keyword}_api_v2.csv"
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
                    'source_api': 'tiktok_api_v2_query_variations',
                    'scraped_at': datetime.now().isoformat()
                })
                saved_count += 1

    logger.info(f"💾 저장 완료: {output_file} ({saved_count}개)")
    print(f"\n✅ 완료: {output_file} ({saved_count}개)")
