#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import re

# 데이터 로드
with open('tiktok_results.json', 'r') as f:
    data = json.load(f)

# 현재 배치의 사용자 이름 로드
usernames = []
with open('usernames.txt', 'r') as f:
    usernames = [line.strip().strip('@') for line in f.readlines()]

# 현재 배치 결과 추출
current_batch = [profile for profile in data if profile['username'] in usernames]

# 이메일이 있는 계정과 없는 계정으로 분류
accounts_with_email = [profile for profile in current_batch if profile['emails']]
accounts_without_email = [profile for profile in current_batch if not profile['emails']]

# 결과 출력
print(f"==== 현재 배치 계정 분석 ====")
print(f"총 계정 수: {len(current_batch)}개")
print(f"이메일 추출 성공: {len(accounts_with_email)}개 ({len(accounts_with_email)/len(current_batch)*100:.1f}%)")
print(f"이메일 추출 실패: {len(accounts_without_email)}개 ({len(accounts_without_email)/len(current_batch)*100:.1f}%)")

print("\n이메일이 있는 계정:")
for profile in sorted(accounts_with_email, key=lambda x: x['username']):
    # 이메일 정제
    cleaned_emails = []
    for email in profile['emails']:
        email = re.sub(r'\.[^@]+$', '', email)
        if email.startswith('n') and '@' in email:
            email = email[1:]
        if '@' in email and not email.startswith('u002F@') and email not in cleaned_emails:
            cleaned_emails.append(email)
    
    # 출력
    print(f"- @{profile['username']}: {', '.join(cleaned_emails)}")

print("\n이메일이 없는 계정:")
for profile in sorted(accounts_without_email, key=lambda x: x['username']):
    print(f"- @{profile['username']}")

# 모든 계정에서 추출된 이메일 통계
all_emails = []
for profile in data:
    for email in profile['emails']:
        # 이메일 정제
        email = re.sub(r'\.[^@]+$', '', email)
        if email.startswith('n') and '@' in email:
            email = email[1:]
        if '@' in email and not email.startswith('u002F@') and email not in all_emails:
            all_emails.append(email)

print(f"\n총 고유 이메일 수: {len(all_emails)}개")