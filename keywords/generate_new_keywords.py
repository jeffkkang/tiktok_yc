#!/usr/bin/env python3
"""
새로운 뷰티 관련 키워드들을 생성하고 검증
"""

import json
from pathlib import Path
from typing import List, Set
import re

class KeywordGenerator:
    """새로운 키워드 생성기"""

    def __init__(self, base_dir: str = None):
        self.base_dir = Path(base_dir) if base_dir else Path.cwd()

        # 기본 키워드 요소들
        self.base_elements = {
            'categories': [
                'beauty', 'makeup', 'skincare', 'cosmetics', 'skin', 'face', 'eyes',
                'lips', 'hair', 'nails', 'body', 'wellness', 'selfcare', 'routine'
            ],
            'adjectives': [
                'natural', 'organic', 'clean', 'green', 'sustainable', 'vegan', 'crueltyfree',
                'korean', 'japanese', 'french', 'american', 'luxury', 'affordable', 'drugstore',
                'highend', 'budget', 'premium', 'daily', 'nightly', 'morning', 'evening',
                'quick', 'easy', 'simple', 'advanced', 'professional', 'beginner',
                'trending', 'viral', 'popular', 'favorite', 'musthave', 'essential',
                'best', 'top', 'ultimate', 'perfect', 'amazing', 'beautiful', 'gorgeous',
                'flawless', 'radiant', 'glowing', 'fresh', 'healthy', 'youthful'
            ],
            'actions': [
                'routine', 'tutorial', 'review', 'tips', 'hacks', 'tricks', 'secrets',
                'guide', 'howto', 'diy', 'transformation', 'beforeafter', 'comparison',
                'favorites', 'recommendations', 'musthaves', 'essentials', 'collection',
                'haul', 'unboxing', 'firstimpression', 'demo', 'swatches', 'application'
            ],
            'targets': [
                'products', 'brands', 'items', 'essentials', 'favorites', 'recommendations',
                'discoveries', 'finds', 'gems', 'hidden', 'underrated', 'overrated'
            ]
        }

    def load_existing_keywords(self) -> Set[str]:
        """이미 사용된 키워드들을 로드"""
        used_keywords = set()

        # 키워드 소스 파일들
        keyword_files = [
            'keywords/used_keywords.txt',
            'keywords/failed_keywords.txt',
            'keywords/popular_beauty_keywords.txt',
            'keywords/mega_beauty_keywords.txt',
            'keywords/high_volume_keywords.txt'
        ]

        for file_path in [self.base_dir / f for f in keyword_files]:
            if file_path.exists():
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        for line in f:
                            keyword = line.strip().lower()
                            if keyword and not keyword.startswith('#'):
                                used_keywords.add(keyword)
                except:
                    pass

        # 현재 결과 파일에서 키워드들도 확인
        results_file = self.base_dir / 'results' / 'all_profiles_with_followers_hybrid.csv'
        if results_file.exists():
            try:
                import pandas as pd
                df = pd.read_csv(results_file)
                existing_keywords = df['keyword'].unique()
                used_keywords.update(kw.lower().strip() for kw in existing_keywords if kw)
            except:
                pass

        return used_keywords

    def generate_combinations(self, max_keywords: int = 100) -> List[str]:
        """새로운 키워드 조합 생성"""
        existing = self.load_existing_keywords()
        new_keywords = set()

        print(f"기존 키워드 수: {len(existing)}개")

        # 다양한 조합 생성
        for category in self.base_elements['categories']:
            for adj in self.base_elements['adjectives'][:20]:  # 상위 형용사만 사용
                # 두 단어 조합
                combo = f"{adj}{category}"
                if combo not in existing and len(combo) >= 5:
                    new_keywords.add(combo)

                # 세 단어 조합 (카테고리 + 형용사 + 액션)
                for action in self.base_elements['actions'][:10]:
                    combo3 = f"{adj}{category}{action}"
                    if combo3 not in existing and len(combo3) >= 7:
                        new_keywords.add(combo3)

        # 필터링: 너무 길거나 너무 짧은 키워드 제외
        filtered = [kw for kw in new_keywords if 5 <= len(kw) <= 25]

        # 랜덤 샘플링으로 개수 제한
        import random
        selected = random.sample(filtered, min(max_keywords, len(filtered)))

        print(f"생성된 새 키워드 수: {len(selected)}개")

        return sorted(selected)

    def validate_keywords(self, keywords: List[str]) -> List[str]:
        """키워드 유효성 검증"""
        valid_keywords = []

        for keyword in keywords:
            # 기본 검증
            if not keyword or len(keyword) < 3:
                continue

            # 특수문자나 이모지 제외 (영문, 숫자, 공백만 허용)
            if not re.match(r'^[a-zA-Z0-9\s]+$', keyword):
                continue

            # 너무 일반적인 단어 제외
            common_words = {'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 'had', 'her', 'was', 'one', 'our', 'had', 'by', 'word', 'but', 'not', 'what', 'were', 'been', 'have', 'each', 'said', 'find'}
            words = set(keyword.lower().split())
            if words & common_words:
                continue

            valid_keywords.append(keyword)

        return valid_keywords

def main():
    """메인 실행 함수"""
    generator = KeywordGenerator()

    print("🎯 새로운 키워드 생성 중...")

    # 새 키워드 생성
    new_keywords = generator.generate_combinations(max_keywords=50)

    # 유효성 검증
    valid_keywords = generator.validate_keywords(new_keywords)

    print(f"\n✅ 생성된 유효한 키워드들 ({len(valid_keywords)}개):")
    print("-" * 50)

    for i, keyword in enumerate(valid_keywords, 1):
        print(f"{i:2d}. {keyword}")

    # 파일로 저장
    output_file = Path('new_beauty_keywords.txt')
    with open(output_file, 'w', encoding='utf-8') as f:
        for keyword in valid_keywords:
            f.write(f"{keyword}\n")

    print(f"\n💾 새 키워드들이 {output_file}에 저장되었습니다.")
    print(f"총 {len(valid_keywords)}개 키워드 생성 완료!")

    return valid_keywords


if __name__ == "__main__":
    main()
