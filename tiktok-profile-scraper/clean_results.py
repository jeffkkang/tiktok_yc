#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import re
import pandas as pd

def clean_email_data(input_file, output_file):
    # 1. JSON 파일 읽기
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # 2. 정리된 데이터를 저장할 리스트
    cleaned_data = []
    
    # 3. 각 항목 처리
    for item in data:
        # username 추출
        username = item.get('username', '')
        
        # 이메일 목록 추출 및 정리
        emails = item.get('emails', [])
        valid_emails = []
        
        for email in emails:
            # 비정상 패턴 필터링:
            # 1. 'n'으로 시작하는 이메일 제외
            # 2. 'u002F@'가 포함된 비정상 이메일 제외
            if not email.startswith('n') and 'u002F@' not in email:
                # 가장 기본적인 이메일 형식 추출 (example@domain.com)
                basic_match = re.search(r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', email)
                if basic_match:
                    basic_email = basic_match.group(1)
                    
                    # 도메인 뒤에 점이 있으면 해당 점 이후로 모두 제거
                    # 예: user@example.com.name -> user@example.com
                    parts = basic_email.split('@')
                    if len(parts) == 2:
                        username_part = parts[0]
                        domain_part = parts[1]
                        
                        # 도메인에서 첫 번째 점까지만 포함 (TLD)
                        domain_parts = domain_part.split('.')
                        if len(domain_parts) >= 2:
                            clean_domain = domain_parts[0] + '.' + domain_parts[1]
                            final_email = username_part + '@' + clean_domain
                            
                            # 중복 방지
                            if final_email not in valid_emails:
                                valid_emails.append(final_email)
        
        # 유효한 이메일이 하나 이상 있는 경우에만 데이터에 추가
        if valid_emails:
            cleaned_data.append({
                'username': username,
                'emails': valid_emails
            })
    
    # 4. 정리된 데이터를 JSON 파일로 저장
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(cleaned_data, f, ensure_ascii=False, indent=2)
    
    print(f"총 데이터 개수: {len(data)}")
    print(f"정리된 데이터 개수: {len(cleaned_data)}")
    print(f"필터링된 데이터 개수: {len(data) - len(cleaned_data)}")
    
    return cleaned_data

def json_to_excel(json_file, excel_file):
    # JSON 파일 읽기
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # 이메일과 이름을 저장할 리스트
    email_list = []
    username_list = []

    # 데이터 처리
    for item in data:
        username = item.get('username', '')
        emails = item.get('emails', [])
        for email in emails:
            email_list.append(email)
            username_list.append(username)

    # 데이터프레임 생성
    df = pd.DataFrame({'email': email_list, 'name': username_list})

    # 엑셀 파일로 저장
    df.to_excel(excel_file, index=False)

if __name__ == "__main__":
    input_file = "tiktok_results.json"
    output_file = "cleaned_tiktok_results_0520.json"
    clean_email_data(input_file, output_file)
    # JSON 데이터를 엑셀로 변환
    json_to_excel(output_file, "cleaned_tiktok_results_0520.xlsx")