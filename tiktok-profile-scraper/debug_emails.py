#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import re

# 결과 파일 로드
with open('tiktok_results.json', 'r') as f:
    data = json.load(f)

# 샘플 확인
sample_data = data[:5]
print("샘플 데이터:")
for profile in sample_data:
    print(f"사용자명: {profile['username']}")
    print(f"이메일: {profile['emails']}")
    print("-" * 40)

# 이메일이 있는 계정 수 확인
profiles_with_email = [p for p in data if p['emails']]
print(f"이메일이 있는 계정 수: {len(profiles_with_email)}")

# 샘플 이메일 정제 테스트
if profiles_with_email:
    test_profiles = profiles_with_email[:10]
    print("\n이메일 정제 테스트:")
    for profile in test_profiles:
        raw_email = profile['emails'][0] if profile['emails'] else "이메일 없음"
        
        # 테스트 1: 이메일 끝에 .username 패턴 제거
        clean_email1 = re.sub(r'\.[^@.]+$', '', raw_email)
        
        # 테스트 2: 이전 패턴에 추가로 다른 패턴도 적용
        clean_email2 = clean_email1
        if clean_email2.startswith('n') and '@' in clean_email2:
            clean_email2 = clean_email2[1:]
        
        print(f"사용자명: {profile['username']}")
        print(f"원본 이메일: {raw_email}")
        print(f"정제 1: {clean_email1}")
        print(f"정제 2: {clean_email2}")
        print("-" * 40)