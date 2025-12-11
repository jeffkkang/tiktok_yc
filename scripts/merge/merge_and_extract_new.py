#!/usr/bin/env python3
"""
새로 수집된 데이터에서 기존 파일에 없는 프로필 추출 및 통합
"""

import pandas as pd
import re
from pathlib import Path
from glob import glob

def normalize_email(email: str) -> str:
    """이메일 정규화"""
    if not email or pd.isna(email):
        return ""
    email = str(email).strip().lower().replace(' ', '')
    email_pattern = r'^[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}$'
    if re.match(email_pattern, email):
        return email
    return ""

def normalize_username(username: str) -> str:
    """사용자명 정규화"""
    if not username or pd.isna(username):
        return ""
    return str(username).strip().lower().replace('@', '')

print("=" * 60)
print("새 프로필 추출 및 통합")
print("=" * 60)

# 1. 기존 파일 로드
existing_file = Path('final_filtered_results_with_followers.csv')
print(f"\n📂 기존 파일 로드: {existing_file.name}")
df_existing = pd.read_csv(existing_file)
print(f"   기존 프로필: {len(df_existing):,}개")

# 기존 파일도 정규화
df_existing['creator_email_normalized'] = df_existing['creator_email'].apply(normalize_email)
df_existing['creator_username_normalized'] = df_existing['creator_username'].apply(normalize_username)

# 기존 이메일 및 유저명 세트
existing_emails = set(df_existing['creator_email_normalized'].dropna())
existing_emails = {e for e in existing_emails if e != ''}
existing_usernames = set(df_existing['creator_username_normalized'].dropna())
existing_usernames = {u for u in existing_usernames if u != ''}
print(f"   기존 이메일: {len(existing_emails):,}개")
print(f"   기존 유저명: {len(existing_usernames):,}개")

# 2. 모든 results CSV 파일 로드
print(f"\n📂 results 디렉토리 스캔 중...")
csv_files = glob('results/*_api_v4.csv')
print(f"   발견된 파일: {len(csv_files)}개")

all_data = []
for csv_file in csv_files:
    try:
        df = pd.read_csv(csv_file)
        if len(df) > 0:
            all_data.append(df)
    except Exception as e:
        print(f"   ⚠️  {Path(csv_file).name} 로드 실패: {e}")

if not all_data:
    print("\n❌ 로드할 데이터가 없습니다!")
    exit(1)

df_all = pd.concat(all_data, ignore_index=True)
print(f"\n📊 전체 데이터: {len(df_all):,}개")

# 3. 이메일 및 유저명 정규화
print(f"\n🔧 데이터 정규화 중...")
df_all['creator_email_normalized'] = df_all['creator_email'].apply(normalize_email)
df_all['creator_username_normalized'] = df_all['creator_username'].apply(normalize_username)

# 4. 새로운 프로필만 필터링
print(f"\n🔍 새로운 프로필 필터링 중...")

# 이메일이 있고 기존에 없는 것
df_new_email = df_all[
    (df_all['creator_email_normalized'] != '') &
    (~df_all['creator_email_normalized'].isin(existing_emails))
]

# 이메일은 없지만 유저명이 새로운 것
df_new_username = df_all[
    (df_all['creator_email_normalized'] == '') &
    (df_all['creator_username_normalized'] != '') &
    (~df_all['creator_username_normalized'].isin(existing_usernames))
]

df_new = pd.concat([df_new_email, df_new_username], ignore_index=True)

print(f"   새 이메일: {len(df_new_email):,}개")
print(f"   새 유저명 (이메일 없음): {len(df_new_username):,}개")
print(f"   총 새 프로필: {len(df_new):,}개")

if len(df_new) == 0:
    print("\n⚠️  새로운 프로필이 없습니다!")
    exit(0)

# 5. 중복 제거
print(f"\n🔧 중복 제거 중...")
before = len(df_new)

# 이메일이 있는 것끼리 중복 제거
df_with_email = df_new[df_new['creator_email_normalized'] != ''].drop_duplicates(
    subset=['creator_email_normalized'], keep='first'
)

# 이메일이 없는 것끼리 유저명으로 중복 제거
df_no_email = df_new[df_new['creator_email_normalized'] == ''].drop_duplicates(
    subset=['creator_username_normalized'], keep='first'
)

df_new = pd.concat([df_with_email, df_no_email], ignore_index=True)

print(f"   제거된 중복: {before - len(df_new):,}개")
print(f"   최종 새 프로필: {len(df_new):,}개")

# 6. follower_count 컬럼 추가 (초기값 0)
df_new['follower_count'] = 0

# 7. 저장
output_file = Path('new_profiles_for_enrichment.csv')
df_new.to_csv(output_file, index=False, encoding='utf-8-sig')

print(f"\n💾 저장 완료: {output_file}")
print(f"   파일 크기: {output_file.stat().st_size / 1024:.1f} KB")

# 8. 통계
df_with_email_final = df_new[df_new['creator_email_normalized'] != '']
print(f"\n📊 최종 통계:")
print(f"   총 새 프로필: {len(df_new):,}개")
print(f"   이메일 보유: {len(df_with_email_final):,}개 ({100*len(df_with_email_final)/len(df_new):.1f}%)")
print(f"   이메일 없음: {len(df_new) - len(df_with_email_final):,}개")

print("\n" + "=" * 60)
print("✅ 완료!")
print("=" * 60)
