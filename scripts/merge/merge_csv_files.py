#!/usr/bin/env python3
"""
CSV 파일들을 병합하는 스크립트
all_profiles_with_followers_and_emails.csv의 email_checked 정보를
all_profiles_with_followers_hybrid.csv에 추가
"""

import csv
import os
from pathlib import Path

def merge_csv_files():
    """두 CSV 파일을 병합"""
    results_dir = Path("results")
    emails_file = results_dir / "all_profiles_with_followers_and_emails.csv"
    hybrid_file = results_dir / "all_profiles_with_followers_hybrid.csv"
    output_file = results_dir / "all_profiles_with_followers_and_emails_hybrid.csv"

    print("📊 CSV 파일 병합 시작...")

    # 파일 존재 확인
    if not emails_file.exists():
        print(f"❌ {emails_file} 파일이 존재하지 않습니다.")
        return

    if not hybrid_file.exists():
        print(f"❌ {hybrid_file} 파일이 존재하지 않습니다.")
        return

    # email_checked 정보를 담을 딕셔너리 (video_id -> email_checked)
    email_checked_map = {}

    print("📖 이메일 파일에서 email_checked 정보 로드 중...")
    with open(emails_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            video_id = row['video_id']
            email_checked = row.get('email_checked', '')
            email_checked_map[video_id] = email_checked

    print(f"✅ {len(email_checked_map)}개의 video_id에서 email_checked 정보 로드 완료")

    # 결과 파일 작성
    print("📝 병합된 파일 작성 중...")
    with open(hybrid_file, 'r', encoding='utf-8') as hybrid_f:
        with open(output_file, 'w', encoding='utf-8', newline='') as output_f:
            reader = csv.reader(hybrid_f)
            writer = csv.writer(output_f)

            # 헤더 처리 (email_checked 컬럼 추가)
            header = next(reader)
            header.append('email_checked')
            writer.writerow(header)

            # 데이터 행 처리
            rows_written = 0
            for row in reader:
                video_id = row[1]  # video_id는 두 번째 컬럼

                # email_checked 정보 추가
                email_checked = email_checked_map.get(video_id, '')

                # email_checked 정보가 있는 경우 업데이트
                if email_checked:
                    print(f"✨ video_id {video_id}에 email_checked 정보 추가: {email_checked}")

                row.append(email_checked)
                writer.writerow(row)
                rows_written += 1

    print(f"✅ 병합 완료! 총 {rows_written}개의 행이 처리되었습니다.")
    print(f"📁 결과 파일: {output_file}")

    # 통계 정보
    print("📊 통계 정보:")
    print(f"   - 이메일 체크 정보 추가됨: {len([v for v in email_checked_map.values() if v])}개")
    print(f"   - 총 처리된 행 수: {rows_written}개")

if __name__ == "__main__":
    merge_csv_files()
