#!/usr/bin/env python3
"""
HTTP 요청으로 팔로워 수와 이메일 추출 및 CSV 업데이트
Rate Limiting 강화: Cookie Rotation + Sliding Window
"""

import os
import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import json
import re
import time
import html
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, List
import threading
import random
import sys

# CookieRotator 및 SlidingWindowRateLimiter 임포트
sys.path.insert(0, str(Path(__file__).parent / 'tiktok_keyword_scraper'))
from cookie_rotator import CookieRotator, SlidingWindowRateLimiter


class FollowerCountExtractor:
    """HTTP 요청으로 팔로워 수 추출"""

    # User-Agent 리스트 (다양한 브라우저/디바이스)
    USER_AGENTS = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        'Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1',
    ]

    def __init__(self, cookies_file: str = 'cookies.json', verbose: bool = False, proxy_file: Optional[str] = None,
                 conservative_mode: bool = False, use_cookie_rotation: bool = True,
                 requests_per_minute: int = 30):
        """
        초기화

        Args:
            cookies_file: 단일 쿠키 파일 경로 (use_cookie_rotation=False인 경우)
            verbose: 상세 로깅
            proxy_file: 프록시 파일 경로
            conservative_mode: 보수적 모드 (느리지만 안정적)
            use_cookie_rotation: 쿠키 로테이션 사용 여부
            requests_per_minute: 분당 최대 요청 수
        """
        self.verbose = verbose
        self.conservative_mode = conservative_mode
        self.use_cookie_rotation = use_cookie_rotation

        # 프록시 리스트 로드
        self.proxies_list = []
        self.proxy_index = 0
        self.proxy_lock = threading.Lock()
        if proxy_file:
            self.proxies_list = self._load_proxies(proxy_file)
            if self.proxies_list:
                print(f"✅ 프록시 로드: {len(self.proxies_list)}개")

        # 쿠키 로테이션 설정
        if use_cookie_rotation:
            try:
                # data 디렉토리에서 쿠키 파일들 로드
                cookies_dir = Path(__file__).parent / 'data'
                if not cookies_dir.exists():
                    cookies_dir = Path.cwd() / 'data'

                self.cookie_rotator = CookieRotator(str(cookies_dir))
                self.cookies = self.cookie_rotator.get_next_cookies()
                print(f"✅ 쿠키 로테이션 활성화: {self.cookie_rotator.get_cookie_count()}개 쿠키")

                # 쿠키 교체 주기 설정
                self.cookie_rotation_interval = 20  # 20요청마다 쿠키 교체
                self.request_count = 0

            except FileNotFoundError as e:
                print(f"⚠️  쿠키 로테이션 실패: {e}")
                print("   단일 쿠키 모드로 전환합니다.")
                self.use_cookie_rotation = False
                cookies_path = self._resolve_cookies_path(cookies_file)
                with cookies_path.open('r', encoding='utf-8') as f:
                    cookies_list = json.load(f)
                self.cookies = {cookie['name']: cookie['value'] for cookie in cookies_list}
        else:
            # 단일 쿠키 모드
            cookies_path = self._resolve_cookies_path(cookies_file)
            with cookies_path.open('r', encoding='utf-8') as f:
                cookies_list = json.load(f)
            self.cookies = {cookie['name']: cookie['value'] for cookie in cookies_list}
            print("ℹ️  단일 쿠키 모드")

        # Sliding Window Rate Limiter 초기화 (최대 대기 3초)
        self.rate_limiter = SlidingWindowRateLimiter(
            max_requests_per_minute=requests_per_minute,
            max_wait_time=3.0  # 최대 3초 대기
        )
        print(f"✅ Sliding Window Rate Limiter: {requests_per_minute} req/min (최대 대기: 3초)")

        # 세션 생성 및 Connection Pool 최적화
        self.session = requests.Session()

        # HTTPAdapter로 Connection Pool 설정 (동시 연결 최적화)
        adapter = HTTPAdapter(
            pool_connections=10,  # Connection pool 크기
            pool_maxsize=10,      # 최대 연결 수
            max_retries=0,        # 자체 재시도 로직 사용
            pool_block=False
        )
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)

        self.session.cookies.update(self.cookies)

        # 기본 헤더 (User-Agent는 요청마다 변경)
        self.base_headers = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'en-US,en;q=0.9,ko;q=0.8',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
            'Referer': 'https://www.tiktok.com/',
        }
        self.session.headers.update(self.base_headers)

        # Rate limiting (보수적/공격적 모드)
        self.lock = threading.Lock()
        self.last_request_time = 0

        if conservative_mode:
            self.min_delay = 1.0  # 보수적 모드: 1초
            self.max_delay = 3.0
            print("🐢 보수적 모드: 느리지만 안정적")
        else:
            self.min_delay = 0.4  # 기본: 0.4초
            self.max_delay = 0.6  # 기본: 0.6초
            print("🚀 일반 모드: 0.4~0.6초 랜덤 딜레이")

        # 실패 카운터 (연속 실패 시 속도 조절)
        self.consecutive_failures = 0
        self.failure_threshold = 5

    def _resolve_cookies_path(self, cookies_file: str) -> Path:
        """쿠키 파일 경로를 탐색하고 확인한다."""
        search_paths = []

        # 1. 환경 변수 우선
        env_path = os.getenv('TIKTOK_COOKIES_FILE')
        if env_path:
            search_paths.append(Path(env_path).expanduser())

        # 2. 인자로 받은 경로 (절대/상대)
        input_path = Path(cookies_file).expanduser()
        if input_path.is_absolute():
            search_paths.append(input_path)
        else:
            # CWD 기준
            search_paths.append(Path.cwd() / input_path)

        # 3. 스크립트 기준 추가 후보
        script_dir = Path(__file__).resolve().parent
        search_paths.extend([
            script_dir / input_path,
            script_dir / 'configs' / input_path,
            script_dir / 'data' / input_path,
        ])

        # 중복 제거 preserving order
        unique_paths = []
        seen = set()
        for path in search_paths:
            resolved = path if path.is_absolute() else path.resolve()
            if resolved not in seen:
                seen.add(resolved)
                unique_paths.append(path)

        for path in unique_paths:
            if path.is_file():
                return path

        attempted = '\n'.join(f" - {path}" for path in unique_paths)
        raise FileNotFoundError(
            "쿠키 파일을 찾을 수 없습니다. 아래 경로들을 확인해 주세요:\n"
            f"{attempted}\n"
            "환경 변수 TIKTOK_COOKIES_FILE를 설정하거나 '--cookies-file' 인자를 사용해 주세요."
        )

    def _load_proxies(self, proxy_file: str) -> List[str]:
        """프록시 리스트 파일 로드"""
        proxies = []
        try:
            proxy_path = Path(proxy_file)
            if not proxy_path.exists():
                # 여러 경로 시도
                for base in [Path.cwd(), Path(__file__).parent, Path(__file__).parent / 'data']:
                    test_path = base / proxy_file
                    if test_path.exists():
                        proxy_path = test_path
                        break

            if proxy_path.exists():
                with open(proxy_path, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            # http://ip:port 또는 http://user:pass@ip:port 형식 지원
                            if not line.startswith('http'):
                                line = f'http://{line}'
                            proxies.append(line)
            else:
                print(f"⚠️  프록시 파일을 찾을 수 없음: {proxy_file}")
        except Exception as e:
            print(f"⚠️  프록시 로드 실패: {e}")

        return proxies

    def _get_next_proxy(self) -> Optional[dict]:
        """다음 프록시 가져오기 (라운드 로빈)"""
        if not self.proxies_list:
            return None

        with self.proxy_lock:
            proxy_url = self.proxies_list[self.proxy_index]
            self.proxy_index = (self.proxy_index + 1) % len(self.proxies_list)

        return {
            'http': proxy_url,
            'https': proxy_url
        }

    def extract_profile_info(self, username: str, max_retries: int = 3) -> tuple[Optional[int], Optional[str]]:
        """
        Username으로 팔로워 수와 이메일 추출

        Args:
            username: TikTok username
            max_retries: 재시도 횟수

        Returns:
            (팔로워 수, 이메일) 또는 (None, None) (실패시)
        """
        # Sliding Window Rate Limiter로 요청 제어
        self.rate_limiter.acquire()

        # 쿠키 로테이션 (일정 요청마다)
        if self.use_cookie_rotation:
            self.request_count += 1
            if self.request_count % self.cookie_rotation_interval == 0:
                self.cookies = self.cookie_rotator.get_next_cookies()
                self.session.cookies.update(self.cookies)
                if self.verbose:
                    print(f"   🔄 쿠키 교체 ({self.request_count}번째 요청)")

        # Rate limiting with random delay (추가 자연스러움)
        with self.lock:
            elapsed = time.time() - self.last_request_time

            # 랜덤 딜레이 추가 (더 자연스럽게)
            delay = random.uniform(self.min_delay, self.max_delay)

            # 연속 실패 시 더 긴 대기
            if self.consecutive_failures >= self.failure_threshold:
                delay *= 2
                if self.verbose:
                    print(f"   ⚠️ 연속 실패 감지 - 대기 시간 2배 증가: {delay:.1f}초")

            if elapsed < delay:
                time.sleep(delay - elapsed)
            self.last_request_time = time.time()

        for attempt in range(max_retries):
            try:
                # User-Agent 랜덤 선택
                user_agent = random.choice(self.USER_AGENTS)
                headers = self.base_headers.copy()
                headers['User-Agent'] = user_agent

                # 프록시 가져오기
                proxy = self._get_next_proxy()

                # 프로필 페이지 요청
                profile_url = f"https://www.tiktok.com/@{username}"
                response = self.session.get(profile_url, timeout=10, proxies=proxy, headers=headers)

                # 429 Rate Limit 처리
                if response.status_code == 429:
                    retry_after = int(response.headers.get('Retry-After', 60))
                    if self.verbose:
                        print(f"   ⚠️ Rate Limit (429)! {retry_after}초 대기...")
                    time.sleep(retry_after)

                    # 쿠키 강제 교체
                    if self.use_cookie_rotation:
                        self.cookies = self.cookie_rotator.get_next_cookies()
                        self.session.cookies.update(self.cookies)
                        if self.verbose:
                            print(f"   🔄 쿠키 강제 교체 (429 응답)")

                    if attempt < max_retries - 1:
                        continue
                    return None, None

                if response.status_code != 200:
                    if attempt < max_retries - 1:
                        time.sleep(0.5 * (attempt + 1))  # 더 짧은 backoff
                        continue
                    return None, None

                html_content = response.text
                follower_count = None
                email = None

                # 방법 1: Embedded JSON에서 추출
                pattern = r'<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__" type="application/json">(.*?)</script>'
                matches = re.findall(pattern, html_content, re.DOTALL)

                if matches:
                    try:
                        data = json.loads(matches[0])
                        scope = data.get('__DEFAULT_SCOPE__', {})
                        user_detail = scope.get('webapp.user-detail', {})
                        user_info = user_detail.get('userInfo', {})
                        stats = user_info.get('stats', {})

                        follower_count = stats.get('followerCount')

                        if follower_count is not None:
                            follower_count = int(follower_count)
                        # else: follower_count remains None

                        # 이메일 정보 찾기 (bio, signature, bioLink 등 포함)
                        user_record = user_info.get('user', {})
                        text_candidates = []

                        bio = user_info.get('bio')
                        if bio:
                            text_candidates.append(bio)

                        signature = user_record.get('signature')
                        if signature:
                            text_candidates.append(signature)

                        signature_l2 = user_record.get('signatureL2')
                        if signature_l2:
                            text_candidates.append(signature_l2)

                        bio_link = user_record.get('bioLink')
                        if isinstance(bio_link, dict):
                            link_value = bio_link.get('link')
                            title_value = bio_link.get('title')
                            if link_value:
                                text_candidates.append(link_value)
                            if title_value:
                                text_candidates.append(title_value)

                        for candidate_text in text_candidates:
                            extracted_email = self._extract_first_email(candidate_text)
                            if extracted_email:
                                email = extracted_email
                                break

                    except Exception as e:
                        if self.verbose:
                            print(f"   JSON 파싱 에러: {e}")
                        pass

                # 방법 2: HTML에서 직접 이메일 추출 (개선된 방식)
                if not email:
                    email = self._extract_first_email(html_content)

                # 성공 시 연속 실패 카운터 리셋
                with self.lock:
                    if self.consecutive_failures > 0:
                        self.consecutive_failures = 0

                return follower_count, email

            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(0.5 * (attempt + 1))  # 더 짧은 backoff
                    continue

                if self.verbose:
                    print(f"\n🚨 디버깅 정보 - @{username}: {str(e)}")

                # 실패 카운터 증가
                with self.lock:
                    self.consecutive_failures += 1

                return None, None

        # 최종 실패
        with self.lock:
            self.consecutive_failures += 1

        return None, None

    def _is_valid_email(self, email: str) -> bool:
        """
        이메일 주소 유효성 검증 (강화된 버전)

        Args:
            email: 검증할 이메일 주소

        Returns:
            유효한 이메일이면 True, 그렇지 않으면 False
        """
        if not email or '@' not in email:
            return False

        # HTML 엔티티나 유니코드 이스케이프 시퀀스 제거
        clean_email = html.unescape(email).strip()

        # 기본 이메일 패턴 검증 (더 엄격한 패턴)
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, clean_email):
            return False

        # 유니코드 이스케이프 시퀀스나 이상한 문자 제거 후 재검증
        if '\\u' in clean_email or 'u002' in clean_email:
            return False

        # 일반적인 이메일 도메인 제외 (너무 일반적인 것은 제외)
        excluded_domains = [
            'example.com', 'test.com', 'sample.com', 'domain.com',
            'email.com', 'mail.com', 'placeholder.com'
        ]

        domain = clean_email.split('@')[-1].lower()
        if domain in excluded_domains:
            return False

        # 너무 짧거나 긴 이메일 제외
        if len(clean_email) < 5 or len(clean_email) > 100:
            return False

        return True

    def _extract_first_email(self, raw_text: Optional[str]) -> Optional[str]:
        """문자열에서 첫 번째 유효한 이메일을 찾아 반환한다."""
        if not raw_text:
            return None

        decoded_text = html.unescape(str(raw_text))

        primary_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b'
        fallback_pattern = r'[\w.+-]+@[\w-]+\.[\w.-]+'

        primary_match = re.search(primary_pattern, decoded_text)
        if primary_match:
            candidate = primary_match.group(0).lower()
            if self._is_valid_email(candidate):
                return candidate

        for match in re.findall(fallback_pattern, decoded_text):
            normalized = match.lower()
            if self._is_valid_email(normalized):
                return normalized

        return None


