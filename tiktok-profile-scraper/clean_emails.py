#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import re
import os

# 결과 파일 로드
with open('tiktok_results.json', 'r') as f:
    data = json.load(f)

# 정제된 결과를 저장할 리스트
cleaned_results = []

# 이미 처리한 이메일 추적
processed_emails = set()

# 각 프로필 처리
for profile in data:
    username = profile['username']
    raw_emails = profile['emails']
    
    # 이메일 정제
    cleaned_emails = []
    
    for email in raw_emails:
        # 기본적인 이메일 형식 검사
        if not '@' in email or not '.' in email.split('@')[1]:
            continue
            
        # 패턴 1: 이메일 뒤에 붙은 유저네임 제거 (예: email@gmail.com.username -> email@gmail.com)
        clean_email = re.sub(r'\.[^@.]+$', '', email)
        
        # 패턴 2: 'n'으로 시작하는 오류 수정 (예: nemail@domain.com -> email@domain.com)
        if clean_email.startswith('n') and '@' in clean_email:
            clean_email = clean_email[1:]
            
        # 패턴 3: 'icole'로 시작하는 경우 'nicole'로 수정 (예: icolemoosemakeup@gmail.com -> nicolemoosemakeup@gmail.com)
        if clean_email.startswith('icole') and 'gmail.com' in clean_email:
            clean_email = 'n' + clean_email
            
        # 패턴 4: '-'로 시작하는 이메일 수정 (예: -email@gmail.com -> email@gmail.com)
        if clean_email.startswith('-'):
            clean_email = clean_email[1:]
            
        # 패턴 5: u002F@ 형식의 이메일 제외
        if 'u002F@' in clean_email:
            continue
            
        # 패턴 6: 도메인 수정 (예: myyahoo.com -> yahoo.com)
        if '@myyahoo.com' in clean_email:
            clean_email = clean_email.replace('@myyahoo.com', '@yahoo.com')
            
        # 패턴 7: 이메일에 공백이 있는 경우 제거
        clean_email = clean_email.strip()
        
        # 패턴 8: 도메인이 없는 이메일 제외
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', clean_email):
            continue
            
        # 중복 방지
        if clean_email not in processed_emails:
            processed_emails.add(clean_email)
            cleaned_emails.append(clean_email)
    
    # 정제된 정보 저장
    if cleaned_emails:  # 유효한 이메일이 있는 경우만 저장
        cleaned_results.append({
            "username": username,
            "emails": cleaned_emails
        })

# 새 파일로 저장
with open('cleaned_tiktok_emails.json', 'w') as f:
    json.dump(cleaned_results, f, indent=2)

# CSV 형식으로도 저장
with open('cleaned_tiktok_emails.csv', 'w') as f:
    f.write("username,email\n")
    for profile in cleaned_results:
        username = profile['username']
        for email in profile['emails']:
            f.write(f"{username},{email}\n")

print(f"정제된 데이터가 cleaned_tiktok_emails.json 및 cleaned_tiktok_emails.csv 파일에 저장되었습니다.")
print(f"총 {len(cleaned_results)} 개의 프로필에서 유효한 이메일을 찾았습니다.")
print(f"총 {len(processed_emails)} 개의 고유한 이메일을 추출했습니다.")