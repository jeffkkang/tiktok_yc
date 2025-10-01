#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Output management for TikTok keyword scraper
Phase 3: Excel support, Phase 4: Memory optimization
"""

import csv
import logging
import pandas as pd
from typing import List
from pathlib import Path

from .models import CreatorProfile

logger = logging.getLogger(__name__)


class OutputManager:
    """출력 관리자"""

    @staticmethod
    def save_to_csv(profiles: List[CreatorProfile], output_file: str, mode: str = 'w'):
        """
        결과를 CSV로 저장
        Phase 4: 스트리밍 방식으로 메모리 효율적

        Args:
            profiles: 크리에이터 프로필 리스트
            output_file: 출력 파일 경로
            mode: 파일 모드 ('w': 덮어쓰기, 'a': 추가)
        """
        if not profiles:
            logger.warning("⚠️  저장할 프로필이 없습니다.")
            return

        try:
            # 파일 디렉토리 생성
            Path(output_file).parent.mkdir(parents=True, exist_ok=True)

            # 파일 존재 여부 확인
            file_exists = Path(output_file).exists()

            with open(output_file, mode, newline='', encoding='utf-8-sig') as csvfile:
                fieldnames = [
                    "keyword", "video_id", "video_url", "creator_id", "creator_username",
                    "creator_email", "follower_count", "view_count", "like_count",
                    "comment_count", "hashtags", "video_desc", "posted_date",
                    "source_api", "extraction_method", "scraped_at", "notes"
                ]

                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

                # 헤더 쓰기 (덮어쓰기 모드이거나 파일이 없을 때만)
                if mode == 'w' or not file_exists:
                    writer.writeheader()

                # 데이터 쓰기
                for profile in profiles:
                    writer.writerow(profile.to_dict())

            logger.info(f"✅ {len(profiles)}개 항목이 {output_file}에 저장되었습니다.")

        except Exception as e:
            logger.error(f"❌ CSV 저장 실패: {e}")
            raise

    @staticmethod
    def save_to_excel(profiles: List[CreatorProfile], output_file: str):
        """
        결과를 Excel로 저장
        Phase 3: Excel 출력 지원

        Args:
            profiles: 크리에이터 프로필 리스트
            output_file: 출력 파일 경로
        """
        if not profiles:
            logger.warning("⚠️  저장할 프로필이 없습니다.")
            return

        try:
            # 파일 디렉토리 생성
            Path(output_file).parent.mkdir(parents=True, exist_ok=True)

            # DataFrame으로 변환
            data = [profile.to_dict() for profile in profiles]
            df = pd.DataFrame(data)

            # Excel 저장
            df.to_excel(output_file, index=False, engine='openpyxl')
            logger.info(f"✅ {len(profiles)}개 항목이 {output_file}에 저장되었습니다.")

        except Exception as e:
            logger.error(f"❌ Excel 저장 실패: {e}")
            raise

    @staticmethod
    def append_to_csv(profiles: List[CreatorProfile], output_file: str):
        """
        Phase 3: 증분 스크래핑 - CSV에 추가

        Args:
            profiles: 크리에이터 프로필 리스트
            output_file: 출력 파일 경로
        """
        OutputManager.save_to_csv(profiles, output_file, mode='a')

    @staticmethod
    def load_existing_creators(output_file: str) -> set:
        """
        Phase 3: 기존 크리에이터 로드 (중복 방지)

        Args:
            output_file: 출력 파일 경로

        Returns:
            set: 기존 크리에이터 사용자명 집합
        """
        existing = set()

        try:
            if not Path(output_file).exists():
                return existing

            with open(output_file, 'r', encoding='utf-8-sig') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    username = row.get('creator_username')
                    if username:
                        existing.add(username)

            logger.info(f"📋 기존 크리에이터 {len(existing)}명 로드")

        except Exception as e:
            logger.warning(f"⚠️  기존 파일 로드 실패: {e}")

        return existing
