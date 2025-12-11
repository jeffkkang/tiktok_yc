#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
분석되지 않은 키워드 선택 및 분석 스크립트
- 사용 가능한 키워드 소스에서 키워드들을 수집
- 이미 사용된/실패한/분석된 키워드들을 제외
- 남은 키워드들 중에서 선택하여 하이브리드 스크래핑 실행
"""

import os
import json
import random
import subprocess
import sys
import logging
import signal
import psutil
import time
import csv
from pathlib import Path
from typing import List, Set, Dict, Optional
from datetime import datetime

# Selenium imports
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from selenium.common.exceptions import WebDriverException, TimeoutException
    from webdriver_manager.chrome import ChromeDriverManager
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    logger.warning("⚠️ Selenium not available. Browser mode will be disabled.")

# TikTok scraper imports
try:
    import tiktok_keyword_scraper
    from tiktok_keyword_scraper.hybrid_scraper import HybridTikTokScraper
    from tiktok_keyword_scraper.cookie import CookieManager
    from tiktok_keyword_scraper.scraper import CaptchaDetectedException
    SCRAPER_AVAILABLE = True
except ImportError:
    SCRAPER_AVAILABLE = False
    logger.warning("⚠️ TikTok scraper module not available.")

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('keyword_analysis.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class KeywordAnalyzer:
    """키워드 분석 및 선택 관리자"""

    def __init__(self, base_dir: str = None):
        if base_dir:
            self.base_dir = Path(base_dir)
        else:
            # 스크립트 위치와 관계없이 프로젝트 루트를 기준으로 삼는다
            self.base_dir = Path(__file__).resolve().parents[1]

        # 키워드 소스 파일들
        self.keyword_sources = [
            'keywords/popular_beauty_keywords.txt',
            'keywords/mega_beauty_keywords.txt',
            'keywords/high_volume_keywords.txt',
            'keywords/popular_keywords_batch2.txt',
            'keywords/fresh_beauty_keywords.txt'
        ]

        # 제외 키워드 파일들
        self.exclude_files = [
            'keywords/used_keywords.txt',
            'keywords/failed_keywords.txt',
            'keywords/keyword_history.json'
        ]

    def load_keyword_source(self, filename: str) -> Set[str]:
        """키워드 소스 파일에서 키워드들을 로드"""
        try:
            file_path = self.base_dir / filename
            if not file_path.exists():
                logger.warning(f"키워드 소스 파일 없음: {filename}")
                return set()

            keywords = set()
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    keyword = line.strip().lower()
                    if keyword and not keyword.startswith('#'):
                        keywords.add(keyword)

            logger.info(f"✅ {filename}: {len(keywords)}개 키워드 로드")
            return keywords

        except Exception as e:
            logger.error(f"❌ {filename} 로드 실패: {e}")
            return set()

    def load_used_keywords(self, filename: str) -> Set[str]:
        """사용된 키워드 파일에서 키워드들을 로드"""
        try:
            file_path = self.base_dir / filename
            if not file_path.exists():
                logger.warning(f"사용 키워드 파일 없음: {filename}")
                return set()

            keywords = set()

            if filename.endswith('.json'):
                # JSON 파일 처리 (keyword_history.json)
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    used_list = data.get('used_keywords', [])
                    keywords.update(kw.lower().strip() for kw in used_list)
            else:
                # 텍스트 파일 처리 (used_keywords.txt, failed_keywords.txt)
                with open(file_path, 'r', encoding='utf-8') as f:
                    for line_num, line in enumerate(f, 1):
                        line = line.strip()
                        if not line:
                            continue

                        # 다양한 형식 처리
                        # 1. "keyword (count items)" 형식
                        # 2. 그냥 "keyword" 형식
                        # 3. 공백으로 구분된 첫 번째 단어

                        # 괄호 앞부분 추출
                        if '(' in line:
                            keyword = line.split('(')[0].strip().lower()
                        else:
                            # 첫 번째 단어 추출 (공백이나 탭으로 구분)
                            keyword = line.split()[0].split('\t')[0].strip().lower()

                        if keyword:
                            keywords.add(keyword)

            logger.info(f"✅ {filename}: {len(keywords)}개 키워드 제외")
            return keywords

        except Exception as e:
            logger.error(f"❌ {filename} 로드 실패: {e}")
            return set()

    def get_analyzed_keywords(self) -> Set[str]:
        """이미 분석된 키워드들을 결과 파일에서 추출"""
        analyzed = set()

        try:
            results_dir = self.base_dir / 'results'
            if not results_dir.exists():
                return analyzed

            # 모든 CSV 파일들을 확인
            for csv_file in results_dir.glob('*.csv'):
                filename = csv_file.stem  # .csv 제거

                # 1. 하이브리드 결과 파일들 (형식: keyword_hybrid.csv)
                if filename.endswith('_hybrid'):
                    keyword = filename.replace('_hybrid', '').lower()
                    if keyword:
                        analyzed.add(keyword)
                    continue

                # 2. 개별 키워드 결과 파일들
                # 다양한 패턴 시도: keyword.csv, keyword_results.csv 등
                if '_' in filename:
                    # 언더스코어로 구분된 첫 번째 부분을 키워드로 사용
                    keyword = filename.split('_')[0].lower()
                    if keyword and len(keyword) > 2:  # 너무 짧은 키워드는 제외
                        analyzed.add(keyword)
                else:
                    # 단순 파일명도 확인 (keyword.csv)
                    keyword = filename.lower()
                    if keyword and len(keyword) > 2:
                        analyzed.add(keyword)

                # 3. CSV 파일 내용에서 키워드 읽기 (더 정확함)
                try:
                    import pandas as pd
                    df = pd.read_csv(csv_file)
                    if 'keyword' in df.columns:
                        file_keywords = df['keyword'].unique()
                        for kw in file_keywords:
                            if kw and isinstance(kw, str):
                                analyzed.add(kw.lower().strip())
                except:
                    pass  # CSV 읽기 실패는 무시

            logger.info(f"✅ 이미 분석된 키워드: {len(analyzed)}개")
            return analyzed

        except Exception as e:
            logger.error(f"❌ 분석된 키워드 확인 실패: {e}")
            return set()

    def get_all_available_keywords(self) -> Set[str]:
        """모든 사용 가능한 키워드들을 수집"""
        all_keywords = set()

        logger.info("🔍 키워드 소스 파일들 로드 중...")

        for source_file in self.keyword_sources:
            keywords = self.load_keyword_source(source_file)
            all_keywords.update(keywords)

        logger.info(f"📊 총 키워드 소스: {len(all_keywords)}개")
        return all_keywords

    def get_excluded_keywords(self) -> Set[str]:
        """제외할 키워드들을 수집"""
        excluded = set()

        logger.info("🚫 제외 키워드 파일들 로드 중...")

        for exclude_file in self.exclude_files:
            keywords = self.load_used_keywords(exclude_file)
            excluded.update(keywords)

        # 이미 분석된 키워드들도 제외
        analyzed = self.get_analyzed_keywords()
        excluded.update(analyzed)

        logger.info(f"📊 총 제외 키워드: {len(excluded)}개")
        return excluded

    def get_unanalyzed_keywords(self) -> List[str]:
        """분석되지 않은 키워드들을 반환"""
        available = self.get_all_available_keywords()
        excluded = self.get_excluded_keywords()

        unanalyzed = list(available - excluded)

        logger.info(f"🎯 분석되지 않은 키워드: {len(unanalyzed)}개")
        return sorted(unanalyzed)

    def select_keywords(self, method: str = 'random', count: int = 5,
                       priority_keywords: List[str] = None) -> List[str]:
        """
        키워드 선택

        Args:
            method: 선택 방법 ('random', 'priority', 'all')
            count: 선택할 개수
            priority_keywords: 우선순위 키워드들
        """
        unanalyzed = self.get_unanalyzed_keywords()

        if not unanalyzed:
            logger.warning("⚠️ 분석할 키워드가 없습니다.")
            return []

        if method == 'all':
            return unanalyzed[:count]
        elif method == 'priority' and priority_keywords:
            # 우선순위 키워드들을 먼저 선택
            priority_set = set(kw.lower() for kw in priority_keywords)
            priority_found = [kw for kw in unanalyzed if kw in priority_set]
            remaining = [kw for kw in unanalyzed if kw not in priority_set]

            selected = priority_found + remaining[:count-len(priority_found)]
            return selected[:count]
        else:
            # 랜덤 선택 (기본값)
            return random.sample(unanalyzed, min(count, len(unanalyzed)))

    def _kill_process_tree(self, pid: int):
        """프로세스 트리 전체를 종료 (브라우저 프로세스 포함)"""
        try:
            parent = psutil.Process(pid)
            children = parent.children(recursive=True)

            # 자식 프로세스들 종료
            for child in children:
                try:
                    logger.debug(f"  자식 프로세스 종료: {child.pid} ({child.name()})")
                    child.terminate()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass

            # 부모 프로세스 종료
            try:
                parent.terminate()
                parent.wait(timeout=3)
            except psutil.TimeoutExpired:
                parent.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

            logger.info("  ✅ 프로세스 트리 종료 완료")
        except Exception as e:
            logger.warning(f"  ⚠️  프로세스 종료 중 오류: {e}")

    def _check_partial_results(self, keyword: str) -> bool:
        """타임아웃 후 부분 결과가 저장되었는지 확인"""
        try:
            results_dir = self.base_dir / 'results'
            result_file = results_dir / f'{keyword}_hybrid.csv'

            if result_file.exists():
                # 파일 크기 확인 (헤더만 있는지 확인)
                file_size = result_file.stat().st_size
                if file_size > 200:  # 헤더보다 큰 경우 데이터가 있음
                    # 라인 수 확인
                    with open(result_file, 'r', encoding='utf-8') as f:
                        lines = len(f.readlines())
                        if lines > 1:  # 헤더 + 데이터
                            logger.info(f"  ✅ 부분 결과 발견: {result_file} ({lines-1}개 항목)")
                            return True
            return False
        except Exception as e:
            logger.warning(f"  ⚠️  결과 파일 확인 중 오류: {e}")
            return False

    def _record_timeout_keyword(self, keyword: str):
        """타임아웃된 키워드를 별도 파일에 기록"""
        try:
            timeout_file = self.base_dir / 'keywords' / 'timeout_keywords.txt'
            timeout_file.parent.mkdir(exist_ok=True)

            with open(timeout_file, 'a', encoding='utf-8') as f:
                f.write(f"{keyword}\t{datetime.now().isoformat()}\n")
            logger.info(f"  📝 타임아웃 키워드 기록: {timeout_file}")
        except Exception as e:
            logger.warning(f"  ⚠️  타임아웃 키워드 기록 실패: {e}")

    def _cleanup_zombie_chrome_processes(self):
        """좀비 Chrome/ChromeDriver 프로세스 정리"""
        try:
            zombie_count = 0
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    name = proc.info['name'].lower()
                    cmdline = ' '.join(proc.info['cmdline'] or []).lower()
                    
                    # ChromeDriver 프로세스 찾기 (automation 관련만)
                    if 'chromedriver' in name and ('--port=' in cmdline or 'test-type' in cmdline):
                        proc.kill()
                        zombie_count += 1
                        logger.debug(f"좀비 ChromeDriver 제거: PID={proc.info['pid']}")
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            
            if zombie_count > 0:
                logger.info(f"✅ {zombie_count}개 좀비 프로세스 정리 완료")
                time.sleep(1)
        except Exception as e:
            logger.warning(f"⚠️ 프로세스 정리 중 오류 (무시함): {e}")

    def _init_browser(self, headless: bool = False) -> Optional[webdriver.Chrome]:
        """브라우저 초기화 (재시도 로직 포함)"""
        if not SELENIUM_AVAILABLE:
            logger.error("❌ Selenium이 설치되지 않았습니다. pip install selenium webdriver-manager")
            return None

        # 좀비 프로세스 정리
        self._cleanup_zombie_chrome_processes()

        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"🌐 브라우저 초기화 중... (시도 {attempt}/{max_retries})")

                options = Options()
                
                # 동적 포트 할당 (충돌 방지)
                debug_port = random.randint(9222, 9999)
                options.add_argument(f"--remote-debugging-port={debug_port}")
                logger.debug(f"Remote debugging port: {debug_port}")

                if headless:
                    # 헤드리스 모드 강화
                    options.add_argument("--headless=new")
                    options.add_argument("--disable-blink-features=AutomationControlled")
                    options.add_argument("--disable-features=VizDisplayCompositor")
                    options.add_argument("--disable-ipc-flooding-protection")
                    options.add_argument("--disable-web-security")
                    options.add_argument("--disable-features=VizHitTestSurfaceLayer")
                    options.add_argument("--disable-background-timer-throttling")
                    options.add_argument("--disable-renderer-backgrounding")
                    options.add_argument("--disable-backgrounding-occluded-windows")
                    options.add_argument("--no-sandbox")
                    options.add_argument("--disable-dev-shm-usage")
                    options.add_argument("--disable-gpu")
                    options.add_argument("--disable-software-rasterizer")
                    options.add_argument("--memory-pressure-off")
                    options.add_argument("--max_old_space_size=4096")
                    options.add_argument("--disable-http2")
                    options.add_argument("--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
                else:
                    # 브라우저 모드 (일부 옵션만)
                    options.add_argument("--disable-blink-features=AutomationControlled")
                    options.add_argument("--disable-web-security")

                # 공통 옵션
                options.add_experimental_option("excludeSwitches", ["enable-automation"])
                options.add_experimental_option('useAutomationExtension', False)

                service = Service(ChromeDriverManager().install())
                driver = webdriver.Chrome(service=service, options=options)

                # 초기 페이지 로드
                driver.get("https://www.tiktok.com")
                time.sleep(3)

                logger.info("✅ 브라우저 초기화 성공")
                return driver

            except Exception as e:
                logger.error(f"❌ 브라우저 초기화 실패 (시도 {attempt}/{max_retries}): {e}")
                if attempt < max_retries:
                    logger.info(f"⏳ 5초 후 재시도...")
                    time.sleep(5)
                else:
                    logger.error("❌ 브라우저 초기화 최종 실패")
                    return None

        return None

    def _is_browser_alive(self, driver: Optional[webdriver.Chrome]) -> bool:
        """브라우저가 살아있는지 확인"""
        if driver is None:
            return False

        try:
            # 간단한 명령어로 브라우저 상태 확인
            _ = driver.current_url
            return True
        except Exception:
            return False

    def _restart_browser(self, old_driver: Optional[webdriver.Chrome], headless: bool = False) -> Optional[webdriver.Chrome]:
        """브라우저 재시작"""
        logger.warning("🔄 브라우저 재시작 중...")

        # 기존 브라우저 정리
        self._cleanup_browser(old_driver)

        # 새 브라우저 초기화
        return self._init_browser(headless=headless)

    def _cleanup_browser(self, driver: Optional[webdriver.Chrome]):
        """안전한 브라우저 종료"""
        if driver is None:
            return

        try:
            logger.info("🔄 브라우저 종료 중...")
            driver.quit()
            logger.info("✅ 브라우저 종료 완료")
        except Exception as e:
            logger.warning(f"⚠️  브라우저 종료 중 오류: {e}")

            # 강제 종료 시도
            try:
                driver.close()
            except Exception:
                pass

    def _save_keyword_results(self, keyword: str, results: list) -> bool:
        """키워드 결과를 CSV 파일로 저장"""
        try:
            results_dir = self.base_dir / 'results'
            results_dir.mkdir(exist_ok=True)

            output_file = results_dir / f'{keyword}_hybrid.csv'

            with open(output_file, 'w', newline='', encoding='utf-8-sig') as f:
                fieldnames = [
                    'keyword', 'video_id', 'video_url', 'creator_id',
                    'creator_username', 'view_count', 'like_count',
                    'video_desc', 'hashtags', 'scraped_at'
                ]
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()

                for result in results:
                    writer.writerow({
                        'keyword': keyword,
                        'video_id': result.video_id,
                        'video_url': result.video_url,
                        'creator_id': result.creator_id,
                        'creator_username': result.creator_username,
                        'view_count': result.view_count,
                        'like_count': result.like_count,
                        'video_desc': result.video_desc,
                        'hashtags': ','.join(result.hashtags) if result.hashtags else '',
                        'scraped_at': datetime.now().isoformat()
                    })

            logger.info(f"💾 결과 저장 완료: {output_file} ({len(results)}개)")
            return True

        except Exception as e:
            logger.error(f"❌ 결과 저장 실패: {e}")
            return False

    def analyze_selected_keywords(self, keywords: List[str], limit: int = 100,
                                use_browser: bool = False) -> Dict[str, bool]:
        """
        선택된 키워드들로 하이브리드 스크래핑 실행 (브라우저 재사용 방식)

        Args:
            keywords: 분석할 키워드 리스트
            limit: 수집할 개수
            use_browser: 브라우저 모드 사용 여부

        Returns:
            성공/실패 결과 딕셔너리
        """
        if not SCRAPER_AVAILABLE:
            logger.error("❌ TikTok 스크래퍼 모듈을 import할 수 없습니다.")
            return {kw: False for kw in keywords}

        results = {}
        driver = None
        scraper = None
        cookie_manager = None

        # 브라우저 재시작 주기 (메모리 누수 방지)
        BROWSER_RESTART_INTERVAL = 50

        try:
            logger.info(f"🚀 {len(keywords)}개 키워드 분석 시작 (브라우저 재사용 모드)")

            # 쿠키 관리자 초기화
            try:
                cookie_file = self.base_dir / 'cookies.json'
                if cookie_file.exists():
                    cookie_manager = CookieManager(str(cookie_file))
                    logger.info(f"✅ 쿠키 로드 완료: {cookie_file}")
                else:
                    logger.warning(f"⚠️  쿠키 파일 없음: {cookie_file}")
                    cookie_manager = CookieManager(str(cookie_file))  # 빈 쿠키로 진행
            except Exception as e:
                logger.error(f"❌ 쿠키 관리자 초기화 실패: {e}")
                cookie_manager = None

            # 브라우저 초기화
            driver = self._init_browser(headless=not use_browser)
            if driver is None:
                logger.error("❌ 브라우저 초기화 실패로 작업을 중단합니다.")
                return {kw: False for kw in keywords}

            # 하이브리드 스크래퍼 초기화
            try:
                scraper = HybridTikTokScraper(
                    cookie_manager=cookie_manager,
                    headless=not use_browser,
                    delay_min=2.0,
                    delay_max=4.0
                )
                logger.info("✅ 하이브리드 스크래퍼 초기화 완료")
            except Exception as e:
                logger.error(f"❌ 스크래퍼 초기화 실패: {e}")
                self._cleanup_browser(driver)
                return {kw: False for kw in keywords}

            # 각 키워드 처리
            for i, keyword in enumerate(keywords, 1):
                logger.info(f"\n{'='*60}")
                logger.info(f"[{i}/{len(keywords)}] '{keyword}' 분석 중...")
                logger.info(f"{'='*60}")

                # 주기적으로 브라우저 재시작 (메모리 누수 방지)
                if i > 1 and (i - 1) % BROWSER_RESTART_INTERVAL == 0:
                    logger.info(f"🔄 메모리 관리를 위해 브라우저 재시작 ({BROWSER_RESTART_INTERVAL}개마다)")
                    driver = self._restart_browser(driver, headless=not use_browser)
                    if driver is None:
                        logger.error("❌ 브라우저 재시작 실패, 나머지 키워드는 건너뜁니다.")
                        for remaining_kw in keywords[i-1:]:
                            results[remaining_kw] = False
                        break

                # 브라우저 상태 확인
                if not self._is_browser_alive(driver):
                    logger.warning("⚠️  브라우저가 죽었습니다. 재시작합니다...")
                    driver = self._restart_browser(driver, headless=not use_browser)
                    if driver is None:
                        logger.error(f"❌ '{keyword}' 브라우저 재시작 실패로 건너뜁니다.")
                        results[keyword] = False
                        continue

                # 키워드 스크래핑 시작
                keyword_success = False
                start_time = time.time()

                try:
                    # 타임아웃 설정 (10분)
                    SCRAPING_TIMEOUT = 600
                    scraping_results = []

                    # 스크래핑 실행
                    try:
                        scraping_results = scraper.scrape_hybrid(
                            keyword=keyword,
                            limit=limit,
                            driver=driver
                        )

                        # 소요 시간 계산
                        elapsed = time.time() - start_time

                        if scraping_results and len(scraping_results) > 0:
                            logger.info(f"✅ '{keyword}' 스크래핑 성공: {len(scraping_results)}개 수집 ({elapsed:.1f}초)")

                            # 결과 즉시 저장
                            if self._save_keyword_results(keyword, scraping_results):
                                keyword_success = True
                            else:
                                logger.warning(f"⚠️  '{keyword}' 스크래핑은 성공했으나 저장 실패")
                                # 저장 재시도
                                time.sleep(1)
                                if self._save_keyword_results(keyword, scraping_results):
                                    keyword_success = True
                                    logger.info("✅ 재시도로 저장 성공")
                                else:
                                    keyword_success = False
                        else:
                            logger.warning(f"⚠️  '{keyword}' 스크래핑 결과 없음 ({elapsed:.1f}초)")
                            keyword_success = False

                    except CaptchaDetectedException as e:
                        logger.error(f"🔒 '{keyword}' CAPTCHA 감지: {e}")
                        logger.warning("CAPTCHA 발생으로 이 키워드를 건너뜁니다.")
                        keyword_success = False

                        # CAPTCHA 발생 시 브라우저 재시작 시도
                        logger.info("🔄 CAPTCHA 회피를 위해 브라우저 재시작...")
                        driver = self._restart_browser(driver, headless=not use_browser)
                        if driver is None:
                            logger.error("❌ 브라우저 재시작 실패")
                            break

                    except TimeoutException as e:
                        logger.error(f"⏰ '{keyword}' 타임아웃: {e}")
                        self._record_timeout_keyword(keyword)

                        # 부분 결과 확인
                        has_partial = self._check_partial_results(keyword)
                        if has_partial:
                            logger.warning(f"⚠️  '{keyword}' 타임아웃되었지만 부분 결과 발견")
                            keyword_success = True
                        else:
                            keyword_success = False

                    except WebDriverException as e:
                        logger.error(f"🌐 '{keyword}' 브라우저 오류: {e}")
                        logger.warning("브라우저 재시작 시도...")

                        driver = self._restart_browser(driver, headless=not use_browser)
                        if driver is None:
                            logger.error("❌ 브라우저 재시작 실패")
                            keyword_success = False
                        else:
                            logger.info("✅ 브라우저 재시작 성공, 이 키워드는 건너뜁니다.")
                            keyword_success = False

                    except Exception as e:
                        logger.error(f"💥 '{keyword}' 예상치 못한 오류: {e}", exc_info=True)
                        keyword_success = False

                except Exception as e:
                    logger.error(f"💥 '{keyword}' 처리 중 치명적 오류: {e}", exc_info=True)
                    keyword_success = False

                # 결과 기록
                results[keyword] = keyword_success

                # 키워드 간 간격 (서버 부하 방지)
                if i < len(keywords):
                    logger.info("⏳ 다음 키워드까지 3초 대기...")
                    time.sleep(3)

            # 최종 통계
            logger.info(f"\n{'='*60}")
            logger.info(f"📊 전체 분석 완료")
            logger.info(f"{'='*60}")
            success_count = sum(results.values())
            logger.info(f"✅ 성공: {success_count}/{len(keywords)}")
            logger.info(f"❌ 실패: {len(keywords) - success_count}/{len(keywords)}")

        except KeyboardInterrupt:
            logger.warning("\n⚠️  사용자 중단 (Ctrl+C)")
            # 현재까지 처리하지 못한 키워드들은 실패 처리
            for kw in keywords:
                if kw not in results:
                    results[kw] = False

        except Exception as e:
            logger.error(f"💥 치명적 오류 발생: {e}", exc_info=True)
            # 처리하지 못한 키워드들은 실패 처리
            for kw in keywords:
                if kw not in results:
                    results[kw] = False

        finally:
            # 브라우저 정리 (반드시 실행)
            logger.info("\n🔄 브라우저 정리 중...")
            self._cleanup_browser(driver)
            logger.info("✅ 정리 완료")

        return results


def main():
    """메인 실행 함수"""
    import argparse

    parser = argparse.ArgumentParser(description='분석되지 않은 키워드 선택 및 분석')
    parser.add_argument('-m', '--method', choices=['random', 'priority', 'all'],
                       default='random', help='키워드 선택 방법')
    parser.add_argument('-c', '--count', type=int, default=5, help='선택할 키워드 개수')
    parser.add_argument('-l', '--limit', type=int, default=100, help='스크래핑할 개수')
    parser.add_argument('--headless', action='store_true', help='헤드리스 모드 사용 (기본값: 브라우저 모드)')
    parser.add_argument('--browser', action='store_true', help='브라우저 모드 강제 사용')
    parser.add_argument('--list-only', action='store_true', help='키워드만 출력하고 실행하지 않음')
    parser.add_argument('--priority', nargs='*', help='우선순위 키워드들')

    args = parser.parse_args()

    # 키워드 분석기 초기화
    analyzer = KeywordAnalyzer()

    # 키워드 선택
    selected_keywords = analyzer.select_keywords(
        method=args.method,
        count=args.count,
        priority_keywords=args.priority
    )

    if not selected_keywords:
        logger.error("❌ 선택할 키워드가 없습니다.")
        return

    print(f"\n🎯 선택된 키워드들 ({len(selected_keywords)}개):")
    for i, keyword in enumerate(selected_keywords, 1):
        print(f"  {i}. {keyword}")

    if args.list_only:
        logger.info("ℹ️ --list-only 옵션으로 실행을 건너뜁니다.")
        return

    # 사용자 확인
    confirm = input(f"\n🚀 위 키워드들로 분석을 시작하시겠습니까? (y/N): ")
    if confirm.lower() not in ['y', 'yes']:
        logger.info("ℹ️ 사용자가 취소했습니다.")
        return

    # 분석 실행 (기본적으로 브라우저 모드 사용, --headless 옵션이 있으면 헤드리스 모드)
    use_browser_mode = not args.headless
    results = analyzer.analyze_selected_keywords(
        keywords=selected_keywords,
        limit=args.limit,
        use_browser=use_browser_mode
    )

    # 결과 요약
    print(f"\n📊 분석 결과:")
    success_count = sum(results.values())
    total_count = len(results)

    for keyword, success in results.items():
        status = "✅ 성공" if success else "❌ 실패"
        print(f"  {keyword}: {status}")

    print(f"\n🎉 완료: {success_count}/{total_count} 성공")


if __name__ == "__main__":
    main()
