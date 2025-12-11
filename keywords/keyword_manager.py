#!/usr/bin/env python3
"""키워드 관리 시스템 - 중복 방지 및 히스토리 추적"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import List, Set, Dict
import pandas as pd


class KeywordManager:
    """키워드 사용 이력 관리 및 중복 방지"""

    def __init__(self,
                 history_file: str = 'keyword_history.json',
                 results_dir: str = 'results'):
        self.history_file = Path(history_file)
        self.results_dir = Path(results_dir)
        self.history = self._load_history()

    def _load_history(self) -> Dict:
        """키워드 히스토리 로드"""
        if self.history_file.exists():
            with open(self.history_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {
            'used_keywords': [],
            'keyword_stats': {},
            'last_updated': None
        }

    def _save_history(self):
        """키워드 히스토리 저장"""
        self.history['last_updated'] = datetime.now().isoformat()
        with open(self.history_file, 'w', encoding='utf-8') as f:
            json.dump(self.history, f, indent=2, ensure_ascii=False)

    def get_used_keywords(self) -> Set[str]:
        """사용된 키워드 목록 반환"""
        return set(self.history['used_keywords'])

    def mark_keyword_used(self, keyword: str, item_count: int = 0):
        """키워드를 사용됨으로 표시"""
        if keyword not in self.history['used_keywords']:
            self.history['used_keywords'].append(keyword)

        # 통계 업데이트
        if keyword not in self.history['keyword_stats']:
            self.history['keyword_stats'][keyword] = {
                'first_scraped': datetime.now().isoformat(),
                'total_scrapes': 0,
                'total_items': 0,
                'last_scraped': None
            }

        stats = self.history['keyword_stats'][keyword]
        stats['total_scrapes'] += 1
        stats['total_items'] += item_count
        stats['last_scraped'] = datetime.now().isoformat()

        self._save_history()

    def filter_new_keywords(self, keywords: List[str]) -> List[str]:
        """새로운 키워드만 필터링"""
        used = self.get_used_keywords()
        return [k for k in keywords if k not in used]

    def scan_results_directory(self):
        """results 디렉토리를 스캔하여 히스토리 업데이트"""
        if not self.results_dir.exists():
            return

        for csv_file in self.results_dir.glob('*_api_v4.csv'):
            # 파일명에서 키워드 추출
            keyword = csv_file.stem.replace('_api_v4', '')

            # CSV 파일 읽어서 아이템 수 확인
            try:
                df = pd.read_csv(csv_file)
                item_count = len(df)

                # 빈 파일이 아닌 경우만 표시
                if item_count > 0:
                    self.mark_keyword_used(keyword, item_count)
            except Exception as e:
                print(f"⚠️  파일 읽기 실패: {csv_file.name} - {e}")

    def get_statistics(self) -> Dict:
        """키워드 통계 반환"""
        total_keywords = len(self.history['used_keywords'])
        total_items = sum(
            stats['total_items']
            for stats in self.history['keyword_stats'].values()
        )

        return {
            'total_keywords_used': total_keywords,
            'total_items_collected': total_items,
            'average_items_per_keyword': total_items / total_keywords if total_keywords > 0 else 0,
            'last_updated': self.history.get('last_updated')
        }

    def export_used_keywords(self, output_file: str = 'used_keywords.txt'):
        """사용된 키워드를 파일로 출력"""
        used = sorted(self.get_used_keywords())
        with open(output_file, 'w', encoding='utf-8') as f:
            for keyword in used:
                stats = self.history['keyword_stats'].get(keyword, {})
                item_count = stats.get('total_items', 0)
                f.write(f"{keyword} ({item_count} items)\n")

        print(f"✅ 사용된 키워드 {len(used)}개를 {output_file}에 저장했습니다")

    def consolidate_duplicate_files(self):
        """중복된 파일 통합 (예: beautyreview vs beauty review)"""
        consolidated = {}

        for csv_file in self.results_dir.glob('*_api_v4.csv'):
            keyword = csv_file.stem.replace('_api_v4', '')
            normalized = keyword.replace(' ', '').lower()

            if normalized not in consolidated:
                consolidated[normalized] = []
            consolidated[normalized].append(csv_file)

        # 중복이 있는 경우 병합
        for normalized, files in consolidated.items():
            if len(files) > 1:
                print(f"\n📋 중복 발견: {normalized}")
                all_data = []

                for file in files:
                    try:
                        df = pd.read_csv(file)
                        if len(df) > 0:
                            print(f"   - {file.name}: {len(df)} items")
                            all_data.append(df)
                    except Exception as e:
                        print(f"   ⚠️  {file.name}: 읽기 실패")

                if all_data:
                    # 병합 및 중복 제거
                    merged = pd.concat(all_data, ignore_index=True)
                    merged = merged.drop_duplicates(subset=['video_id'], keep='first')

                    # 새 파일명 (공백 없는 버전 사용)
                    new_filename = self.results_dir / f"{normalized}_api_v4.csv"
                    merged.to_csv(new_filename, index=False, encoding='utf-8-sig')

                    print(f"   ✅ 병합 완료: {len(merged)} items → {new_filename.name}")

                    # 중복 파일 삭제
                    for file in files:
                        if file != new_filename:
                            file.unlink()
                            print(f"   🗑️  삭제: {file.name}")


def main():
    """메인 함수"""
    print("=" * 60)
    print("키워드 관리 시스템")
    print("=" * 60)
    print()

    manager = KeywordManager()

    # 1. results 디렉토리 스캔
    print("📂 results 디렉토리 스캔 중...")
    manager.scan_results_directory()

    # 2. 통계 출력
    print("\n📊 통계:")
    stats = manager.get_statistics()
    print(f"   - 사용된 키워드: {stats['total_keywords_used']}개")
    print(f"   - 수집된 아이템: {stats['total_items_collected']}개")
    print(f"   - 키워드당 평균: {stats['average_items_per_keyword']:.1f}개")

    # 3. 사용된 키워드 출력
    print("\n📝 사용된 키워드 목록:")
    used = sorted(manager.get_used_keywords())
    for keyword in used:
        stats = manager.history['keyword_stats'].get(keyword, {})
        item_count = stats.get('total_items', 0)
        print(f"   ✓ {keyword} ({item_count} items)")

    # 4. 파일로 저장
    manager.export_used_keywords()

    # 5. 중복 파일 통합
    print("\n🔍 중복 파일 검사 및 통합...")
    manager.consolidate_duplicate_files()

    print("\n" + "=" * 60)
    print("✅ 완료!")
    print("=" * 60)


if __name__ == '__main__':
    main()
