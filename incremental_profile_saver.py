#!/usr/bin/env python3
"""
증분 프로필 저장 스크립트

새로운 프로필 데이터를 버전 관리하면서 증분 저장합니다.
- 이전 버전에 없는 새로운 프로필만 추출
- 버전 번호 자동 증가 (ver1 → ver2 → ver3...)
- 이메일이 있는 프로필만 필터링하여 별도 저장
"""

import pandas as pd
import glob
import os
from pathlib import Path
from typing import Tuple, Optional
import logging

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def find_latest_version(base_path: str, filename_pattern: str) -> int:
    """
    기존 버전 파일들을 검색하여 최신 버전 번호를 찾습니다.

    Args:
        base_path: 검색할 디렉토리 경로
        filename_pattern: 파일명 패턴 (예: 'all_profiles_with_followers_and_emails_ver*_filtered.csv')

    Returns:
        int: 최신 버전 번호 (파일이 없으면 0 반환)
    """
    pattern = os.path.join(base_path, filename_pattern)
    existing_files = glob.glob(pattern)

    if not existing_files:
        logger.info(f"기존 버전 파일을 찾을 수 없습니다: {pattern}")
        return 0

    # 파일명에서 버전 번호 추출
    versions = []
    for file_path in existing_files:
        filename = os.path.basename(file_path)
        # 'ver' 다음의 숫자 추출
        try:
            # 예: all_profiles_with_followers_and_emails_ver1_filtered.csv -> 1
            ver_part = filename.split('ver')[1].split('_')[0].split('.')[0]
            versions.append(int(ver_part))
        except (IndexError, ValueError) as e:
            logger.warning(f"버전 번호 파싱 실패: {filename} - {e}")
            continue

    if not versions:
        return 0

    latest_version = max(versions)
    logger.info(f"최신 버전: ver{latest_version}")
    return latest_version


def load_previous_profiles(previous_file: str) -> set:
    """
    이전 버전 파일에서 creator_id 목록을 로드합니다.

    Args:
        previous_file: 이전 버전 파일 경로

    Returns:
        set: creator_id 집합
    """
    if not os.path.exists(previous_file):
        logger.warning(f"이전 파일을 찾을 수 없습니다: {previous_file}")
        return set()

    try:
        df = pd.read_csv(previous_file)
        if 'creator_id' not in df.columns:
            logger.error(f"'creator_id' 컬럼을 찾을 수 없습니다: {previous_file}")
            return set()

        # creator_id를 문자열로 변환하여 저장
        previous_ids = set(df['creator_id'].astype(str))
        logger.info(f"이전 버전에서 {len(previous_ids)}개의 프로필 ID 로드됨")
        return previous_ids

    except Exception as e:
        logger.error(f"파일 로드 중 오류 발생: {previous_file} - {e}")
        return set()


def find_new_profiles(
    source_file: str,
    previous_ids: set
) -> Tuple[pd.DataFrame, int, int]:
    """
    소스 파일에서 이전 버전에 없는 새로운 프로필을 찾습니다.

    Args:
        source_file: 전체 프로필 데이터 파일 경로
        previous_ids: 이전 버전의 creator_id 집합

    Returns:
        Tuple[pd.DataFrame, int, int]: (새로운 프로필 DataFrame, 전체 개수, 새로운 개수)
    """
    if not os.path.exists(source_file):
        raise FileNotFoundError(f"소스 파일을 찾을 수 없습니다: {source_file}")

    df = pd.read_csv(source_file)
    total_count = len(df)

    if 'creator_id' not in df.columns:
        raise ValueError(f"'creator_id' 컬럼을 찾을 수 없습니다: {source_file}")

    # creator_id를 문자열로 변환
    df['creator_id'] = df['creator_id'].astype(str)

    # 새로운 프로필만 필터링
    if previous_ids:
        new_profiles = df[~df['creator_id'].isin(previous_ids)]
    else:
        # 이전 버전이 없으면 모든 프로필이 새로운 것
        new_profiles = df

    new_count = len(new_profiles)
    logger.info(f"전체 프로필: {total_count}개, 새로운 프로필: {new_count}개")

    return new_profiles, total_count, new_count


def filter_profiles_with_email(df: pd.DataFrame) -> Tuple[pd.DataFrame, int]:
    """
    이메일이 있는 프로필만 필터링합니다.

    Args:
        df: 프로필 DataFrame

    Returns:
        Tuple[pd.DataFrame, int]: (필터링된 DataFrame, 개수)
    """
    if 'creator_email' not in df.columns:
        logger.warning("'creator_email' 컬럼을 찾을 수 없습니다")
        return df, len(df)

    # 이메일이 있는 행만 선택 (NaN이 아니고 빈 문자열이 아닌 것)
    filtered_df = df[
        df['creator_email'].notna() &
        (df['creator_email'].astype(str).str.strip() != '')
    ]

    count = len(filtered_df)
    logger.info(f"이메일이 있는 프로필: {count}개")

    return filtered_df, count