def enrich_csv_with_followers(
    input_file: Path,
    output_file: Path,
    max_workers: int = 8,
    checkpoint_interval: int = 100,
    proxy_file: Optional[str] = None,
    conservative_mode: bool = False,
    use_cookie_rotation: bool = True,
    requests_per_minute: int = 30,
    max_retry_attempts: int = 3
):
    """
    CSV에 팔로워 수 추가

    Args:
        input_file: 입력 CSV 파일
        output_file: 출력 CSV 파일
        max_workers: 병렬 워커 수
        checkpoint_interval: 중간 저장 간격
        proxy_file: 프록시 파일 경로
        conservative_mode: 보수적 모드
        use_cookie_rotation: 쿠키 로테이션 사용
        requests_per_minute: 분당 최대 요청 수
        max_retry_attempts: 최대 재시도 횟수 (기본: 3)
    """
    print("=" * 60)
    print("팔로워 수 추출 및 CSV 업데이트")
    print("=" * 60)

    # CSV 로드
    source_file = output_file if output_file.exists() else input_file
    if source_file == output_file:
        print(f"\n📂 파일 로드: {output_file.name} (재시작)")
    else:
        print(f"\n📂 파일 로드: {input_file.name}")

    original_df = pd.read_csv(source_file)

    # 입력 파일에만 있는 신규 행을 병합
    additional_rows = pd.DataFrame()
    if source_file == output_file and input_file.exists():
        input_df = pd.read_csv(input_file)
        if 'creator_username' in input_df.columns and 'creator_username' in original_df.columns:
            existing_usernames = set(original_df['creator_username'].dropna())
            mask_new = ~input_df['creator_username'].isin(existing_usernames)
            additional_rows = input_df[mask_new].copy()

            if not additional_rows.empty:
                print(f"   ➕ 신규 행 추가: {len(additional_rows):,}개 (입력 파일 기반)")

                if 'email_checked' not in additional_rows.columns:
                    additional_rows['email_checked'] = False
                else:
                    additional_rows['email_checked'] = False

                if 'retry_count' not in additional_rows.columns:
                    additional_rows['retry_count'] = 0

                if 'creator_email' not in additional_rows.columns:
                    additional_rows['creator_email'] = ''

                # 원본과 컬럼 정렬
                for col in original_df.columns:
                    if col not in additional_rows.columns:
                        additional_rows[col] = pd.NA

                for col in additional_rows.columns:
                    if col not in original_df.columns:
                        original_df[col] = pd.NA

                original_df = pd.concat([original_df, additional_rows[original_df.columns]], ignore_index=True, sort=False)
        else:
            print("   ⚠️ creator_username 열을 찾을 수 없어 신규 행 병합을 건너뜁니다.")

    total_original = len(original_df)
    print(f"   총 프로필: {total_original:,}개")

    # 이메일 체크 상태 및 retry_count 확인
    if 'email_checked' not in original_df.columns:
        original_df['email_checked'] = False

    if 'retry_count' not in original_df.columns:
        original_df['retry_count'] = 0

    # 이미 이메일이 있는 사용자들
    df_with_email = original_df[original_df['creator_email'].notna() & (original_df['creator_email'] != '')]

    # 재처리 대상 필터링:
    # 1. (이메일 없음 AND email_checked=False) OR
    # 2. (이메일 없음 AND follower_count=0 AND retry_count < 2)
    df_without_email = original_df[
        (original_df['creator_email'].isna() | (original_df['creator_email'] == '')) &
        (
            (~original_df['email_checked']) |  # 아직 체크 안 됨
            ((original_df['follower_count'] == 0) & (original_df['retry_count'] < 2))  # 실패했지만 재시도 가능
        )
    ]

    # 재시도 제한 초과 (retry_count >= 2)
    retry_exceeded = original_df[
        (original_df['creator_email'].isna() | (original_df['creator_email'] == '')) &
        (original_df['follower_count'] == 0) &
        (original_df['retry_count'] >= 2)
    ]

    print(f"   이메일 보유: {len(df_with_email):,}개")
    print(f"   재처리 대상: {len(df_without_email):,}개")
    print(f"   재시도 한도 초과: {len(retry_exceeded):,}개 (retry_count >= 2)")
    print(f"   기타: {len(original_df) - len(df_with_email) - len(df_without_email) - len(retry_exceeded):,}개")

    if len(df_without_email) == 0:
        print("   ✅ 이메일 미보유 사용자가 없거나 이미 모두 체크되었습니다.")
        # 원본 파일을 출력 파일로 복사
        original_df.to_csv(output_file, index=False, encoding='utf-8-sig')
        print(f"   💾 원본 파일을 복사: {output_file}")
        return original_df

    # 이메일이 없는 사용자만 처리
    df = df_without_email.copy()

    # 출력용 데이터프레임 (원본 복사본) 준비
    output_df = original_df.copy()
    total = len(df)

    # 재시도 사용자와 신규 사용자 구분
    retry_users = df[df['retry_count'] > 0]
    new_users = df[df['retry_count'] == 0]

    print(f"   📋 처리 대상: {total:,}개 (신규: {len(new_users):,}개, 재시도: {len(retry_users):,}개)")

    # Extractor 초기화
    extractor = FollowerCountExtractor(
        proxy_file=proxy_file,
        conservative_mode=conservative_mode,
        use_cookie_rotation=use_cookie_rotation,
        requests_per_minute=requests_per_minute
    )

    # 진행 상황 추적
    completed = 0
    success = 0
    failed = 0

    print(f"\n🚀 팔로워 수 추출 시작 (워커: {max_workers}개)")
    print(f"   중간 저장 간격: {checkpoint_interval}개")
    print()

    start_time = time.time()

    # 병렬 처리
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 작업 제출
        future_to_idx = {}
        for idx, row in df.iterrows():
            username = row['creator_username']
            future = executor.submit(extractor.extract_profile_info, username)
            future_to_idx[future] = idx

        # 결과 처리
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            username = df.loc[idx, 'creator_username']

            try:
                follower_count, email = future.result()

                # 현재 retry_count 가져오기
                current_retry = df.at[idx, 'retry_count'] if pd.notna(df.at[idx, 'retry_count']) else 0

                # 성공 시
                if follower_count is not None and follower_count > 0:
                    df.at[idx, 'follower_count'] = follower_count
                    df.at[idx, 'email_checked'] = True
                    df.at[idx, 'retry_count'] = 0  # 성공 시 retry_count 리셋

                    output_df.at[idx, 'follower_count'] = follower_count
                    output_df.at[idx, 'email_checked'] = True
                    output_df.at[idx, 'retry_count'] = 0

                    success += 1
                    status = f"✅ 팔로워: {follower_count:,}"

                # 실패 시
                else:
                    df.at[idx, 'follower_count'] = 0
                    df.at[idx, 'retry_count'] = current_retry + 1

                    output_df.at[idx, 'follower_count'] = 0
                    output_df.at[idx, 'retry_count'] = current_retry + 1

                    # retry_count >= 2이면 더 이상 재처리 안 함
                    if current_retry + 1 >= 2:
                        df.at[idx, 'email_checked'] = True
                        output_df.at[idx, 'email_checked'] = True
                        failed += 1
                        status = f"❌ 팔로워 실패 [최종실패 {current_retry+1}/2]"
                    else:
                        df.at[idx, 'email_checked'] = False  # 다음에 재처리
                        output_df.at[idx, 'email_checked'] = False
                        status = f"❌ 팔로워 실패 [재시도{current_retry+1}/2]"

                # 이메일 처리
                if email is not None:
                    df.at[idx, 'creator_email'] = email
                    output_df.at[idx, 'creator_email'] = email
                    display_email = email[:30] + "..." if len(email) > 30 else email
                    status += f" 📧 {display_email}"
                else:
                    status += " (이메일 없음)"

            except Exception as e:
                # 예외 발생 시
                current_retry = df.at[idx, 'retry_count'] if pd.notna(df.at[idx, 'retry_count']) else 0

                df.at[idx, 'follower_count'] = 0
                df.at[idx, 'retry_count'] = current_retry + 1

                output_df.at[idx, 'follower_count'] = 0
                output_df.at[idx, 'retry_count'] = current_retry + 1

                # retry_count >= 2이면 더 이상 재처리 안 함
                if current_retry + 1 >= 2:
                    df.at[idx, 'email_checked'] = True
                    output_df.at[idx, 'email_checked'] = True
                    failed += 1
                    status = f"❌ 오류: {str(e)[:30]} [최종실패 {current_retry+1}/2]"
                else:
                    df.at[idx, 'email_checked'] = False  # 다음에 재처리
                    output_df.at[idx, 'email_checked'] = False
                    status = f"❌ 오류: {str(e)[:30]} [재시도{current_retry+1}/2]"

            completed += 1

            # 진행 상황 출력
            progress = 100 * completed / total
            elapsed = time.time() - start_time
            rate = completed / elapsed if elapsed > 0 else 0
            eta = (total - completed) / rate if rate > 0 else 0

            print(f"   [{completed:,}/{total:,}] ({progress:.1f}%) @{username[:20]:20} {status:25} "
                  f"| 성공: {success:,} 실패: {failed:,} | {rate:.1f}/s ETA: {eta/60:.1f}분")

            # 중간 저장
            if completed % checkpoint_interval == 0:
                output_df.to_csv(output_file, index=False, encoding='utf-8-sig')
                print(f"\n   💾 중간 저장 완료: {completed:,}/{total:,}\n")

    # 최종 저장
    output_df.to_csv(output_file, index=False, encoding='utf-8-sig')
    final_df = output_df

    elapsed = time.time() - start_time

    print("\n" + "=" * 60)
    print("✅ 완료!")
    print("=" * 60)
    print(f"\n📊 최종 통계:")
    print(f"   원본 프로필: {total_original:,}개")
    print(f"   처리 대상: {total:,}개")
    print(f"   성공: {success:,}개 ({100*success/total:.1f}%)")
    print(f"   실패: {failed:,}개 ({100*failed/total:.1f}%)")
    print(f"   소요 시간: {elapsed/60:.1f}분")
    print(f"   처리 속도: {total/elapsed:.1f}개/초")

    # 전체 결과 파일의 통계 (원본 + 업데이트된 데이터)
    print(f"\n📈 전체 결과 통계:")
    print(f"   총 프로필: {len(final_df):,}개")

    # 팔로워 수 통계 (전체 파일 기준)
    df_with_followers = final_df[final_df['follower_count'] > 0]
    if len(df_with_followers) > 0:
        print(f"\n👥 팔로워 수 통계:")
        print(f"   팔로워 보유: {len(df_with_followers):,}개 ({100*len(df_with_followers)/len(final_df):.1f}%)")
        print(f"   평균: {df_with_followers['follower_count'].mean():,.0f}명")
        print(f"   중앙값: {df_with_followers['follower_count'].median():,.0f}명")
        print(f"   최대: {df_with_followers['follower_count'].max():,}명")
        print(f"   최소: {df_with_followers['follower_count'].min():,}명")

    # 이메일 통계 (전체 파일 기준)
    df_with_emails = final_df[final_df['creator_email'].notna() & (final_df['creator_email'] != '')]
    if len(df_with_emails) > 0:
        print(f"\n📧 이메일 통계:")
        print(f"   이메일 보유: {len(df_with_emails):,}개 ({100*len(df_with_emails)/len(final_df):.1f}%)")

        # 새로 수집된 이메일 계산 (기존에 없던 이메일)
        new_emails = len(df_with_emails) - len(df_with_email)
        print(f"   새로 수집된 이메일: {new_emails:,}개")

        if new_emails > 0:
            print(f"   이메일 수집률: {100*new_emails/total:.1f}%")

    print(f"\n💾 저장 위치: {output_file}")
    print(f"   파일 크기: {output_file.stat().st_size / 1024:.1f} KB")


