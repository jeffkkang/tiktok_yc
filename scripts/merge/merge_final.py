#!/usr/bin/env python3
"""
새로운 배치 프로필을 기존 파일과 통합
"""

import pandas as pd
from pathlib import Path

print("=" * 60)
print("최종 프로필 통합")
print("=" * 60)

# 기존 파일들 로드
files = [
    'final_filtered_results_with_followers.csv',
    'new_profiles_with_followers.csv',
    'new_batch_with_followers.csv'
]

all_dfs = []
total = 0

for file in files:
    file_path = Path(file)
    if file_path.exists():
        print(f"\n📂 파일 로드: {file}")
        df = pd.read_csv(file_path)
        print(f"   프로필 수: {len(df):,}개")
        all_dfs.append(df)
        total += len(df)
    else:
        print(f"\n⚠️  파일 없음: {file}")

if not all_dfs:
    print("\n❌ 로드할 파일이 없습니다!")
    exit(1)

# 통합
print(f"\n🔧 통합 중...")
df_combined = pd.concat(all_dfs, ignore_index=True)
print(f"   총 프로필: {len(df_combined):,}개")

# 저장
output_file = Path('all_profiles_with_followers.csv')
df_combined.to_csv(output_file, index=False, encoding='utf-8-sig')

print(f"\n💾 저장 완료: {output_file}")
print(f"   파일 크기: {output_file.stat().st_size / 1024:.1f} KB")

# 통계
df_with_followers = df_combined[df_combined['follower_count'] > 0]
df_with_email = df_combined[df_combined['creator_email'].notna() & (df_combined['creator_email'] != '')]

print(f"\n📊 최종 통계:")
print(f"   총 프로필: {len(df_combined):,}개")
print(f"   팔로워 정보 있음: {len(df_with_followers):,}개 ({100*len(df_with_followers)/len(df_combined):.1f}%)")
print(f"   이메일 보유: {len(df_with_email):,}개 ({100*len(df_with_email)/len(df_combined):.1f}%)")

if len(df_with_followers) > 0:
    print(f"\n👥 팔로워 수 통계:")
    print(f"   평균: {df_with_followers['follower_count'].mean():,.0f}명")
    print(f"   중앙값: {df_with_followers['follower_count'].median():,.0f}명")
    print(f"   최대: {df_with_followers['follower_count'].max():,}명")
    print(f"   최소: {df_with_followers['follower_count'].min():,}명")

print("\n" + "=" * 60)
print("✅ 완료!")
print("=" * 60)
