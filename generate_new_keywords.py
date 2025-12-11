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
                'lips', 'hair', 'nails', 'body', 'wellness', 'selfcare', 'routine',
                'facial', 'serum', 'moisturizer', 'cleanser', 'toner', 'mask', 'sunscreen',
                'foundation', 'concealer', 'blush', 'bronzer', 'highlighter', 'eyeshadow',
                'mascara', 'eyeliner', 'brows', 'lipstick', 'lipgloss', 'liner',
                'shampoo', 'conditioner', 'treatment', 'styling', 'haircare'
            ],
            'adjectives': [
                'natural', 'organic', 'clean', 'green', 'sustainable', 'vegan', 'crueltyfree',
                'korean', 'japanese', 'french', 'american', 'luxury', 'affordable', 'drugstore',
                'highend', 'budget', 'premium', 'daily', 'nightly', 'morning', 'evening',
                'quick', 'easy', 'simple', 'advanced', 'professional', 'beginner',
                'trending', 'viral', 'popular', 'favorite', 'musthave', 'essential',
                'best', 'top', 'ultimate', 'perfect', 'amazing', 'beautiful', 'gorgeous',
                'flawless', 'radiant', 'glowing', 'fresh', 'healthy', 'youthful',
                'gentle', 'sensitive', 'hypoallergenic', 'dermatologist', 'tested',
                'waterproof', 'longwear', 'longlasting', 'transfer', 'proof',
                'matte', 'dewy', 'glossy', 'shimmer', 'glitter', 'metallic',
                'nude', 'bold', 'bright', 'pastel', 'dark', 'light'
            ],
            'actions': [
                'routine', 'tutorial', 'review', 'tips', 'hacks', 'tricks', 'secrets',
                'guide', 'howto', 'diy', 'transformation', 'beforeafter', 'comparison',
                'favorites', 'recommendations', 'musthaves', 'essentials', 'collection',
                'haul', 'unboxing', 'firstimpression', 'demo', 'swatches', 'application',
                'grwm', 'getready', 'prep', 'apply', 'blend', 'contour', 'highlight',
                'skinprep', 'baseprep', 'eyeprep', 'lipprep', 'setting', 'finishing'
            ],
            'targets': [
                'products', 'brands', 'items', 'essentials', 'favorites', 'recommendations',
                'discoveries', 'finds', 'gems', 'hidden', 'underrated', 'overrated',
                'dupes', 'alternatives', 'options', 'choices', 'picks', 'selections'
            ],
            'skin_types': [
                'dry', 'oily', 'combination', 'sensitive', 'acne', 'mature', 'aging',
                'normal', 'dehydrated', 'problematic', 'rosacea', 'eczema'
            ],
            'concerns': [
                'antiaging', 'wrinkles', 'finelines', 'darkspots', 'hyperpigmentation',
                'acne', 'pores', 'blackheads', 'whiteheads', 'redness', 'dryness',
                'oiliness', 'dullness', 'texture', 'scarring', 'darkcircles', 'puffiness',
                'sagging', 'firming', 'brightening', 'hydrating', 'soothing'
            ],
            'ingredients': [
                'retinol', 'niacinamide', 'vitamin', 'hyaluronic', 'ceramide', 'peptide',
                'collagen', 'snail', 'cica', 'centella', 'tea', 'glycolic', 'salicylic',
                'azelaic', 'lactic', 'mandelic', 'bakuchiol', 'squalane', 'rosehip'
            ],
            'trends': [
                'kbeauty', 'jbeauty', 'cbeauty', 'glassskin', 'slugging', 'skincycling',
                'doublecleanse', 'layering', 'essence', 'ampule', 'sheet', 'overnight',
                'nofilter', 'nomakeup', 'natural', 'minimal', 'maximalist', 'euphoria',
                'clean', 'indie', 'viral', 'tiktok', 'fyp'
            ],
            'occasions': [
                'everyday', 'work', 'school', 'date', 'wedding', 'party', 'festival',
                'summer', 'winter', 'spring', 'fall', 'holiday', 'vacation', 'beach',
                'night', 'day', 'casual', 'formal', 'glam'
            ],
            'intensity': [
                'minimal', 'natural', 'light', 'medium', 'full', 'glam', 'soft', 'bold',
                'subtle', 'dramatic', 'nude', 'smokey', 'glowy', 'matte'
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

        for file_path_str in keyword_files:
            file_path = self.base_dir / file_path_str
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

    def generate_combinations(self, max_keywords: int = 200) -> List[str]:
        """새로운 키워드 조합 생성 - 더 다양한 패턴"""
        existing = self.load_existing_keywords()
        new_keywords = set()
        import random

        print(f"기존 키워드 수: {len(existing)}개")
        print("다양한 패턴으로 키워드 생성 중...\n")

        # 패턴 1: 스킨타입 + 카테고리 (예: dryskincare, oilyskin)
        print("📌 패턴 1: 스킨타입 조합")
        for skin in self.base_elements['skin_types']:
            for cat in random.sample(self.base_elements['categories'], min(20, len(self.base_elements['categories']))):
                combo = f"{skin}{cat}"
                if combo not in existing and 6 <= len(combo) <= 25:
                    new_keywords.add(combo)

        # 패턴 2: 문제해결 + 카테고리 (예: acnetreatment, antiagingserum)
        print("📌 패턴 2: 문제해결 조합")
        for concern in self.base_elements['concerns']:
            for cat in random.sample(self.base_elements['categories'], min(15, len(self.base_elements['categories']))):
                combo = f"{concern}{cat}"
                if combo not in existing and 6 <= len(combo) <= 25:
                    new_keywords.add(combo)

        # 패턴 3: 성분 + 카테고리 (예: retinolserum, niacinamidetoner)
        print("📌 패턴 3: 성분 조합")
        for ingredient in self.base_elements['ingredients']:
            for cat in random.sample(self.base_elements['categories'], min(12, len(self.base_elements['categories']))):
                combo = f"{ingredient}{cat}"
                if combo not in existing and 6 <= len(combo) <= 25:
                    new_keywords.add(combo)

        # 패턴 4: 트렌드 + 액션/카테고리 (예: kbeautyroutine, glassskintutorial)
        print("📌 패턴 4: 트렌드 조합")
        for trend in self.base_elements['trends']:
            for action in random.sample(self.base_elements['actions'], min(10, len(self.base_elements['actions']))):
                combo = f"{trend}{action}"
                if combo not in existing and 6 <= len(combo) <= 25:
                    new_keywords.add(combo)

        # 패턴 5: 상황별 + 강도 + 카테고리 (예: daynaturalmakeup, nightglam)
        print("📌 패턴 5: 상황별 조합")
        for occasion in self.base_elements['occasions']:
            for intensity in random.sample(self.base_elements['intensity'], min(8, len(self.base_elements['intensity']))):
                combo = f"{occasion}{intensity}makeup"
                if combo not in existing and 8 <= len(combo) <= 25:
                    new_keywords.add(combo)

        # 패턴 6: 형용사 + 카테고리 (예: koreanmakeup, naturalskincare)
        print("📌 패턴 6: 형용사 조합")
        for adj in random.sample(self.base_elements['adjectives'], min(30, len(self.base_elements['adjectives']))):
            for cat in random.sample(self.base_elements['categories'], min(20, len(self.base_elements['categories']))):
                combo = f"{adj}{cat}"
                if combo not in existing and 6 <= len(combo) <= 25:
                    new_keywords.add(combo)

        # 패턴 7: 카테고리 + 액션 (예: makeuptutorial, skincarereview)
        print("📌 패턴 7: 카테고리 + 액션 조합")
        for cat in self.base_elements['categories']:
            for action in random.sample(self.base_elements['actions'], min(15, len(self.base_elements['actions']))):
                combo = f"{cat}{action}"
                if combo not in existing and 6 <= len(combo) <= 25:
                    new_keywords.add(combo)

        # 패턴 8: 형용사 + 액션 (예: quicktutorial, easyroutine)
        print("📌 패턴 8: 형용사 + 액션 조합")
        for adj in random.sample(self.base_elements['adjectives'], min(25, len(self.base_elements['adjectives']))):
            for action in random.sample(self.base_elements['actions'], min(12, len(self.base_elements['actions']))):
                combo = f"{adj}{action}"
                if combo not in existing and 6 <= len(combo) <= 25:
                    new_keywords.add(combo)

        # 패턴 9: 3단어 조합 - 트렌드 + 카테고리 + 액션 (예: kbeautyskincarehaul)
        print("📌 패턴 9: 트렌드 3단어 조합")
        for trend in random.sample(self.base_elements['trends'], min(10, len(self.base_elements['trends']))):
            for cat in random.sample(self.base_elements['categories'], min(8, len(self.base_elements['categories']))):
                for action in random.sample(self.base_elements['actions'], min(8, len(self.base_elements['actions']))):
                    combo = f"{trend}{cat}{action}"
                    if combo not in existing and 10 <= len(combo) <= 30:
                        new_keywords.add(combo)

        # 패턴 10: 스킨타입 + 문제해결 (예: dryskinhydrating, oilyskinacne)
        print("📌 패턴 10: 스킨타입 + 문제해결 조합")
        for skin in self.base_elements['skin_types']:
            for concern in random.sample(self.base_elements['concerns'], min(10, len(self.base_elements['concerns']))):
                combo = f"{skin}skin{concern}"
                if combo not in existing and 8 <= len(combo) <= 30:
                    new_keywords.add(combo)

        # 필터링: 적절한 길이의 키워드만 선택
        filtered = [kw for kw in new_keywords if 5 <= len(kw) <= 30]

        # 랜덤 샘플링으로 개수 제한
        selected = random.sample(filtered, min(max_keywords, len(filtered)))

        print(f"\n✅ 총 생성 가능한 키워드 수: {len(filtered)}개")
        print(f"✅ 선택된 새 키워드 수: {len(selected)}개")

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

    print("=" * 60)
    print("🎯 새로운 키워드 생성 시작 - 다양성 강화 버전")
    print("=" * 60)
    print()

    # 새 키워드 생성 (더 많은 개수)
    new_keywords = generator.generate_combinations(max_keywords=200)

    # 유효성 검증
    valid_keywords = generator.validate_keywords(new_keywords)

    print(f"\n{'=' * 60}")
    print(f"✅ 생성된 유효한 키워드들 ({len(valid_keywords)}개)")
    print("=" * 60)

    # 키워드 미리보기 (처음 30개만)
    print("\n📋 키워드 미리보기 (처음 30개):")
    print("-" * 60)
    for i, keyword in enumerate(valid_keywords[:30], 1):
        print(f"{i:3d}. {keyword}")

    if len(valid_keywords) > 30:
        print(f"\n... 그 외 {len(valid_keywords) - 30}개 키워드")

    # 파일로 저장
    output_file = Path('keywords/fresh_beauty_keywords.txt')
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, 'w', encoding='utf-8') as f:
        for keyword in valid_keywords:
            f.write(f"{keyword}\n")

    # 통계 정보
    print(f"\n{'=' * 60}")
    print("📊 키워드 통계:")
    print("-" * 60)
    print(f"총 생성된 키워드: {len(valid_keywords)}개")
    print(f"평균 키워드 길이: {sum(len(k) for k in valid_keywords) / len(valid_keywords):.1f}자")
    print(f"최단 키워드: {min(valid_keywords, key=len)} ({len(min(valid_keywords, key=len))}자)")
    print(f"최장 키워드: {max(valid_keywords, key=len)} ({len(max(valid_keywords, key=len))}자)")

    print(f"\n💾 저장 위치: {output_file.absolute()}")
    print(f"\n✨ 총 {len(valid_keywords)}개의 다양한 키워드 생성 완료!")
    print("=" * 60)

    return valid_keywords


if __name__ == "__main__":
    main()
