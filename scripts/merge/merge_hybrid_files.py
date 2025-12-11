#!/usr/bin/env python3
"""
새로운 hybrid CSV 파일들을 all_profiles_with_followers_hybrid.csv에 합치기
중복 크리에이터 제거
"""

import pandas as pd
import os
from pathlib import Path

def merge_hybrid_files():
    """새로운 hybrid 파일들을 메인 파일에 합치기"""

    # 파일 경로 설정 (프로젝트 루트 기준)
    # scripts/merge/merge_hybrid_files.py -> 2단계 위가 프로젝트 루트
    base_dir = Path(__file__).resolve().parent.parent.parent
    results_dir = base_dir / 'results'

    # 이미 처리된 파일들 (이전 실행에서 이미 합쳐진 파일들)
    already_processed = {
        'crueltyfreebeauty_hybrid.csv',
        'cleanmakeupproducts_hybrid.csv',
        'sustainableskincare_hybrid.csv',
        'vegancosmetics_hybrid.csv'
    }

    # results 폴더에서 모든 hybrid 파일들을 찾기
    hybrid_files = []
    for file_path in results_dir.glob('*_hybrid.csv'):
        file_name = file_path.name
        if file_name not in already_processed and file_name != 'all_profiles_with_followers_hybrid.csv':
            hybrid_files.append(file_name)

    hybrid_files.sort()  # 알파벳순으로 정렬
    print(f"📋 찾은 hybrid 파일들 ({len(hybrid_files)}개):")
    for file in hybrid_files:
        print(f"   - {file}")

    # 합칠 파일들
    new_files = hybrid_files

    main_file = results_dir / 'all_profiles_with_followers_hybrid.csv'

    print("🚀 파일 합치기 시작")
    print("=" * 60)

    # 메인 파일 로드
    print(f"📂 메인 파일 로드: {main_file}")
    main_df = pd.read_csv(main_file)
    print(f"   메인 파일 크기: {len(main_df):,}개 행")

    # 새로운 파일들 로드 및 병합
    all_new_data = []

    for file_name in new_files:
        file_path = results_dir / file_name

        if not file_path.exists():
            print(f"   ⚠️  파일 없음: {file_name}")
            continue

        print(f"📂 파일 로드: {file_name}")
        df = pd.read_csv(file_path)

        print(f"   크기: {len(df):,}개 행")
        print(f"   컬럼: {list(df.columns)}")

        # 메인 파일 구조에 맞게 컬럼 조정
        # 누락된 컬럼들 추가 (기본값 설정)
        for col in main_df.columns:
            if col not in df.columns:
                if col in ['creator_nickname', 'creator_email', 'follower_count', 'following_count',
                          'video_count', 'heart_count', 'create_time', 'source_api',
                          'creator_email_normalized', 'creator_username_normalized']:
                    df[col] = ''  # 문자열 컬럼
                elif col in ['following_count', 'video_count', 'heart_count']:
                    df[col] = 0   # 숫자 컬럼
                elif col == 'create_time':
                    df[col] = 0   # 숫자 컬럼

        # 메인 파일에는 없는 컬럼들 제거
        for col in df.columns:
            if col not in main_df.columns:
                df = df.drop(columns=[col])
                print(f"   🗑️  컬럼 제거: {col}")

        # 컬럼 순서 재정렬
        df = df[main_df.columns]

        all_new_data.append(df)
        print(f"   ✅ 처리 완료: {file_name}")

    if not all_new_data:
        print("❌ 처리할 새로운 파일이 없습니다.")
        return

    # 모든 새로운 데이터 합치기
    print("\n🔄 새로운 데이터 합치기")
    new_combined_df = pd.concat(all_new_data, ignore_index=True)
    print(f"   합친 데이터 크기: {len(new_combined_df):,}개 행")

    # 메인 파일과 합치기
    print("\n🔄 메인 파일과 합치기")
    combined_df = pd.concat([main_df, new_combined_df], ignore_index=True)
    print(f"   합치기 후 크기: {len(combined_df):,}개 행")

    # 중복 제거 (creator_id 기준, 첫 번째 발생만 유지)
    print("\n🔍 중복 제거 중 (creator_id 기준)...")
    before_dedup = len(combined_df)

    # creator_id가 같은 행들 중에서 먼저 나타난 것만 유지
    combined_df = combined_df.drop_duplicates(subset=['creator_id'], keep='first')

    after_dedup = len(combined_df)
    removed_duplicates = before_dedup - after_dedup

    print(f"   중복 제거 완료: {removed_duplicates:,}개 행 제거")
    print(f"   최종 크기: {len(combined_df):,}개 행")

    # 결과 저장
    output_file = results_dir / 'all_profiles_with_followers_hybrid.csv'
    print(f"\n💾 결과 저장: {output_file}")

    combined_df.to_csv(output_file, index=False, encoding='utf-8-sig')
    file_size = output_file.stat().st_size / 1024  # KB
    print(f"   파일 크기: {file_size:.1f} KB")

    # 병합이 완료된 하이브리드 파일 삭제 (데이터 중복 방지)
    if new_files:
        print("\n🧹 병합된 하이브리드 파일 정리 중...")
        for file_name in new_files:
            file_path = results_dir / file_name
            try:
                file_path.unlink()
                print(f"   🗑️  삭제 완료: {file_name}")
            except FileNotFoundError:
                print(f"   ⚠️  이미 삭제되었거나 찾을 수 없음: {file_name}")
            except Exception as exc:
                print(f"   ⚠️  삭제 실패 ({file_name}): {exc}")

    # 통계 출력
    print("\n" + "=" * 60)
    print("✅ 완료!")
    print("=" * 60)
    print("\n📊 통계:")
    print(f"   메인 파일 원본: {len(main_df):,}개 행")
    print(f"   새로운 데이터 추가: {len(new_combined_df):,}개 행")
    print(f"   중복 제거: {removed_duplicates:,}개 행")
    print(f"   최종 결과: {len(combined_df):,}개 행")

    # 키워드별 통계
    keyword_counts = combined_df['keyword'].value_counts()
    print("\n🏷️  키워드별 분포:")
    for keyword, count in keyword_counts.head(10).items():
        print(f"   {keyword}: {count:,}개")

    print(f"\n💾 저장 완료: {output_file}")

if __name__ == '__main__':
    merge_hybrid_files()
