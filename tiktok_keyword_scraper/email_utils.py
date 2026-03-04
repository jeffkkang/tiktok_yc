#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Email extraction module for TikTok keyword scraper
"""

import re
import logging
from typing import List

logger = logging.getLogger(__name__)


class EmailExtractor:
    """이메일 추출기"""

    # 일반적인 이메일 패턴
    EMAIL_PATTERN = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,15}\b'

    # 숨겨진 이메일 패턴 (예: user [at] domain [dot] com)
    OBSCURED_PATTERN = r'\b[a-zA-Z0-9_.+-]+\s*[\[\(]at[\]\)]\s*[a-zA-Z0-9-]+\s*[\[\(]dot[\]\)]\s*[a-zA-Z0-9-.]+\b'

    # 제외할 도메인 (스팸/테스트)
    EXCLUDED_DOMAINS = {
        'example.com',
        'test.com',
        'domain.com',
        'email.com',
        'mail.com',
    }

    @staticmethod
    def extract_emails(text: str) -> List[str]:
        """
        텍스트에서 이메일 추출

        Args:
            text: 텍스트

        Returns:
            List[str]: 이메일 리스트
        """
        if not text:
            return []

        clean_emails = []

        # 1. 일반 이메일 패턴 추출
        emails = re.findall(EmailExtractor.EMAIL_PATTERN, text)
        for email in emails:
            email = email.lower().strip()
            if EmailExtractor.is_valid_email(email) and email not in clean_emails:
                clean_emails.append(email)

        # 2. 숨겨진 이메일 형식 추출
        obscured_matches = re.findall(EmailExtractor.OBSCURED_PATTERN, text, re.IGNORECASE)
        for match in obscured_matches:
            # [at] 또는 (at)를 @로 변환
            clean_email = match.replace('[at]', '@').replace('(at)', '@')
            clean_email = clean_email.replace('[AT]', '@').replace('(AT)', '@')

            # [dot] 또는 (dot)을 .로 변환
            clean_email = clean_email.replace('[dot]', '.').replace('(dot)', '.')
            clean_email = clean_email.replace('[DOT]', '.').replace('(DOT)', '.')

            # 공백 제거
            clean_email = re.sub(r'\s+', '', clean_email).lower()

            if EmailExtractor.is_valid_email(clean_email) and clean_email not in clean_emails:
                clean_emails.append(clean_email)

        # 3. 제외 도메인 필터링
        clean_emails = [
            email for email in clean_emails
            if email.split('@')[1] not in EmailExtractor.EXCLUDED_DOMAINS
        ]

        return clean_emails

    @staticmethod
    def is_valid_email(email: str) -> bool:
        """
        이메일 유효성 검사

        Args:
            email: 이메일 주소

        Returns:
            bool: 유효 여부
        """
        if not email or '@' not in email:
            return False

        # URL 인코딩 잔재 필터 (페이지 소스에서 \u002f 등이 이메일로 오탐)
        local_part = email.split('@')[0]
        if re.search(r'u[0-9a-fA-F]{4}$', local_part):
            return False

        # 기본 패턴 검사
        pattern = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
        if not re.match(pattern, email):
            return False

        # 도메인 확인
        try:
            local, domain = email.split('@')

            # 로컬 파트 검증
            if not local or len(local) > 64:
                return False

            # 도메인 검증
            if not domain or '.' not in domain:
                return False

            # TLD 검증 (2~15자)
            tld = domain.split('.')[-1]
            if len(tld) < 2 or len(tld) > 15:
                return False

            return True

        except ValueError:
            return False

    @staticmethod
    def get_primary_email(emails: List[str]) -> str:
        """
        주요 이메일 선택 (첫 번째 이메일 또는 example.com 제외)

        Args:
            emails: 이메일 리스트

        Returns:
            str: 주요 이메일 또는 'example@example.com'
        """
        if not emails:
            return 'example@example.com'

        # 제외 도메인이 아닌 첫 번째 이메일 선택
        for email in emails:
            domain = email.split('@')[1]
            if domain not in EmailExtractor.EXCLUDED_DOMAINS:
                return email

        # 모두 제외 도메인이면 첫 번째 반환
        return emails[0] if emails else 'example@example.com'

    @staticmethod
    def format_emails(emails: List[str], separator: str = ', ') -> str:
        """
        이메일 리스트를 문자열로 포맷

        Args:
            emails: 이메일 리스트
            separator: 구분자

        Returns:
            str: 포맷된 이메일 문자열
        """
        return separator.join(emails) if emails else ''