def save_incremental_profiles(
    source_file: str,
    base_path: str,
    base_filename: str = 'all_profiles_with_followers_and_emails',
    force_version: Optional[int] = None
) -> dict:
    """
    새로운 프로필을 증분 저장합니다.

    Args:
        source_file: 전체 프로필 데이터 파일 경로
        base_path: 저장할 디렉토리 경로
        base_filename: 기본 파일명
        force_version: 강제로 지정할 버전 번호 (None이면 자동 증가)

    Returns:
        dict: 작업 결과 통계
    """
    logger.info("=" * 60)
    logger.info("증분 프로필 저장 시작")
    logger.info("=" * 60)

    # 1. 최신 버전 찾기
    if force_version is not None:
        latest_version = force_version - 1
        logger.info(f"강제 버전 지정: ver{force_version}")
    else:
        latest_version = find_latest_version(
            base_path,
            f'{base_filename}_ver*_filtered.csv'
        )

    new_version = latest_version + 1
    logger.info(f"새 버전: ver{new_version}")

    # 2. 이전 모든 버전의 프로필 ID 로드 (중복 방지)
    previous_ids = set()
    for version in range(1, latest_version + 1):
        version_file = os.path.join(
            base_path,
            f'{base_filename}_ver{version}_filtered.csv'
        )
        version_ids = load_previous_profiles(version_file)
        previous_ids.update(version_ids)

    logger.info(f"이전 모든 버전(ver1~ver{latest_version})에서 총 {len(previous_ids):,}개의 프로필 ID 로드됨")

    # 3. 새로운 프로필 찾기
    new_profiles, total_count, new_count = find_new_profiles(
        source_file,
        previous_ids
    )

    # 4. 새 버전 파일 저장 (전체)
    new_version_file = os.path.join(
        base_path,
        f'{base_filename}_ver{new_version}.csv'
    )
    new_profiles.to_csv(new_version_file, index=False, encoding='utf-8-sig')
    logger.info(f"✓ 저장 완료: {new_version_file} ({new_count}개)")

    # 5. 이메일이 있는 프로필만 필터링하여 저장
    filtered_profiles, filtered_count = filter_profiles_with_email(new_profiles)

    filtered_version_file = os.path.join(
        base_path,
        f'{base_filename}_ver{new_version}_filtered.csv'
    )
    filtered_profiles.to_csv(filtered_version_file, index=False, encoding='utf-8-sig')
    logger.info(f"✓ 저장 완료: {filtered_version_file} ({filtered_count}개)")

    # 6. 결과 통계
    results = {
        'version': new_version,
        'previous_version': latest_version,
        'source_file': source_file,
        'total_profiles': total_count,
        'new_profiles': new_count,
        'new_with_email': filtered_count,
        'email_ratio': f"{filtered_count / new_count * 100:.1f}%" if new_count > 0 else "0%",
        'saved_files': {
            'all': new_version_file,
            'filtered': filtered_version_file
        }
    }

    logger.info("=" * 60)
    logger.info("작업 완료 요약")
    logger.info("=" * 60)
    logger.info(f"버전: ver{latest_version} → ver{new_version}")
    logger.info(f"소스 파일: {source_file}")
    logger.info(f"전체 프로필: {total_count}개")
    logger.info(f"새로운 프로필: {new_count}개")
    logger.info(f"이메일 있음: {filtered_count}개 ({results['email_ratio']})")
    logger.info(f"\n저장된 파일:")
    logger.info(f"  • {new_version_file}")
    logger.info(f"  • {filtered_version_file}")
    logger.info("=" * 60)

    return results


def main():
    """
    메인 실행 함수
    """
    import argparse

    parser = argparse.ArgumentParser(
        description='TikTok 프로필 증분 저장 스크립트'
    )
    parser.add_argument(
        '--source',
        default='results/all_profiles_with_followers_and_emails.csv',
        help='소스 파일 경로 (기본값: results/all_profiles_with_followers_and_emails.csv)'
    )
    parser.add_argument(
        '--output-dir',
        default='.',
        help='출력 디렉토리 (기본값: 현재 디렉토리)'
    )
    parser.add_argument(
        '--base-filename',
        default='all_profiles_with_followers_and_emails',
        help='기본 파일명 (기본값: all_profiles_with_followers_and_emails)'
    )
    parser.add_argument(
        '--version',
        type=int,
        help='강제로 지정할 버전 번호'
    )

    args = parser.parse_args()

    # 경로 확인
    script_dir = os.path.dirname(os.path.abspath(__file__))
    source_file = os.path.join(script_dir, args.source)
    output_dir = os.path.join(script_dir, args.output_dir)

    try:
        results = save_incremental_profiles(
            source_file=source_file,
            base_path=output_dir,
            base_filename=args.base_filename,
            force_version=args.version
        )

        return results

    except Exception as e:
        logger.error(f"오류 발생: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == '__main__':
    main()