def main():
    print("🚀 스크립트 시작!")
    base_dir = Path(__file__).resolve().parent
    print(f"📂 베이스 디렉토리: {base_dir}")

    input_file = base_dir / 'results' / 'all_profiles_with_followers_hybrid.csv'
    output_file = base_dir / 'results' / 'all_profiles_with_followers_and_emails.csv'

    # 프록시 파일 경로 (선택사항)
    proxy_file = base_dir / 'data' / 'proxies.txt'
    if not proxy_file.exists():
        proxy_file = None
        print("⚠️  프록시 파일 없음 - 직접 연결 모드")

    print(f"📄 입력 파일: {input_file}")
    print(f"📄 출력 파일: {output_file}")
    print(f"✅ 파일 존재 확인: 입력={input_file.exists()}, 출력 디렉토리 존재={output_file.parent.exists()}")

    # 설정
    conservative_mode = False  # False: 0.4~0.6초 랜덤, True: 2~4초 랜덤
    use_cookie_rotation = True  # 쿠키 로테이션 사용
    requests_per_minute = 30  # 분당 최대 요청 수

    # 모드에 따른 설정
    if conservative_mode:
        max_workers = 3
        requests_per_minute = 20
        print("🐢 보수적 모드: 워커 3개, 20 req/min")
    else:
        max_workers = 5
        requests_per_minute = 30
        print("⚡ 일반 모드: 워커 5개, 30 req/min")

    enrich_csv_with_followers(
        input_file=input_file,
        output_file=output_file,
        max_workers=max_workers,
        checkpoint_interval=50,  # 50개마다 저장
        proxy_file=str(proxy_file) if proxy_file else None,
        conservative_mode=conservative_mode,
        use_cookie_rotation=use_cookie_rotation,
        requests_per_minute=requests_per_minute,
        max_retry_attempts=2  # 최대 2회 재시도 (retry_count < 2)
    )

    print("\n" + "=" * 60)


if __name__ == '__main__':
    main()
