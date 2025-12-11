#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TikTok Fast API Scraper
- 10배 이상 빠른 API 직접 호출 방식
- requests만 사용 (Selenium 불필요)
- 페이지네이션 자동 처리
"""

import requests
import json
import time
import re
from typing import List, Dict, Optional
from urllib.parse import urlparse, parse_qs
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class FastTikTokAPIScraper:
    """고속 TikTok API 스크래퍼"""

    def __init__(self, cookies_file: str = 'tiktok_cookies.json',
                 endpoints_file: str = 'tiktok_api_endpoints.json'):
        """
        Args:
            cookies_file: 쿠키 JSON 파일 경로
            endpoints_file: API 엔드포인트 JSON 파일 경로
        """
        self.cookies = self._load_cookies(cookies_file)
        self.base_params = self._load_base_params(endpoints_file)

        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Referer': 'https://www.tiktok.com/',
            'Accept': 'application/json, text/plain, */*',
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

            # 검색 API 찾기
            search_api = None
            for endpoint in endpoints:
                if '/api/search/general/full/' in endpoint['url']:
                    search_api = endpoint
                    break

            if not search_api:
                logger.warning("검색 API를 찾을 수 없음")
                return {}

            # URL 파싱
            parsed_url = urlparse(search_api['url'])
            params = parse_qs(parsed_url.query)

            # 단일 값으로 변환 & 서명 제거
            params_clean = {
                k: v[0] if isinstance(v, list) else v
                for k, v in params.items()
                if k not in ['X-Bogus', 'X-Gnarly', 'msToken', 'keyword', 'offset']
            }

            return params_clean

        except Exception as e:
            logger.warning(f"파라미터 로드 실패: {e}")
            return {}

    def search(self, keyword: str, limit: int = 200) -> List[Dict]:
        """
        키워드 검색 (API 직접 호출)

        Args:
            keyword: 검색 키워드
            limit: 수집할 최대 개수

        Returns:
            비디오 리스트
        """
        all_videos = []
        offset = 0

        logger.info(f"🚀 API 검색 시작: {keyword} (목표: {limit}개)")

        while len(all_videos) < limit:
            # 파라미터 설정
            params = self.base_params.copy()
            params['keyword'] = keyword
            params['offset'] = offset

            try:
                # API 호출
                response = self.session.get(
                    'https://www.tiktok.com/api/search/general/full/',
                    params=params,
                    timeout=30
                )

                if response.status_code != 200:
                    logger.warning(f"API 실패: {response.status_code}")
                    break

                data = response.json()

                # 비디오 추출
                videos = data.get('data', [])
                if not videos:
                    logger.warning("더 이상 결과 없음")
                    break

                all_videos.extend(videos)
                logger.info(f"   수집: {len(all_videos)}/{limit}개")

                # 페이지네이션
                if not data.get('has_more'):
                    logger.info("   마지막 페이지 도달")
                    break

                offset = data.get('cursor', offset + len(videos))

                # 레이트 리밋 대응
                time.sleep(1)

            except Exception as e:
                logger.error(f"API 요청 오류: {e}")
                break

        logger.info(f"✅ 수집 완료: {len(all_videos)}개")
        return all_videos[:limit]

    def parse_video(self, video_data: Dict) -> Optional[Dict]:
        """
        비디오 데이터 파싱

        Args:
            video_data: API 응답의 비디오 데이터

        Returns:
            파싱된 데이터
        """
        try:
            item = video_data.get('item', {})
            author = item.get('author', {})
            stats = item.get('authorStats', {})

            # 이메일 추출 (signature에서)
            email = self._extract_email(author.get('signature', ''))

            return {
                'video_id': item.get('id'),
                'video_url': f"https://www.tiktok.com/@{author.get('uniqueId')}/video/{item.get('id')}",
                'creator_id': author.get('id'),
                'creator_username': author.get('uniqueId'),
                'creator_nickname': author.get('nickname'),
                'creator_email': email,
                'follower_count': stats.get('followerCount', 0),
                'following_count': stats.get('followingCount', 0),
                'video_count': stats.get('videoCount', 0),
                'heart_count': stats.get('heartCount', 0),
                'video_desc': item.get('desc', ''),
                'create_time': item.get('createTime'),
                'hashtags': ','.join([c.get('title', '') for c in item.get('challenges', [])]),
            }

        except Exception as e:
            logger.error(f"비디오 파싱 오류: {e}")
            return None

    def _extract_email(self, text: str) -> str:
        """텍스트에서 이메일 추출"""
        if not text:
            return ""

        # 이메일 정규식
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        match = re.search(email_pattern, text)

        if match:
            return match.group(0)

        return ""

    def scrape_to_csv(self, keyword: str, limit: int = 200, output_file: str = None) -> str:
        """
        키워드 검색 후 CSV 저장

        Args:
            keyword: 검색 키워드
            limit: 수집할 개수
            output_file: 출력 파일 경로

        Returns:
            저장된 파일 경로
        """
        import csv
        import os

        if not output_file:
            output_file = f"results/{keyword}_api.csv"

        # 디렉토리 생성
        os.makedirs(os.path.dirname(output_file), exist_ok=True)

        # 검색 실행
        videos = self.search(keyword, limit)

        if not videos:
            logger.warning(f"수집된 데이터 없음: {keyword}")
            return ""

        # CSV 저장
        parsed_videos = []
        for video in videos:
            parsed = self.parse_video(video)
            if parsed:
                parsed['keyword'] = keyword
                parsed['scraped_at'] = datetime.now().isoformat()
                parsed['source_api'] = 'tiktok_api_v1'
                parsed_videos.append(parsed)

        # 중복 제거 (creator_username 기준)
        unique_videos = {}
        for v in parsed_videos:
            username = v['creator_username']
            if username and username not in unique_videos:
                unique_videos[username] = v

        # CSV 쓰기
        if unique_videos:
            with open(output_file, 'w', newline='', encoding='utf-8-sig') as f:
                fieldnames = [
                    'keyword', 'video_id', 'video_url', 'creator_id',
                    'creator_username', 'creator_nickname', 'creator_email',
                    'follower_count', 'following_count', 'video_count', 'heart_count',
                    'video_desc', 'create_time', 'hashtags', 'source_api', 'scraped_at'
                ]
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(unique_videos.values())

            logger.info(f"💾 저장 완료: {output_file} ({len(unique_videos)}개)")
            return output_file
        else:
            logger.warning("저장할 데이터 없음")
            return ""


# CLI 인터페이스
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='TikTok Fast API Scraper')
    parser.add_argument('-k', '--keyword', required=True, help='검색 키워드')
    parser.add_argument('-l', '--limit', type=int, default=200, help='수집할 개수')
    parser.add_argument('-o', '--output', help='출력 파일 경로')

    args = parser.parse_args()

    # 로깅 설정
    logging.basicConfig(
        level=logging.INFO,
        format='[%(asctime)s] %(levelname)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # 스크래퍼 실행
    scraper = FastTikTokAPIScraper()
    output_file = scraper.scrape_to_csv(
        keyword=args.keyword,
        limit=args.limit,
        output_file=args.output
    )

    if output_file:
        print(f"\n✅ 완료: {output_file}")
    else:
        print(f"\n❌ 실패")
