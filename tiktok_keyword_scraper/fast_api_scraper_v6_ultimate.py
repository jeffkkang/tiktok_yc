#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fast TikTok API Scraper V6 - 12개 제한 우회 강화판
"""

import requests
import json
import logging
import time
import random
from typing import List, Dict, Optional
from urllib.parse import urlparse, parse_qs
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)


class FastTikTokAPIScraperV6:
    """12개 제한 우회 강화 스크래퍼"""

    def __init__(self, cookies_file: str = 'cookies.json',
                 endpoints_file: str = 'tiktok_api_endpoints.json',
                 max_workers: int = 3):
        self.max_workers = max_workers
        self.cookies = self._load_cookies(cookies_file)
        self.base_params = self._load_base_params(endpoints_file)

        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Accept': 'application/json',
            'Referer': 'https://www.tiktok.com/'
        })

        if self.cookies:
            self.session.cookies.update(self.cookies)

        logger.info("⚡ V6 스크래퍼 초기화 (12개 제한 우회 강화)")

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

            for endpoint in endpoints:
                if '/api/search/general/full/' in endpoint['url']:
                    parsed_url = urlparse(endpoint['url'])
                    params = parse_qs(parsed_url.query)

                    params_clean = {
                        k: v[0] if isinstance(v, list) else v
                        for k, v in params.items()
                        if k not in ['X-Bogus', 'X-Gnarly', 'msToken', 'keyword', 'offset', 'cursor']
                    }

                    return params_clean

            return {}

        except Exception as e:
            logger.warning(f"파라미터 로드 실패: {e}")
            return {}

    def _generate_extended_variations(self, keyword: str, target: int = 500) -> List[Dict[str, any]]:
        """
        확장된 검색어 변형 생성 (sort_type, publish_time 조합 포함)

        핵심 전략:
        1. 기본 검색어 변형 (50개+)
        2. 각 변형에 대해 sort_type 변경 (종합/최신)
        3. publish_time 필터 추가 (전체/7일/30일/90일)

        → 이론적으로 수천 개의 고유 쿼리 생성 가능
        """
        base_variations = [
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
            f"{keyword} haul",
            f"{keyword} favorites",
            f"{keyword} essentials",
            f"{keyword} routine",
            f"my {keyword}",
            f"{keyword} must haves",
            f"{keyword} recommendations",
            f"affordable {keyword}",
            f"luxury {keyword}",
            f"drugstore {keyword}",
            f"{keyword} dupes",
            f"{keyword} collection",
            f"{keyword} organization",
            f"{keyword} storage",
            f"professional {keyword}",
            f"beginner {keyword}",
            f"advanced {keyword}",
            f"{keyword} mistakes",
            f"{keyword} secrets",
            f"{keyword} tricks",
            f"viral {keyword}",
            f"trending {keyword}",
            f"{keyword} hack",
            f"{keyword} skincare",
            f"{keyword} beauty",
            f"glam {keyword}",
            f"natural {keyword} look",
            f"dramatic {keyword}",
            f"subtle {keyword}",
            f"{keyword} for beginners",
        ]

        # 조합 생성
        queries = []

        # 전략 1: 검색어 변형만 (sort_type=0)
        for variation in base_variations[:20]:
            queries.append({
                'query': variation,
                'sort_type': 0,
                'publish_time': None
            })

        # 전략 2: 최신순 검색 (sort_type=1)
        for variation in base_variations[:15]:
            queries.append({
                'query': variation,
                'sort_type': 1,
                'publish_time': None
            })

        # 전략 3: 시간 필터 조합
        time_filters = [7, 30, 90]
        for variation in base_variations[:10]:
            for time_filter in time_filters:
                queries.append({
                    'query': variation,
                    'sort_type': 0,
                    'publish_time': time_filter
                })

        # 전략 4: sort_type=1 + 시간 필터
        for variation in base_variations[:5]:
            for time_filter in [7, 30]:
                queries.append({
                    'query': variation,
                    'sort_type': 1,
                    'publish_time': time_filter
                })

        logger.info(f"   생성된 쿼리 조합: {len(queries)}개")
        logger.info(f"   예상 최대 수집량: {len(queries) * 12}개")

        return queries[:target // 10]  # 목표치에 맞게 조정

    def _scrape_single_query(self, query_config: Dict, index: int, total: int) -> Dict:
        """단일 쿼리 스크래핑"""
        query = query_config['query']
        sort_type = query_config.get('sort_type')
        publish_time = query_config.get('publish_time')

        params = self.base_params.copy()
        params['keyword'] = query
        params['offset'] = 0

        if sort_type is not None:
            params['sort_type'] = sort_type

        if publish_time is not None:
            params['publish_time'] = publish_time

        # 쿼리 설명
        desc_parts = [f"'{query}'"]
        if sort_type == 1:
            desc_parts.append("최신순")
        if publish_time:
            desc_parts.append(f"{publish_time}일")
        desc = " | ".join(desc_parts)

        try:
            response = self.session.get(
                'https://www.tiktok.com/api/search/general/full/',
                params=params,
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                videos = data.get('data', [])

                logger.info(f"   [{index}/{total}] {desc}: {len(videos)}개")

                time.sleep(random.uniform(1.0, 2.0))

                return {'query': desc, 'videos': videos, 'error': False}

            else:
                logger.warning(f"   [{index}/{total}] {desc}: HTTP {response.status_code}")
                return {'query': desc, 'videos': [], 'error': True}

        except Exception as e:
            logger.error(f"   [{index}/{total}] {desc}: 오류 - {e}")
            return {'query': desc, 'videos': [], 'error': True}

    def search_ultimate(self, keyword: str, limit: int = 500) -> List[Dict]:
        """
        12개 제한 우회 궁극 버전

        Args:
            keyword: 기본 검색 키워드
            limit: 목표 개수

        Returns:
            비디오 리스트
        """
        logger.info(f"🚀 궁극 버전 수집 시작: {keyword} (목표: {limit}개)")

        # 확장된 쿼리 생성
        query_configs = self._generate_extended_variations(keyword, limit)

        all_videos = []
        video_ids_seen = set()
        usernames_seen = set()
        failed_queries = []

        # 병렬 처리
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_query = {
                executor.submit(self._scrape_single_query, config, i + 1, len(query_configs)): config
                for i, config in enumerate(query_configs)
            }

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
        logger.info(f"✅ 수집 완료: {len(all_videos)}개 (고유 크리에이터: {len(usernames_seen)}명)")
        logger.info(f"   성공률: {100 * (len(query_configs) - len(failed_queries)) / len(query_configs):.1f}%")
        logger.info(f"   실패한 쿼리: {len(failed_queries)}개")

        return all_videos[:limit]


# CLI 테스트
if __name__ == "__main__":
    import argparse
    import csv
    import os
    from datetime import datetime

    parser = argparse.ArgumentParser(description='Fast TikTok API Scraper V6 Ultimate')
    parser.add_argument('-k', '--keyword', required=True, help='검색 키워드')
    parser.add_argument('-l', '--limit', type=int, default=500, help='수집할 개수')
    parser.add_argument('--max-workers', type=int, default=3, help='병렬 워커 수')

    args = parser.parse_args()

    # 로깅 설정
    logging.basicConfig(
        level=logging.INFO,
        format='[%(asctime)s] %(levelname)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # 스크래퍼 실행
    scraper = FastTikTokAPIScraperV6(max_workers=args.max_workers)
    videos = scraper.search_ultimate(args.keyword, args.limit)

    # 결과 저장
    output_file = f"results/{args.keyword}_v6_ultimate.csv"
    os.makedirs('results', exist_ok=True)

    # 간단한 파싱 (기존 parse_video 메서드 대신)
    with open(output_file, 'w', newline='', encoding='utf-8-sig') as f:
        fieldnames = [
            'keyword', 'video_id', 'video_url', 'creator_username',
            'creator_nickname', 'follower_count', 'scraped_at'
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        saved_count = 0
        for video in videos:
            item = video.get('item', {})
            author = item.get('author', {})
            stats = author.get('stats', {})

            video_id = item.get('id', '')
            creator_username = author.get('uniqueId') or author.get('unique_id', '')
            creator_nickname = author.get('nickname', '')
            follower_count = stats.get('followerCount', 0)

            if creator_username:
                writer.writerow({
                    'keyword': args.keyword,
                    'video_id': video_id,
                    'video_url': f"https://www.tiktok.com/@{creator_username}/video/{video_id}",
                    'creator_username': creator_username,
                    'creator_nickname': creator_nickname,
                    'follower_count': follower_count,
                    'scraped_at': datetime.now().isoformat()
                })
                saved_count += 1

    logger.info(f"💾 저장 완료: {output_file} ({saved_count}개)")
    print(f"\n✅ 완료: {output_file} ({saved_count}개)")
