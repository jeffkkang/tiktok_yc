#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Utility functions for TikTok keyword scraper
"""

import re
import time
import random
from typing import List
from functools import wraps
import logging

logger = logging.getLogger(__name__)


def parse_count(count_text: str) -> int:
    """
    숫자 형식 파싱 ('1.2K', '1.2M' 등)

    Args:
        count_text: 숫자 문자열 (예: "1.2K", "5M", "100")

    Returns:
        int: 파싱된 숫자
    """
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


def extract_hashtags(text: str) -> List[str]:
    """
    텍스트에서 해시태그 추출

    Args:
        text: 텍스트

    Returns:
        List[str]: 해시태그 리스트
    """
    if not text:
        return []

    hashtag_pattern = r'#(\w+)'
    hashtags = re.findall(hashtag_pattern, text)
    return list(set(hashtags))  # 중복 제거


def random_delay(min_delay: float = 1.5, max_delay: float = 3.0):
    """
    랜덤 딜레이 (인간다운 행동 패턴)

    Args:
        min_delay: 최소 지연 시간 (초)
        max_delay: 최대 지연 시간 (초)
    """
    delay = random.uniform(min_delay, max_delay)
    time.sleep(delay)


def retry_on_failure(max_retries: int = 3, delay: int = 5, exceptions: tuple = (Exception,)):
    """
    실패 시 재시도 데코레이터

    Args:
        max_retries: 최대 재시도 횟수
        delay: 재시도 전 대기 시간 (초)
        exceptions: 재시도할 예외 타입들
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    if attempt == max_retries - 1:
                        logger.error(f"❌ {func.__name__} 실패 (최대 재시도 횟수 초과): {str(e)}")
                        raise

                    wait_time = delay * (2 ** attempt)  # Exponential backoff
                    logger.warning(f"⚠️  {func.__name__} 실패 (재시도 {attempt + 1}/{max_retries}), {wait_time}초 후 재시도...")
                    time.sleep(wait_time)

        return wrapper
    return decorator


def sanitize_filename(filename: str) -> str:
    """
    파일명에서 유효하지 않은 문자 제거

    Args:
        filename: 파일명

    Returns:
        str: 정제된 파일명
    """
    # 파일명에 사용할 수 없는 문자 제거
    invalid_chars = r'[<>:"/\\|?*]'
    sanitized = re.sub(invalid_chars, '_', filename)

    # 연속된 언더스코어 제거
    sanitized = re.sub(r'_+', '_', sanitized)

    # 앞뒤 공백 및 언더스코어 제거
    sanitized = sanitized.strip('_ ')

    return sanitized


def get_random_user_agent() -> str:
    """
    랜덤 User-Agent 반환 (봇 감지 회피)

    Returns:
        str: User-Agent 문자열
    """
    user_agents = [
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    ]
    return random.choice(user_agents)


def format_duration(seconds: float) -> str:
    """
    시간을 읽기 쉬운 형식으로 변환

    Args:
        seconds: 초

    Returns:
        str: 포맷된 시간 (예: "1h 30m 45s")
    """
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}m"
    else:
        hours = seconds / 3600
        minutes = (seconds % 3600) / 60
        return f"{int(hours)}h {int(minutes)}m"
