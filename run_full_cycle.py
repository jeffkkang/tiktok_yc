#!/usr/bin/env python3
"""전체 TikTok 하이브리드 → 병합 → 팔로워/이메일 보강 워크플로우 실행기"""

import argparse
import logging
import sys
from pathlib import Path

from keywords.analyze_unanalyzed_keywords import KeywordAnalyzer
from merge_hybrid_files import merge_hybrid_files
from enrich_follower_counts import enrich_csv_with_followers
from incremental_profile_saver import save_incremental_profiles


def configure_logging(level: str = "INFO") -> None:
    """간단한 콘솔 로깅 설정"""
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )


def run_full_cycle(args: argparse.Namespace) -> None:
    """전체 파이프라인을 순차적으로 실행"""
    repo_root = Path(__file__).resolve().parent
    logger = logging.getLogger("workflow")

    logger.info("🚀 전체 워크플로우 시작")

    analyzer = KeywordAnalyzer(base_dir=str(repo_root))
    selected_keywords = analyzer.select_keywords(
        method=args.method,
        count=args.keyword_count,
        priority_keywords=args.priority,
    )

    if not selected_keywords:
        logger.warning("선택된 키워드가 없어 작업을 종료합니다.")
        return

    logger.info("🎯 선택된 키워드 (%d개): %s", len(selected_keywords), ", ".join(selected_keywords))

    if args.select_only:
        logger.info("--select-only 옵션으로 키워드 선택까지만 수행했습니다.")
        return

    logger.info("🔄 하이브리드 스크래퍼 실행 (limit=%d, browser=%s)", args.limit, args.use_browser)
    scrape_results = analyzer.analyze_selected_keywords(
        keywords=selected_keywords,
        limit=args.limit,
        use_browser=args.use_browser,
    )

    success_count = sum(scrape_results.values())
    logger.info("📊 하이브리드 결과: %d/%d 성공", success_count, len(scrape_results))

    if args.skip_merge and args.skip_enrich:
        logger.info("합치기/보강 단계가 모두 건너뛰기로 설정되어 워크플로우를 종료합니다.")
        return

    if not args.skip_merge:
        logger.info("🧩 hybrid 결과 병합 실행")
        merge_hybrid_files()
    else:
        logger.info("merge_hybrid_files 단계는 건너뜁니다 (--skip-merge)")

    if args.skip_enrich:
        logger.info("enrich_follower_counts 단계는 건너뜁니다 (--skip-enrich)")
        return

    logger.info("📈 팔로워/이메일 보강 실행 (workers=%d, checkpoint=%d)", args.max_workers, args.checkpoint)
    input_file = repo_root / "results" / "all_profiles_with_followers_hybrid.csv"
    output_file = repo_root / "results" / "all_profiles_with_followers_and_emails.csv"

    enrich_csv_with_followers(
        input_file=input_file,
        output_file=output_file,
        max_workers=args.max_workers,
        checkpoint_interval=args.checkpoint,
    )

    if args.skip_incremental:
        logger.info("증분 저장 단계는 건너뜁니다 (--skip-incremental)")
    else:
        logger.info("💾 증분 프로필 저장 실행 (새 프로필만 버전별 저장)")
        try:
            results = save_incremental_profiles(
                source_file=str(output_file),
                base_path=str(repo_root),
                base_filename='all_profiles_with_followers_and_emails'
            )
            logger.info(
                "✓ 증분 저장 완료: ver%d (새 프로필 %d개, 이메일 %d개)",
                results['version'],
                results['new_profiles'],
                results['new_with_email']
            )
        except Exception as e:
            logger.error("증분 저장 중 오류 발생: %s", e)

    logger.info("🎉 전체 워크플로우 완료")


def build_arg_parser() -> argparse.ArgumentParser:
    """CLI 인자 파서 생성"""
    parser = argparse.ArgumentParser(description="하이브리드 → 병합 → 보강 전체 파이프라인 실행")
    parser.add_argument("-c", "--keyword-count", type=int, default=200, help="선택할 키워드 개수")
    parser.add_argument("-l", "--limit", type=int, default=200, help="하이브리드 스크래핑 수집 개수")
    parser.add_argument("-m", "--method", choices=["random", "priority", "all"], default="random", help="키워드 선택 방식")
    parser.add_argument("--priority", nargs="*", help="우선순위 키워드 목록")
    parser.add_argument("--headless", action="store_true", help="브라우저 대신 헤드리스 모드로 실행")
    parser.add_argument("--select-only", action="store_true", help="키워드 선정까지만 수행하고 종료")
    parser.add_argument("--skip-merge", action="store_true", help="merge_hybrid_files 단계를 건너뜀")
    parser.add_argument("--skip-enrich", action="store_true", help="enrich_follower_counts 단계를 건너뜀")
    parser.add_argument("--skip-incremental", action="store_true", help="증분 프로필 저장 단계를 건너뜀")
    parser.add_argument("--max-workers", type=int, default=3, help="enrich_follower_counts 병렬 워커 수")
    parser.add_argument("--checkpoint", type=int, default=50, help="enrich 중간 저장 간격")
    parser.add_argument("--log-level", default="INFO", help="로깅 레벨 (DEBUG/INFO/WARNING/ERROR)")
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    args.use_browser = not args.headless

    configure_logging(args.log_level)

    try:
        run_full_cycle(args)
    except KeyboardInterrupt:
        logging.getLogger("workflow").warning("사용자에 의해 중단되었습니다.")
    except Exception:
        logging.getLogger("workflow").exception("워크플로우 실행 중 예기치 않은 오류 발생")


if __name__ == "__main__":
    main()
