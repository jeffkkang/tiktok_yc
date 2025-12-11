import pandas as pd
import os
from pathlib import Path

def filter_rows_with_emails(input_file, output_file):
    """
    CSV 파일에서 이메일이 있는 행들만 필터링하여 새 파일로 저장

    Args:
        input_file (str): 입력 CSV 파일 경로
        output_file (str): 출력 CSV 파일 경로
    """

    # CSV 파일 읽기 (메모리 효율을 위해 청크 단위로 읽기)
    print(f"입력 파일 읽는 중: {input_file}")

    # 파일 크기가 크므로 청크 단위로 처리
    chunks = []
    chunk_size = 10000

    for chunk in pd.read_csv(input_file, chunksize=chunk_size, low_memory=False):
        # 이메일이 있는 행들만 필터링
        # creator_email 컬럼이 비어있지 않은 행들만 선택
        filtered_chunk = chunk[chunk['creator_email'].notna() & (chunk['creator_email'] != '')]
        chunks.append(filtered_chunk)

    # 모든 청크를 합치기
    filtered_df = pd.concat(chunks, ignore_index=True)

    print(f"전체 행 수: {len(pd.read_csv(input_file, low_memory=False))}")
    print(f"이메일이 있는 행 수: {len(filtered_df)}")
    print(f"제거된 행 수: {len(pd.read_csv(input_file, low_memory=False)) - len(filtered_df)}")

    # 결과 저장
    filtered_df.to_csv(output_file, index=False)
    print(f"필터링된 데이터 저장 완료: {output_file}")

    return len(filtered_df)

if __name__ == "__main__":
    # 입력 파일 경로
    base_dir = Path(__file__).resolve().parent
    input_file = str(base_dir / "all_profiles_with_followers_and_emails_ver1.csv")

    # 출력 파일 경로 (원본 파일명에 _filtered 추가)
    file_name, file_ext = os.path.splitext(input_file)
    output_file = f"{file_name}_filtered{file_ext}"

    # 필터링 실행
    filtered_count = filter_rows_with_emails(input_file, output_file)

    print("\n처리 완료!")
    print(f"총 {filtered_count}개의 이메일이 있는 행이 추출되었습니다.")
    print(f"출력 파일: {output_file}")
