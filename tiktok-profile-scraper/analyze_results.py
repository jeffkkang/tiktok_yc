#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import re

# 데이터 로드
with open('tiktok_results.json', 'r') as f:
    data = json.load(f)

# 모든 이메일 수집
all_emails = []
for profile in data:
    all_emails.extend(profile['emails'])

# 이메일 정제
clean_emails = []
for email in all_emails:
    # 이메일 뒤에 붙은 사용자명 제거 (예: email@gmail.com.username -> email@gmail.com) 
    clean = re.sub(r'\.[^@]+$', '', email)
    
    # 'n'으로 시작하는 오류 수정 (예: nemail@domain.com -> email@domain.com)
    if clean.startswith('n') and '@' in clean:
        clean = clean[1:]
        
    # 잘못된 이메일 형식 필터링 (u002F@)
    if clean not in clean_emails and '@' in clean and not clean.startswith('u002F@'):
        clean_emails.append(clean)

# 도메인 통계
domains = [email.split('@')[1] for email in clean_emails]
domain_counts = {}
for domain in domains:
    if domain in domain_counts:
        domain_counts[domain] += 1
    else:
        domain_counts[domain] = 1

# 결과 출력
print(f'추출된 총 이메일 수: {len(all_emails)}개')
print(f'고유 이메일 수 (정제 후): {len(clean_emails)}개')

print('\n가장 많이 나타난 이메일 도메인:')
for domain, count in sorted(domain_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
    print(f'- {domain}: {count}개')

print('\n고유 이메일 목록:')
for email in sorted(clean_emails):
    print(f'- {email}')