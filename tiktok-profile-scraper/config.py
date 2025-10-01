import os
import json
from pathlib import Path
from typing import Dict, Any, List
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

class Config:
    """설정 관리 클래스"""
    
    # 기본 설정
    DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    
    # 쿠키 관련 설정
    COOKIE_CHECK_INTERVAL = int(os.getenv('COOKIE_CHECK_INTERVAL', '3600'))  # 1시간
    
    # 스크래퍼 설정
    CONCURRENT_WORKERS = int(os.getenv('CONCURRENT_WORKERS', '5'))
    REQUEST_DELAY_MIN = float(os.getenv('REQUEST_DELAY_MIN', '1.0'))
    REQUEST_DELAY_MAX = float(os.getenv('REQUEST_DELAY_MAX', '3.0'))
    MAX_RETRIES = int(os.getenv('MAX_RETRIES', '3'))
    BATCH_SIZE = int(os.getenv('BATCH_SIZE', '100'))
    
    # 파일 경로 설정
    BASE_DIR = Path(__file__).parent
    OUTPUT_DIR = BASE_DIR / 'output'
    LOG_DIR = BASE_DIR / 'logs'
    
    # 디렉토리 생성
    OUTPUT_DIR.mkdir(exist_ok=True)
    LOG_DIR.mkdir(exist_ok=True)
    
    @classmethod
    def get_cookies(cls) -> List[Dict[str, str]]:
        """쿠키 설정 가져오기"""
        try:
            cookies_str = os.getenv('COOKIES', '[]')
            # 작은따옴표 제거 (환경변수에서 가져올 때 작은따옴표가 포함될 수 있음)
            cookies_str = cookies_str.strip("'")
            return json.loads(cookies_str)
        except Exception as e:
            print(f"쿠키 파싱 오류: {str(e)}")
            return []
    
    @classmethod
    def get_request_delay(cls) -> tuple[float, float]:
        """요청 딜레이 범위 반환"""
        return (cls.REQUEST_DELAY_MIN, cls.REQUEST_DELAY_MAX)
    
    @classmethod
    def get_hashtags(cls) -> List[str]:
        """해시태그 목록 가져오기"""
        hashtags_str = os.getenv('HASHTAGS', 'beauty,skincare,makeup')
        return [tag.strip() for tag in hashtags_str.split(',') if tag.strip()]

# 초기 설정
Config.setup_directories() 