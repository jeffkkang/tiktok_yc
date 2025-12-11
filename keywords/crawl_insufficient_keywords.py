#!/usr/bin/env python3
"""
데이터가 부족한 키워드들을 대상으로 추가 크롤링 진행
"""

import subprocess
import sys
import time
import logging
from pathlib import Path
from typing import List

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('keyword_crawling.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class KeywordCrawler:
    """키워드 크롤링 관리자"""

    def __init__(self, base_dir: str = None):
        self.base_dir = Path(base_dir) if base_dir else Path.cwd()

    def crawl_keyword(self, keyword: str, limit: int = 50) -> bool:
        """
        단일 키워드로 크롤링 실행

        Args:
            keyword: 크롤링할 키워드
            limit: 수집할 개수

        Returns:
            성공 여부
        """
        logger.info(f"🚀 '{keyword}' 크롤링 시작 (목표: {limit}개)...")

        try:
            # 하이브리드 스크래퍼 실행 명령어 구성
            cmd = [
                sys.executable, '-m', 'tiktok_keyword_scraper.hybrid_scraper',
                '-k', keyword,
                '-l', str(limit)
            ]

            # 스크래핑 실행
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600,  # 10분 타임아웃
                cwd=self.base_dir
            )

            # 결과 확인
            if result.returncode == 0:
                logger.info(f"✅ '{keyword}' 크롤링 성공")
                return True
            else:
                logger.error(f"❌ '{keyword}' 크롤링 실패: {result.stderr}")
                return False

        except subprocess.TimeoutExpired:
            logger.error(f"⏰ '{keyword}' 크롤링 타임아웃")
            return False
        except Exception as e:
            logger.error(f"💥 '{keyword}' 크롤링 중 예외 발생: {e}")
            return False

    def crawl_multiple_keywords(self, keywords: List[str], limit_per_keyword: int = 50,
                              delay_between: int = 5) -> dict:
        """
        여러 키워드들을 크롤링

        Args:
            keywords: 크롤링할 키워드 리스트
            limit_per_keyword: 키워드당 수집 개수
            delay_between: 키워드 간 대기 시간(초)

        Returns:
            성공/실패 결과 딕셔너리
        """
        results = {}

        logger.info(f"🚀 {len(keywords)}개 키워드 크롤링 시작...")
        logger.info(f"   키워드당 목표: {limit_per_keyword}개")
        logger.info(f"   키워드 간 대기: {delay_between}초")

        for i, keyword in enumerate(keywords, 1):
            logger.info(f"[{i}/{len(keywords)}] 처리 중...")

            success = self.crawl_keyword(keyword, limit_per_keyword)
            results[keyword] = success

            # 마지막 키워드가 아니면 대기
            if i < len(keywords):
                logger.info(f"⏳ 다음 키워드까지 {delay_between}초 대기...")
                time.sleep(delay_between)

        return results

def main():
    """메인 실행 함수"""
    # 새로 생성한 키워드들 사용
    new_keywords_file = Path('keywords/new_beauty_keywords.txt')
    if new_keywords_file.exists():
        with open(new_keywords_file, 'r', encoding='utf-8') as f:
            priority_keywords = [line.strip() for line in f if line.strip()][:10]  # 처음 10개만 사용
        print(f"📋 새 키워드 파일에서 {len(priority_keywords)}개 키워드 로드")
    else:
        # 기존 키워드들 사용
        priority_keywords = [
            # 1순위: 메이크업 관련 키워드들
            'makeupaddiction', 'makeupworld', 'makeuphaul', 'makeupcollection',
            'makeupreviews', 'makeupblogger', 'makeupblog', 'makeupgram',

            # 2순위: 스킨케어 관련 키워드들
            'skincarelover', 'skincaregoals', 'skincarejunkie', 'naturalbeauty',
            'sustainablecosmetics', 'facialbeauty', 'skincaretime'
        ]

    print("🎯 추가 크롤링 대상 키워드들:")
    for i, keyword in enumerate(priority_keywords, 1):
        print(f"  {i:2d}. {keyword}")

    # 사용자 확인
    confirm = input("\n🚀 위 키워드들로 크롤링을 시작하시겠습니까? (y/N): ")
    if confirm.lower() not in ['y', 'yes']:
        logger.info("ℹ️ 사용자가 취소했습니다.")
        return

    # 크롤러 초기화 및 실행
    crawler = KeywordCrawler()
    results = crawler.crawl_multiple_keywords(
        keywords=priority_keywords,
        limit_per_keyword=50,  # 키워드당 50개 목표
        delay_between=3  # 키워드 간 3초 대기
    )

    # 결과 요약
    print("🔍 크롤링 결과 요약")
    print("📊 크롤링 결과:")
    success_count = sum(results.values())
    total_count = len(results)

    for keyword, success in results.items():
        status = "✅ 성공" if success else "❌ 실패"
        print(f"  {keyword}: {status}")

    print(f"\n🎉 완료: {success_count}/{total_count} 성공")

    if success_count > 0:
        print("💡 크롤링이 완료되었습니다. 이제 merge_hybrid_files.py를 실행하여 결과를 통합해주세요.")


if __name__ == "__main__":
    main()