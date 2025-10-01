#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
import re
import sys
import datetime

def parse_cookie_string(cookie_string):
    """브라우저에서 복사한 쿠키 문자열을 파싱"""
    cookies = []
    lines = cookie_string.strip().split('\n')
    
    for line in lines:
        if not line.strip():
            continue
            
        parts = line.strip().split('\t')
        if len(parts) >= 3:  # 최소한 이름, 값, 도메인이 있어야 함
            name = parts[0].strip()
            value = parts[1].strip()
            domain = parts[2].strip()
            
            # 유효한 쿠키만 추가
            if name and value and domain and name != "name" and domain.startswith('.tiktok.com'):
                cookies.append({
                    "name": name,
                    "value": value,
                    "domain": domain
                })
    
    return cookies

def update_cookies(cookie_string):
    """쿠키 파일 업데이트"""
    cookies = parse_cookie_string(cookie_string)
    
    if not cookies:
        print("⚠️ 유효한 쿠키를 찾을 수 없습니다.")
        return False
    
    # 필수 쿠키 확인
    essential_cookies = ["sessionid", "ttwid", "msToken"]
    found_essentials = [cookie["name"] for cookie in cookies if cookie["name"] in essential_cookies]
    
    missing = [cookie for cookie in essential_cookies if cookie not in found_essentials]
    if missing:
        print(f"⚠️ 필수 쿠키가 누락되었습니다: {', '.join(missing)}")
        answer = input("계속 진행하시겠습니까? (y/n): ")
        if answer.lower() != 'y':
            return False
    
    # 기존 파일 백업
    if os.path.exists('cookies.json'):
        with open('cookies.json', 'r') as f:
            try:
                old_cookies = json.load(f)
                backup_file = f'cookies_backup_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
                with open(backup_file, 'w') as bf:
                    json.dump(old_cookies, bf, indent=2)
                print(f"✅ 기존 쿠키 백업 완료: {backup_file}")
            except json.JSONDecodeError:
                print("⚠️ 기존 쿠키 파일이 손상되었습니다. 백업하지 않고 진행합니다.")
    
    # 새 쿠키 저장
    with open('cookies.json', 'w') as f:
        json.dump(cookies, f, indent=2)
    
    # 쿠키 상세 정보 출력
    lines = cookie_string.strip().split('\n')
    expiry_dates = []
    for cookie in cookies:
        if cookie["name"] == "sessionid" or cookie["name"] == "sid_guard":
            # 만료일 추출
            for line in lines:
                if cookie["name"] in line and "20" in line:  # 년도가 포함된 날짜 형식 찾기
                    date_match = re.search(r'(\d{4}-\d{2}-\d{2})', line)
                    if date_match:
                        expiry_dates.append(date_match.group(1))
                        break
    
    if expiry_dates:
        expiry_date = max(expiry_dates)
        print(f"📅 쿠키 만료일: {expiry_date}")
        today = datetime.datetime.now()
        expiry = datetime.datetime.strptime(expiry_date, "%Y-%m-%d")
        days_left = (expiry - today).days
        print(f"📊 만료까지 남은 기간: {days_left}일")
    
    print(f"✅ 총 {len(cookies)}개 쿠키 업데이트 완료")
    
    # 로컬 스토리지 업데이트 확인
    if "SLARDARtiktok_webapp" in cookie_string or "__tea_cache_tokens_1988" in cookie_string:
        print("\n🔄 로컬 스토리지 정보도 발견되었습니다. 업데이트하시겠습니까?")
        answer = input("로컬 스토리지도 업데이트하시겠습니까? (y/n): ")
        if answer.lower() == 'y':
            update_local_storage(cookie_string)
    
    return True

def update_local_storage(storage_string):
    """로컬 스토리지 업데이트"""
    storage_items = {}
    important_keys = [
        "SLARDARtiktok_webapp",
        "SLARDARtiktok_webapp_login",
        "__tea_cache_tokens_1988"
    ]
    
    lines = storage_string.strip().split('\n')
    for line in lines:
        for key in important_keys:
            if key in line:
                parts = line.split('\t')
                if len(parts) >= 2:
                    storage_items[key] = parts[1].strip()
    
    if not storage_items:
        print("⚠️ 유효한 로컬 스토리지 항목을 찾을 수 없습니다.")
        return False
    
    # 기존 파일 백업
    if os.path.exists('local_storage.json'):
        with open('local_storage.json', 'r') as f:
            try:
                old_storage = json.load(f)
                backup_file = f'local_storage_backup_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
                with open(backup_file, 'w') as bf:
                    json.dump(old_storage, bf, indent=2)
                print(f"✅ 기존 로컬 스토리지 백업 완료: {backup_file}")
            except json.JSONDecodeError:
                print("⚠️ 기존 로컬 스토리지 파일이 손상되었습니다. 백업하지 않고 진행합니다.")
    
    # 기존 파일에서 누락된 항목 유지
    if os.path.exists('local_storage.json'):
        with open('local_storage.json', 'r') as f:
            try:
                existing_storage = json.load(f)
                for key, value in existing_storage.items():
                    if key not in storage_items:
                        storage_items[key] = value
            except json.JSONDecodeError:
                pass
    
    # 새 로컬 스토리지 저장
    with open('local_storage.json', 'w') as f:
        json.dump(storage_items, f, indent=2)
    
    print(f"✅ 총 {len(storage_items)}개 로컬 스토리지 항목 업데이트 완료")
    return True

if __name__ == "__main__":
    print("\n=== 틱톡 쿠키 업데이트 도구 ===\n")
    print("브라우저에서 복사한 쿠키를 붙여넣으세요. 입력을 마치려면 빈 줄에서 Ctrl+D (Unix/Mac) 또는 Ctrl+Z (Windows)를 누르세요.")
    print("붙여넣기 시작 ↓\n")
    
    cookie_lines = []
    try:
        while True:
            line = input()
            cookie_lines.append(line)
    except (EOFError, KeyboardInterrupt):
        cookie_string = '\n'.join(cookie_lines)
        print("\n붙여넣기 완료 ↑\n")
        
        if update_cookies(cookie_string):
            print("\n✅ 쿠키가 성공적으로 업데이트되었습니다.")
            print("✨ 이제 main.py 또는 advanced_scraper.py를 실행하여 스크래핑을 진행할 수 있습니다.")
        else:
            print("\n❌ 쿠키 업데이트에 실패했습니다.")
    
    print("\n=== 처리 완료 ===")