#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hybrid TikTok Scraper
- Phase 1: API로 빠르게 10-12개 수집 (2초)
- Phase 2: 부족하면 DOM으로 나머지 수집 (필요한 만큼만)
- 최적화된 속도 + 안정성
"""

import logging
import json
import time
from typing import List, Dict, Optional
from datetime import datetime

from .fast_api_scraper import FastTikTokAPIScraper
from .scraper import TikTokSearchScraper, CaptchaDetectedException
from .cookie import CookieManager
from .models import VideoResult

logger = logging.getLogger(__name__)


class HybridTikTokScraper:
    """하이브리드 TikTok 스크래퍼 (API + DOM) - 개선된 스크롤 감지 적용"""

    def __init__(self, cookie_manager: CookieManager, headless: bool = False,
                 delay_min: float = 2.0, delay_max: float = 4.0):
        """
        Args:
            cookie_manager: 쿠키 관리자
            headless: 헤드리스 모드 (DOM 스크래핑용)
            delay_min: 최소 지연
            delay_max: 최대 지연
        """
        self.cookie_manager = cookie_manager
        self.headless = headless
        self.delay_min = delay_min
        self.delay_max = delay_max

        # API 스크래퍼 (빠름)
        self.api_scraper = None
        try:
            self.api_scraper = FastTikTokAPIScraper()
            logger.info("✅ API 스크래퍼 초기화 완료")
        except Exception as e:
            logger.warning(f"⚠️  API 스크래퍼 초기화 실패: {e}")

        # DOM 스크래퍼 (느리지만 안정적)
        self.dom_scraper = None

        # 스크롤 통계 추적
        self.scroll_stats = {
            'total_scrolls': 0,
            'successful_scrolls': 0,
            'failed_scrolls': 0
        }

    def _init_dom_scraper(self, driver):
        """DOM 스크래퍼 초기화 (필요할 때만) - 개선된 설정 적용"""
        if not self.dom_scraper:
            # 하이브리드 모드에서는 더 공격적인 설정 사용
            hybrid_delay_min = max(1.5, self.delay_min - 0.5)  # 약간 더 빠른 설정
            hybrid_delay_max = max(2.5, self.delay_max - 0.5)

            self.dom_scraper = TikTokSearchScraper(
                cookie_manager=self.cookie_manager,
                headless=self.headless,
                delay_min=hybrid_delay_min,
                delay_max=hybrid_delay_max,
                use_undetected=False
            )
            self.dom_scraper.driver = driver
            logger.info(f"✅ DOM 스크래퍼 초기화 완료 (하이브리드 모드: {hybrid_delay_min}-{hybrid_delay_max}초 지연)")

    def scrape_hybrid(self, keyword: str, limit: int = 200, driver=None) -> List[VideoResult]:
        """
        하이브리드 스크래핑

        Args:
            keyword: 검색 키워드
            limit: 목표 개수
            driver: Selenium WebDriver (DOM 스크래핑용)

        Returns:
            VideoResult 리스트
        """
        all_results = []
        collected_usernames = set()  # 중복 방지

        # Phase 1: API 스크래핑 (빠름)
        logger.info(f"🚀 Phase 1: API 스크래핑 시작 ({keyword})")

        if self.api_scraper:
            try:
                api_videos = self.api_scraper.search(keyword, limit=min(20, limit))

                # API 응답을 VideoResult로 변환
                for video_data in api_videos:
                    parsed = self.api_scraper.parse_video(video_data)
                    if parsed and parsed['creator_username']:
                        username = parsed['creator_username']

                        # 중복 체크
                        if username not in collected_usernames:
                            video_result = VideoResult(
                                video_id=parsed['video_id'],
                                video_url=parsed['video_url'],
                                creator_id=parsed['creator_id'],
                                creator_username=username,
                                view_count=0,
                                like_count=0,
                                video_desc=parsed['video_desc'],
                                hashtags=[]  # 불필요한 필드 제거로 성능 최적화
                            )
                            all_results.append(video_result)
                            collected_usernames.add(username)

                logger.info(f"   ✅ API로 {len(all_results)}개 수집")

            except Exception as e:
                logger.error(f"   ❌ API 스크래핑 실패: {e}")

        # Phase 2: DOM 스크래핑 (필요한 만큼만, 개선된 알고리즘)
        remaining = limit - len(all_results)

        if remaining > 0 and driver:
            logger.info(f"🔄 Phase 2: DOM 스크래핑 시작 (부족: {remaining}개)")

            try:
                self._init_dom_scraper(driver)

                # API 수집율에 따른 DOM 스크래핑 전략 결정
                api_collection_rate = len(all_results) / min(20, limit) if all_results else 0

                # DOM 스크래핑 목표량 계산 (API 수집율에 따라 조정)
                if api_collection_rate >= 0.8:  # API가 잘 수집된 경우
                    dom_target = remaining + 40  # 최소 여유분 확대
                elif api_collection_rate >= 0.5:  # API가 보통 수준으로 수집된 경우
                    dom_target = remaining + 60
                else:  # API 수집이 부족한 경우
                    dom_target = remaining + 80

                logger.info(f"📊 API 수집율: {api_collection_rate:.1%}, DOM 목표: {dom_target}개")

                # DOM으로 추가 수집 (개선된 스크롤 감지 로직 적용)
                dom_results = self.dom_scraper.search_videos_by_keyword(
                    keyword=keyword,
                    limit=max(dom_target, limit + 40)
                )

                # 중복 제거하며 추가
                added = 0
                for video in dom_results:
                    if video.creator_username not in collected_usernames:
                        all_results.append(video)
                        collected_usernames.add(video.creator_username)
                        added += 1

                        # 목표 달성 시 조기 종료
                        if len(all_results) >= limit:
                            logger.info(f"🎯 목표 개수({limit}) 달성으로 조기 종료")
                            break

                logger.info(f"   ✅ DOM으로 {added}개 추가 수집 (총 {len(all_results)}/{limit})")

                # 최종 상태 체크
                if len(all_results) < limit:
                    logger.warning(f"⚠️ 목표 개수({limit})에 미달: {len(all_results)}개 수집")

            except CaptchaDetectedException as e:
                logger.error(f"   ❌ 헤드리스 모드에서 CAPTCHA 감지: {e}")
                # CAPTCHA 예외는 다시 발생시켜서 호출자가 브라우저 모드로 재시작할 수 있도록 함
                raise e
            except Exception as e:
                logger.error(f"   ❌ DOM 스크래핑 실패: {e}")

        # 최종 통계 로깅
        success_rate = len(all_results) / limit * 100 if limit > 0 else 0
        logger.info(f"🎉 총 {len(all_results)}개 수집 완료 (성공률: {success_rate:.1f}%)")

        # 스크롤 통계 로깅
        if hasattr(self.dom_scraper, 'driver') and self.scroll_stats['total_scrolls'] > 0:
            scroll_success_rate = self.scroll_stats['successful_scrolls'] / self.scroll_stats['total_scrolls'] * 100
            logger.info(f"📊 스크롤 통계: 총 {self.scroll_stats['total_scrolls']}회, 성공 {self.scroll_stats['successful_scrolls']}회, 실패 {self.scroll_stats['failed_scrolls']}회 (성공률: {scroll_success_rate:.1f}%)")

        return all_results[:limit]

    def estimate_time(self, limit: int) -> float:
        """
        예상 소요 시간 계산 (개선된 알고리즘)

        Args:
            limit: 목표 개수

        Returns:
            예상 시간 (초)
        """
        api_time = 2  # API는 고정 2초
        api_count = min(15, limit)  # API 수집량을 12개에서 15개로 상향 조정

        remaining = limit - api_count

        # API 수집율에 따른 DOM 시간 예측
        if remaining <= 0:
            return api_time  # API만으로 충분한 경우
        elif remaining <= 20:
            dom_time_per_video = 3.5  # 적은 수량은 더 빠름
        elif remaining <= 50:
            dom_time_per_video = 4.0  # 보통 수량
        else:
            dom_time_per_video = 4.5  # 많은 수량은 약간 느림

        dom_time = remaining * dom_time_per_video

        total_time = api_time + dom_time

        logger.info(f"📊 예상 시간 계산: API({api_count}개) + DOM({remaining}개) = 총 {total_time:.0f}초 ({total_time/60:.1f}분)")

        return total_time


# CLI 테스트
if __name__ == "__main__":
    import argparse
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from webdriver_manager.chrome import ChromeDriverManager

    parser = argparse.ArgumentParser(description='Hybrid TikTok Scraper')
    parser.add_argument('-k', '--keyword', required=True, help='검색 키워드')
    parser.add_argument('-l', '--limit', type=int, default=50, help='수집할 개수')
    parser.add_argument('--use-browser', action='store_true', help='브라우저 모드')

    args = parser.parse_args()

    # 로깅 설정
    logging.basicConfig(
        level=logging.INFO,
        format='[%(asctime)s] %(levelname)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # 쿠키 관리자
    cookie_manager = CookieManager('cookies.json')

    # 하이브리드 스크래퍼
    scraper = HybridTikTokScraper(
        cookie_manager=cookie_manager,
        headless=not args.use_browser
    )

    # 예상 시간
    estimated = scraper.estimate_time(args.limit)
    logger.info(f"📊 예상 소요 시간: {estimated:.0f}초 ({estimated/60:.1f}분)")

    # Selenium 드라이버 (DOM 스크래핑용) - 헤드리스 모드 강화
    options = Options()

    if not args.use_browser:
        # 헤드리스 모드 강화 (CAPTCHA 회피용)
        options.add_argument("--headless=new")

        # 자동화 감지 회피를 위한 추가 옵션들
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-features=VizDisplayCompositor")
        options.add_argument("--disable-ipc-flooding-protection")

        # 자연스러운 브라우저처럼 보이게 하기
        options.add_argument("--disable-web-security")
        options.add_argument("--disable-features=VizHitTestSurfaceLayer")
        options.add_argument("--disable-background-timer-throttling")
        options.add_argument("--disable-renderer-backgrounding")
        options.add_argument("--disable-backgrounding-occluded-windows")

        # 성능 및 안정성 옵션
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-software-rasterizer")

        # 메모리 및 네트워크 옵션
        options.add_argument("--memory-pressure-off")
        options.add_argument("--max_old_space_size=4096")
        options.add_argument("--disable-http2")

        # 추가 헤더 설정 (자연스러운 브라우저처럼)
        options.add_argument("--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

        print("🔧 헤드리스 모드 강화 옵션 적용 완료")
    else:
        # 브라우저 모드에서도 일부 옵션 적용
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-web-security")
        print("🔧 브라우저 모드 옵션 적용 완료")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    try:
        # 초기 페이지 로드
        driver.get("https://www.tiktok.com")
        time.sleep(3)

        # 하이브리드 스크래핑
        results = scraper.scrape_hybrid(
            keyword=args.keyword,
            limit=args.limit,
            driver=driver
        )

        # 결과 저장
        import csv
        import os

        output_file = f"results/{args.keyword}_hybrid.csv"
        os.makedirs('results', exist_ok=True)

        with open(output_file, 'w', newline='', encoding='utf-8-sig') as f:
            fieldnames = [
                'keyword', 'video_id', 'video_url', 'creator_id',
                'creator_username', 'video_desc', 'scraped_at'
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for result in results:
                writer.writerow({
                    'keyword': args.keyword,
                    'video_id': result.video_id,
                    'video_url': result.video_url,
                    'creator_id': result.creator_id,
                    'creator_username': result.creator_username,
                    'video_desc': result.video_desc,
                    'scraped_at': datetime.now().isoformat()
                })

        print(f"\n✅ 완료: {output_file} ({len(results)}개)")

    finally:
        driver.quit()
