#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cookie Rotation Module for TikTok Scraping
쿠키 로테이션을 통한 Rate Limit 우회
"""

import json
import threading
from pathlib import Path
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class CookieRotator:
    """
    여러 쿠키 파일을 로테이션하여 Rate Limit 우회

    사용법:
        rotator = CookieRotator('data')
        cookies = rotator.get_next_cookies()  # 다음 쿠키
        cookies = rotator.get_cookies_for_worker(0)  # 워커별 고정 쿠키
    """

    def __init__(self, cookies_dir: str = 'data', pattern: str = '*cookies*.json'):
        """
        Args:
            cookies_dir: 쿠키 파일들이 있는 디렉토리
            pattern: 쿠키 파일 패턴 (기본: *cookies*.json)
        """
        self.cookies_dir = Path(cookies_dir)
        self.pattern = pattern
        self.cookie_files = []
        self.current_index = 0
        self.lock = threading.Lock()

        self._load_cookie_files()

        if not self.cookie_files:
            raise FileNotFoundError(
                f"쿠키 파일을 찾을 수 없음: {self.cookies_dir}/{pattern}\n"
                f"최소 1개 이상의 쿠키 파일이 필요합니다."
            )

        logger.info(f"✅ CookieRotator 초기화: {len(self.cookie_files)}개 쿠키 파일")
        for i, cf in enumerate(self.cookie_files, 1):
            logger.info(f"   {i}. {cf.name}")

    def _load_cookie_files(self):
        """쿠키 파일 목록 로드"""
        if not self.cookies_dir.exists():
            # 여러 경로 시도
            search_paths = [
                Path.cwd() / self.cookies_dir,
                Path(__file__).parent.parent / self.cookies_dir,
                Path(__file__).parent / self.cookies_dir,
            ]

            for path in search_paths:
                if path.exists():
                    self.cookies_dir = path
                    break

        if self.cookies_dir.exists():
            self.cookie_files = sorted(list(self.cookies_dir.glob(self.pattern)))

        # 파일이 없으면 configs 디렉토리도 시도
        if not self.cookie_files:
            configs_dir = self.cookies_dir.parent / 'configs'
            if configs_dir.exists():
                self.cookie_files = sorted(list(configs_dir.glob(self.pattern)))

    def _load_cookies_from_file(self, cookie_file: Path) -> Dict[str, str]:
        """
        쿠키 파일에서 쿠키 딕셔너리 로드

        Args:
            cookie_file: 쿠키 파일 경로

        Returns:
            쿠키 딕셔너리 {name: value}
        """
        try:
            with open(cookie_file, 'r', encoding='utf-8') as f:
                cookies_data = json.load(f)

            # List 형식 (Chrome extension export)
            if isinstance(cookies_data, list):
                cookies_dict = {}
                for cookie in cookies_data:
                    if isinstance(cookie, dict) and 'name' in cookie and 'value' in cookie:
                        cookies_dict[cookie['name']] = cookie['value']
                return cookies_dict

            # Dict 형식
            elif isinstance(cookies_data, dict):
                # 이미 {name: value} 형식이면 그대로 반환
                if all(isinstance(v, str) for v in cookies_data.values()):
                    return cookies_data
                # 중첩된 구조면 변환 시도
                else:
                    return {k: str(v) for k, v in cookies_data.items()}

            else:
                logger.warning(f"⚠️  지원하지 않는 쿠키 형식: {cookie_file.name}")
                return {}

        except Exception as e:
            logger.error(f"❌ 쿠키 로드 실패: {cookie_file.name} - {e}")
            return {}

    def get_next_cookies(self) -> Dict[str, str]:
        """
        다음 쿠키 가져오기 (Round-robin 방식)

        Returns:
            쿠키 딕셔너리 {name: value}
        """
        with self.lock:
            cookie_file = self.cookie_files[self.current_index]
            self.current_index = (self.current_index + 1) % len(self.cookie_files)

        cookies = self._load_cookies_from_file(cookie_file)
        logger.info(f"🔄 쿠키 로테이션: {cookie_file.name} ({len(cookies)}개 쿠키)")

        return cookies

    def get_cookies_for_worker(self, worker_id: int) -> Dict[str, str]:
        """
        워커 ID별로 고정 쿠키 할당

        Args:
            worker_id: 워커 ID (0부터 시작)

        Returns:
            쿠키 딕셔너리 {name: value}
        """
        cookie_file = self.cookie_files[worker_id % len(self.cookie_files)]
        cookies = self._load_cookies_from_file(cookie_file)

        logger.debug(f"👷 Worker {worker_id} → {cookie_file.name}")

        return cookies

    def get_all_cookies(self) -> List[Dict[str, str]]:
        """
        모든 쿠키 파일의 쿠키 로드

        Returns:
            쿠키 딕셔너리 리스트
        """
        all_cookies = []
        for cookie_file in self.cookie_files:
            cookies = self._load_cookies_from_file(cookie_file)
            if cookies:
                all_cookies.append(cookies)

        return all_cookies

    def get_cookie_count(self) -> int:
        """사용 가능한 쿠키 파일 수"""
        return len(self.cookie_files)

    def reload(self):
        """쿠키 파일 목록 재로드"""
        logger.info("🔄 쿠키 파일 목록 재로드 중...")
        self.cookie_files = []
        self.current_index = 0
        self._load_cookie_files()

        if not self.cookie_files:
            raise FileNotFoundError(
                f"쿠키 파일을 찾을 수 없음: {self.cookies_dir}/{self.pattern}"
            )

        logger.info(f"✅ 재로드 완료: {len(self.cookie_files)}개 쿠키 파일")


class SlidingWindowRateLimiter:
    """
    Sliding Window 기반 Rate Limiter (최대 대기 시간 제한 포함)

    사용법:
        limiter = SlidingWindowRateLimiter(max_requests_per_minute=30)
        limiter.acquire()  # 요청 전 호출 (필요 시 자동 대기, 최대 3초)
    """

    def __init__(self, max_requests_per_minute: int = 30, max_wait_time: float = 3.0):
        """
        Args:
            max_requests_per_minute: 분당 최대 요청 수
            max_wait_time: 최대 대기 시간 (초, 기본: 3초)
        """
        self.max_requests = max_requests_per_minute
        self.window_size = 10  # 10초 window (더 짧은 대기 시간)
        self.max_wait_time = max_wait_time
        self.requests = []  # 요청 타임스탬프 리스트
        self.lock = threading.Lock()

        logger.info(f"⏱️  Sliding Window Rate Limiter: {max_requests_per_minute} req/min (window: {self.window_size}초, 최대 대기: {max_wait_time}초)")

    def acquire(self) -> float:
        """
        요청 전 호출 - Rate limit 체크 및 필요 시 대기 (최대 대기 시간 제한)

        Returns:
            대기 시간 (초)
        """
        import time

        wait_time = 0  # 초기화

        with self.lock:
            now = time.time()

            # window_size 이전 요청 제거
            self.requests = [req_time for req_time in self.requests
                           if now - req_time < self.window_size]

            # 제한 초과 시 대기
            if len(self.requests) >= self.max_requests:
                oldest_time = self.requests[0]
                calculated_wait = self.window_size - (now - oldest_time) + 0.1

                # 최대 대기 시간 제한 적용
                wait_time = min(calculated_wait, self.max_wait_time)

                if wait_time > 0:
                    if wait_time < calculated_wait:
                        logger.warning(
                            f"⏳ Rate limit 도달 ({len(self.requests)}/{self.max_requests}). "
                            f"{wait_time:.1f}초 대기 (제한: {self.max_wait_time}초)"
                        )
                    else:
                        logger.info(
                            f"⏳ Rate limit 대기: {wait_time:.1f}초"
                        )

                    time.sleep(wait_time)

                    # 대기 후 다시 정리
                    now = time.time()
                    self.requests = [req_time for req_time in self.requests
                                   if now - req_time < self.window_size]

            # 요청 기록
            self.requests.append(now)

        return wait_time

    def get_current_count(self) -> int:
        """현재 1분 내 요청 수"""
        import time

        with self.lock:
            now = time.time()
            self.requests = [req_time for req_time in self.requests
                           if now - req_time < self.window_size]
            return len(self.requests)

    def reset(self):
        """Rate limiter 리셋"""
        with self.lock:
            self.requests = []
            logger.info("🔄 Rate limiter 리셋 완료")


# 테스트
if __name__ == '__main__':
    import logging

    logging.basicConfig(
        level=logging.INFO,
        format='[%(asctime)s] %(levelname)s: %(message)s'
    )

    print("=" * 60)
    print("CookieRotator 테스트")
    print("=" * 60)

    try:
        rotator = CookieRotator('data')
        print(f"\n✅ 쿠키 파일 {rotator.get_cookie_count()}개 로드 완료\n")

        # Round-robin 테스트
        print("📋 Round-robin 테스트:")
        for i in range(5):
            cookies = rotator.get_next_cookies()
            print(f"   {i+1}. 쿠키 개수: {len(cookies)}")

        # 워커별 쿠키 테스트
        print("\n👷 워커별 쿠키 할당 테스트:")
        for worker_id in range(3):
            cookies = rotator.get_cookies_for_worker(worker_id)
            print(f"   Worker {worker_id}: {len(cookies)}개 쿠키")

        print("\n✅ 테스트 완료!")

    except FileNotFoundError as e:
        print(f"\n❌ 오류: {e}")
        print("\n💡 해결 방법:")
        print("   1. data/ 디렉토리에 *cookies*.json 파일을 추가하세요")
        print("   2. 또는 configs/ 디렉토리에 쿠키 파일을 추가하세요")

    print("\n" + "=" * 60)
    print("SlidingWindowRateLimiter 테스트")
    print("=" * 60)

    limiter = SlidingWindowRateLimiter(max_requests_per_minute=5)

    print("\n📊 5회 연속 요청 테스트 (제한: 5 req/min):")
    import time
    for i in range(7):
        start = time.time()
        limiter.acquire()
        elapsed = time.time() - start
        print(f"   요청 {i+1}: 대기 {elapsed:.2f}초 | 현재 카운트: {limiter.get_current_count()}")

    print("\n✅ 테스트 완료!")
