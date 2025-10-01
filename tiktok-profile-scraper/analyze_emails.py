#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import re
import datetime

# 결과 파일 로드
with open('tiktok_results.json', 'r') as f:
    data = json.load(f)

# 모든 이메일 수집
all_emails = []
for profile in data:
    all_emails.extend(profile['emails'])

# 이메일 정제
clean_emails = []
seen_emails = set()

for email in all_emails:
    # 이메일 뒤에 붙은 사용자명 제거 (예: email@gmail.com.username -> email@gmail.com) 
    clean = re.sub(r'\\.[^@]+$', '', email)
    
    # 'n'으로 시작하는 오류 수정 (예: nemail@domain.com -> email@domain.com)
    if clean.startswith('n') and '@' in clean:
        clean = clean[1:]
    
    # 'icolemoosemakeup' -> 'nicolemoosemakeup' 등 특정 오류 수정
    if clean.startswith('icole') and 'gmail.com' in clean:
        clean = 'n' + clean
        
    # '-' 접두사 제거 (예: -email@gmail.com -> email@gmail.com)
    if clean.startswith('-'):
        clean = clean[1:]
    
    # u002F@ 형식의 잘못된 이메일은 제외
    if 'u002F@' in clean:
        continue
        
    # 이메일 형식 검증
    if '@' in clean and '.' in clean.split('@')[1] and clean not in seen_emails:
        seen_emails.add(clean)
        clean_emails.append(clean)

# 도메인별 통계
domains = {}
for email in clean_emails:
    domain = email.split('@')[1]
    domains[domain] = domains.get(domain, 0) + 1

# 결과 출력
print(f"=== 이메일 분석 결과 ===")
print(f"총 추출 이메일 수: {len(all_emails)}개")
print(f"중복 제거 후 고유 이메일 수: {len(clean_emails)}개")
print("\n이메일 도메인 통계 (상위 10개):")
for domain, count in sorted(domains.items(), key=lambda x: x[1], reverse=True)[:10]:
    print(f"  - {domain}: {count}개 ({count/len(clean_emails)*100:.1f}%)")

# 이메일 목록 출력
print("\n모든 고유 이메일 목록:")
for email in sorted(clean_emails):
    print(f"  - {email}")

# 파일로 저장
with open('unique_emails.txt', 'w') as f:
    for email in sorted(clean_emails):
        f.write(f"{email}\n")

print(f"\n고유 이메일 목록이 unique_emails.txt 파일에 저장되었습니다.")