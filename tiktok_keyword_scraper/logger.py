#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Logging configuration for TikTok keyword scraper
Phase 1: Improved logging system with file/console separation
"""

import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler


def setup_logger(
    name: str = "tiktok_scraper",
    log_file: str = "tiktok_keyword_scraper.log",
    level: str = "INFO",
    console_level: str = "INFO",
    file_level: str = "DEBUG",
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5
) -> logging.Logger:
    """
    로깅 시스템 설정
    Phase 1: 파일/콘솔 출력 분리, 로그 레벨별 분리

    Args:
        name: 로거 이름
        log_file: 로그 파일 경로
        level: 전체 로그 레벨
        console_level: 콘솔 출력 레벨
        file_level: 파일 출력 레벨
        max_bytes: 로그 파일 최대 크기
        backup_count: 백업 파일 개수

    Returns:
        logging.Logger: 설정된 로거
    """
    # 로거 생성
    logger = logging.getLogger(name)

    # 로그 레벨 설정
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # 기존 핸들러 제거 (중복 방지)
    logger.handlers.clear()

    # 포맷터 설정
    console_formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    file_formatter = logging.Formatter(
        '[%(asctime)s] %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # 콘솔 핸들러 (INFO 이상)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, console_level.upper(), logging.INFO))
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # 파일 핸들러 (DEBUG 포함, 로테이션)
    try:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(getattr(logging, file_level.upper(), logging.DEBUG))
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

    except Exception as e:
        logger.warning(f"파일 핸들러 설정 실패: {e}")

    return logger


def get_logger(name: str = "tiktok_scraper") -> logging.Logger:
    """
    기존 로거 반환 또는 생성

    Args:
        name: 로거 이름

    Returns:
        logging.Logger: 로거
    """
    logger = logging.getLogger(name)

    if not logger.handlers:
        # 핸들러가 없으면 기본 설정으로 생성
        return setup_logger(name)

    return logger
