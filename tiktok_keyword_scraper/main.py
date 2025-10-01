#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Main entry point for TikTok keyword scraper
Integrates all Phase 1-4 improvements
"""

import argparse
import sys
import time
from datetime import datetime
from typing import List
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

from .models import CreatorProfile, VideoResult
from .scraper import TikTokSearchScraper
from .profile import ProfileScraper
from .cookie import CookieManager
from .email import EmailExtractor
from .config import ConfigManager
from .output import OutputManager
from .logger import setup_logger, get_logger


class TikTokKeywordScraperApp:
    """TikTok 키워드 스크래퍼 애플리케이션 (Phase 1-4 통합)"""

    def __init__(self, config_manager: ConfigManager, cli_args: dict):
        """
        Initialize application

        Args:
            config_manager: 설정 관리자
            cli_args: CLI 인자
        """
        self.config_manager = config_manager
        self.config = config_manager.create_scraper_config(cli_args)

        # 로깅 설정
        log_config = config_manager.get_logging_config()
        self.logger = setup_logger(
            name="tiktok_scraper",
            log_file=log_config.get("log_file", "tiktok_keyword_scraper.log"),
            level=log_config.get("level", "INFO"),
            console_level=log_config.get("console_level", "INFO"),
            file_level=log_config.get("file_level", "DEBUG")
        )

        # 쿠키 관리자
        self.cookie_manager = CookieManager(self.config.cookies_file)

        # 스크래퍼 초기화 (나중에)
        self.search_scraper = None
        self.profile_scraper = None

        # Phase 3: 기존 크리에이터 로드 (증분 스크래핑)
        self.existing_creators = set()
        if self.config.skip_existing:
            self.existing_creators = OutputManager.load_existing_creators(self.config.output_file)

    def run(self):
        """메인 실행 함수"""
        start_time = time.time()

        self.logger.info("=" * 60)
        self.logger.info("🚀 TikTok 키워드 검색 스크래퍼 시작")
        self.logger.info(f"   키워드: {', '.join(self.config.keywords)}")
        self.logger.info(f"   목표 비디오 수: {self.config.limit}")
        self.logger.info(f"   출력 파일: {self.config.output_file}")
        self.logger.info("=" * 60)

        try:
            # 초기화
            self._initialize_scrapers()

            # Phase 3: 다중 키워드 지원
            all_profiles = []
            for keyword in self.config.keywords:
                profiles = self._process_keyword(keyword)
                all_profiles.extend(profiles)

            # 결과 저장
            self._save_results(all_profiles)

            # 완료
            elapsed = time.time() - start_time
            self.logger.info("=" * 60)
            self.logger.info("✅ 스크래핑 완료!")
            self.logger.info(f"   처리된 크리에이터: {len(all_profiles)}명")
            self.logger.info(f"   소요 시간: {elapsed:.1f}초")
            self.logger.info(f"   출력 파일: {self.config.output_file}")
            self.logger.info("=" * 60)

        except KeyboardInterrupt:
            self.logger.warning("\n⚠️  사용자에 의해 중단되었습니다.")
            sys.exit(1)

        except Exception as e:
            self.logger.error(f"❌ 오류 발생: {e}", exc_info=True)
            sys.exit(1)

        finally:
            self._cleanup()

    def _initialize_scrapers(self):
        """스크래퍼 초기화"""
        # 검색 스크래퍼
        self.search_scraper = TikTokSearchScraper(
            cookie_manager=self.cookie_manager,
            headless=not self.config.use_browser,
            delay_min=self.config.delay_min,
            delay_max=self.config.delay_max,
            use_undetected=True
        )

        # 드라이버 설정
        driver = self.search_scraper.setup_driver()

        # 프로필 스크래퍼 (같은 드라이버 공유)
        self.profile_scraper = ProfileScraper(
            driver=driver,
            delay_min=self.config.delay_min,
            delay_max=self.config.delay_max
        )

    def _process_keyword(self, keyword: str) -> List[CreatorProfile]:
        """
        키워드 처리

        Args:
            keyword: 검색 키워드

        Returns:
            List[CreatorProfile]: 크리에이터 프로필 리스트
        """
        self.logger.info(f"\n🔍 키워드 '{keyword}' 처리 중...")

        # 1. 비디오 검색
        videos = self.search_scraper.search_videos_by_keyword(keyword, self.config.limit)

        if not videos:
            self.logger.warning(f"⚠️  '{keyword}' 검색 결과가 없습니다.")
            return []

        # 2. 조회수 기준 정렬
        videos.sort(key=lambda v: v.view_count, reverse=True)
        self.logger.info(f"📊 조회수 기준으로 정렬 완료")

        # 3. 크리에이터 프로필 조회
        profiles = self._fetch_profiles(keyword, videos)

        # 4. Phase 3: 필터링 적용
        profiles = self._apply_filters(profiles)

        return profiles

    def _fetch_profiles(self, keyword: str, videos: List[VideoResult]) -> List[CreatorProfile]:
        """
        크리에이터 프로필 조회

        Args:
            keyword: 검색 키워드
            videos: 비디오 리스트

        Returns:
            List[CreatorProfile]: 프로필 리스트
        """
        self.logger.info(f"\n👤 크리에이터 프로필 조회 시작 ({len(videos)}개)...")

        profiles = []
        processed_usernames = set()

        # Phase 4: 병렬 처리
        if self.config.parallel:
            profiles = self._fetch_profiles_parallel(keyword, videos)
        else:
            profiles = self._fetch_profiles_sequential(keyword, videos)

        return profiles

    def _fetch_profiles_sequential(self, keyword: str, videos: List[VideoResult]) -> List[CreatorProfile]:
        """순차 처리"""
        profiles = []
        processed_usernames = set()

        # tqdm 프로그레스 바
        for idx, video in enumerate(tqdm(videos, desc="프로필 조회", unit="profile")):
            username = video.creator_username

            # 중복 체크
            if username in processed_usernames:
                continue

            # Phase 3: 기존 크리에이터 스킵
            if username in self.existing_creators:
                self.logger.debug(f"  ⏭️  @{username} 스킵 (이미 존재)")
                continue

            processed_usernames.add(username)

            # 프로필 조회
            profile_data = self.profile_scraper.fetch_creator_profile(username)

            if not profile_data.get("success"):
                continue

            # CreatorProfile 생성
            profile = self._create_creator_profile(keyword, video, profile_data)
            if profile:
                profiles.append(profile)

                # Phase 4: 증분 저장 (10개마다)
                if len(profiles) % 10 == 0:
                    self._save_incremental(profiles[-10:])

        return profiles

    def _fetch_profiles_parallel(self, keyword: str, videos: List[VideoResult]) -> List[CreatorProfile]:
        """
        Phase 4: 병렬 처리
        """
        profiles = []
        processed_usernames = set()

        def fetch_single_profile(video):
            username = video.creator_username

            if username in processed_usernames or username in self.existing_creators:
                return None

            profile_data = self.profile_scraper.fetch_creator_profile(username)
            if not profile_data.get("success"):
                return None

            return self._create_creator_profile(keyword, video, profile_data)

        with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
            futures = {executor.submit(fetch_single_profile, video): video for video in videos}

            for future in tqdm(as_completed(futures), total=len(futures), desc="병렬 프로필 조회"):
                try:
                    profile = future.result()
                    if profile:
                        profiles.append(profile)
                        processed_usernames.add(profile.creator_username)

                        # 증분 저장
                        if len(profiles) % 10 == 0:
                            self._save_incremental(profiles[-10:])

                except Exception as e:
                    self.logger.error(f"프로필 조회 중 오류: {e}")

        return profiles

    def _create_creator_profile(self, keyword: str, video: VideoResult, profile_data: dict) -> CreatorProfile:
        """CreatorProfile 생성"""
        emails = profile_data.get("emails", [])
        email_str = EmailExtractor.get_primary_email(emails)

        return CreatorProfile(
            keyword=keyword,
            video_id=video.video_id,
            video_url=video.video_url,
            creator_id=video.creator_id,
            creator_username=video.creator_username,
            creator_email=email_str,
            follower_count=profile_data.get("follower_count", 0),
            view_count=video.view_count,
            like_count=video.like_count,
            comment_count=video.comment_count,
            hashtags=', '.join(video.hashtags),
            video_desc=video.video_desc,
            posted_date=video.posted_date or "",
            source_api="page_dom",
            extraction_method="profile_dom",
            scraped_at=datetime.now().isoformat(),
            notes=""
        )

    def _apply_filters(self, profiles: List[CreatorProfile]) -> List[CreatorProfile]:
        """
        Phase 3: 필터링 적용
        """
        filtered = profiles

        # 최소 팔로워 수 필터
        if self.config.min_followers > 0:
            before = len(filtered)
            filtered = [p for p in filtered if p.follower_count >= self.config.min_followers]
            self.logger.info(f"  📊 최소 팔로워 필터: {before} → {len(filtered)}")

        # 최소 조회수 필터
        if self.config.min_views > 0:
            before = len(filtered)
            filtered = [p for p in filtered if p.view_count >= self.config.min_views]
            self.logger.info(f"  📊 최소 조회수 필터: {before} → {len(filtered)}")

        # 이메일 필수 필터
        if self.config.email_required:
            before = len(filtered)
            filtered = [p for p in filtered if p.creator_email != 'example@example.com']
            self.logger.info(f"  📊 이메일 필수 필터: {before} → {len(filtered)}")

        return filtered

    def _save_results(self, profiles: List[CreatorProfile]):
        """결과 저장"""
        if not profiles:
            self.logger.warning("⚠️  저장할 프로필이 없습니다.")
            return

        self.logger.info(f"\n💾 결과 저장 중: {self.config.output_file}")

        # 출력 형식에 따라 저장
        if self.config.output_format == "xlsx":
            OutputManager.save_to_excel(profiles, self.config.output_file)
        else:
            # 증분 모드
            mode = 'a' if self.config.incremental else 'w'
            OutputManager.save_to_csv(profiles, self.config.output_file, mode=mode)

    def _save_incremental(self, profiles: List[CreatorProfile]):
        """증분 저장 (메모리 효율)"""
        if self.config.incremental and profiles:
            OutputManager.append_to_csv(profiles, self.config.output_file)

    def _cleanup(self):
        """정리"""
        if self.search_scraper:
            self.search_scraper.close()


def parse_args():
    """CLI 인자 파싱"""
    parser = argparse.ArgumentParser(
        description="TikTok Keyword Scraper - Search and export creator profiles",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    # 필수 인자
    parser.add_argument("-k", "--keywords", type=str, required=True,
                        help="검색 키워드 (쉼표로 구분, 예: 'kbeauty,skincare')")

    # 선택 인자
    parser.add_argument("-l", "--limit", type=int, default=None,
                        help="수집할 비디오 수 (기본값: config.yaml 또는 50)")
    parser.add_argument("-o", "--output", dest="output_file", type=str, default=None,
                        help="출력 파일 경로 (기본값: output.csv)")
    parser.add_argument("--format", dest="output_format", choices=["csv", "xlsx"], default=None,
                        help="출력 형식")
    parser.add_argument("--cookies", dest="cookies_file", type=str, default=None,
                        help="쿠키 파일 경로")

    # 지연 시간
    parser.add_argument("--delay-min", type=float, default=None,
                        help="최소 지연 시간 (초)")
    parser.add_argument("--delay-max", type=float, default=None,
                        help="최대 지연 시간 (초)")

    # 브라우저 옵션
    parser.add_argument("--use-browser", action="store_true",
                        help="브라우저 표시 모드 (CAPTCHA 해결용)")
    parser.add_argument("--headless", action="store_true", default=None,
                        help="헤드리스 모드")

    # Phase 3: 필터링
    parser.add_argument("--min-followers", type=int, default=None,
                        help="최소 팔로워 수")
    parser.add_argument("--min-views", type=int, default=None,
                        help="최소 조회수")
    parser.add_argument("--email-required", action="store_true",
                        help="이메일 필수")

    # Phase 3: 증분 스크래핑
    parser.add_argument("--incremental", action="store_true",
                        help="증분 스크래핑 모드")
    parser.add_argument("--skip-existing", action="store_true",
                        help="기존 크리에이터 스킵")

    # Phase 4: 병렬 처리
    parser.add_argument("--parallel", action="store_true",
                        help="병렬 처리 활성화")
    parser.add_argument("--max-workers", type=int, default=None,
                        help="병렬 워커 수")

    # 설정 파일
    parser.add_argument("--config", type=str, default="config.yaml",
                        help="설정 파일 경로")

    return parser.parse_args()


def main():
    """메인 함수"""
    args = parse_args()

    # 키워드 파싱
    keywords = [k.strip() for k in args.keywords.split(',')]

    # CLI 인자를 dict로 변환
    cli_args = {
        "keywords": keywords,
        "limit": args.limit,
        "output_file": args.output,
        "output_format": args.output_format,
        "cookies_file": args.cookies,
        "delay_min": args.delay_min,
        "delay_max": args.delay_max,
        "use_browser": args.use_browser,
        "headless": args.headless,
        "min_followers": args.min_followers,
        "min_views": args.min_views,
        "email_required": args.email_required,
        "incremental": args.incremental,
        "skip_existing": args.skip_existing,
        "parallel": args.parallel,
        "max_workers": args.max_workers,
    }

    # 설정 관리자
    config_manager = ConfigManager(args.config)

    # 애플리케이션 실행
    app = TikTokKeywordScraperApp(config_manager, cli_args)
    app.run()


if __name__ == "__main__":
    main()
