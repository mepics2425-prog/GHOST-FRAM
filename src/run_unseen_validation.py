from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
ACTIVE_JSON = RAW_DIR / "aetheria-all.json"

PIPELINE = [
    "inspect_logs.py",
    "eda_baseline_v2.py",
    "transaction_network.py",
    "behavior_sync.py",
    "cars_v1.py",
]

ANALYSIS_FILES = [
    "baseline_v2_account_scores.csv",
    "baseline_v2_metrics.csv",
    "baseline_v2_general_false_positives.csv",
    "baseline_v2_organized_false_positives.csv",
    "network_edges.csv",
    "network_account_metrics.csv",
    "ghost_motif_candidates_v1.csv",
    "network_role_evaluation.csv",
    "behavior_pair_sync.csv",
    "behavior_account_sync.csv",
    "behavior_sync_type_summary.csv",
    "cars_v1_account_scores.csv",
    "cars_v1_metrics.csv",
    "cars_v1_false_positives.csv",
    "cars_v1_false_negatives.csv",
]

PROCESSED_FILES = [
    "account_features_v1.csv",
    "action_type_counts.csv",
    "transaction_edges.csv",
    "suspicious_price_transactions.csv",
]


def run_script(script_name: str):
    script_path = PROJECT_ROOT / "src" / script_name
    if not script_path.exists():
        raise FileNotFoundError(f"필수 스크립트 없음: {script_path}")

    print("\n" + "#" * 88)
    print(f"RUN: {script_name}")
    print("#" * 88)

    result = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=PROJECT_ROOT,
        check=False,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"{script_name} 실행 실패 (exit code={result.returncode})"
        )


def copy_if_exists(src: Path, dst: Path):
    if src.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def main():
    parser = argparse.ArgumentParser(
        description="GHOST FARM unseen snapshot validation runner"
    )
    parser.add_argument(
        "--input",
        required=True,
        help="검증할 aetheria-all JSON 파일 경로",
    )
    parser.add_argument(
        "--label",
        required=True,
        help="검증 결과 폴더 이름. 예: unseen_01",
    )
    args = parser.parse_args()

    input_json = Path(args.input).resolve()
    if not input_json.exists():
        raise FileNotFoundError(f"입력 JSON 없음: {input_json}")

    RAW_DIR.mkdir(parents=True, exist_ok=True)

    backup_path = None
    if ACTIVE_JSON.exists():
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = RAW_DIR / f"_backup_aetheria-all_{stamp}.json"
        shutil.copy2(ACTIVE_JSON, backup_path)
        print(f"[BACKUP] 기존 active JSON → {backup_path}")

    print(f"[INPUT] {input_json}")
    shutil.copy2(input_json, ACTIVE_JSON)
    print(f"[ACTIVE] {ACTIVE_JSON}")

    try:
        for script in PIPELINE:
            run_script(script)

        validation_dir = PROJECT_ROOT / "data" / "validation" / args.label
        processed_dir = validation_dir / "processed"
        analysis_dir = validation_dir / "analysis"
        figures_dir = analysis_dir / "figures"

        validation_dir.mkdir(parents=True, exist_ok=True)

        copy_if_exists(
            input_json,
            validation_dir / input_json.name,
        )

        for name in PROCESSED_FILES:
            copy_if_exists(
                PROJECT_ROOT / "data" / "processed" / name,
                processed_dir / name,
            )

        for name in ANALYSIS_FILES:
            copy_if_exists(
                PROJECT_ROOT / "data" / "analysis" / name,
                analysis_dir / name,
            )

        src_figures = PROJECT_ROOT / "data" / "analysis" / "figures"
        if src_figures.exists():
            figures_dir.mkdir(parents=True, exist_ok=True)
            for path in src_figures.iterdir():
                if path.is_file():
                    shutil.copy2(path, figures_dir / path.name)

        print("\n" + "=" * 88)
        print("VALIDATION COMPLETE")
        print("=" * 88)
        print(f"결과 저장 위치: {validation_dir}")
        print("")
        print("핵심 확인 파일:")
        print(f"- {analysis_dir / 'baseline_v2_metrics.csv'}")
        print(f"- {analysis_dir / 'network_role_evaluation.csv'}")
        print(f"- {analysis_dir / 'cars_v1_metrics.csv'}")
        print(f"- {analysis_dir / 'cars_v1_false_positives.csv'}")
        print(f"- {analysis_dir / 'cars_v1_false_negatives.csv'}")
        print("=" * 88)

    finally:
        if backup_path and backup_path.exists():
            shutil.copy2(backup_path, ACTIVE_JSON)
            print(f"\n[RESTORE] 기존 active JSON 복원 → {ACTIVE_JSON}")


if __name__ == "__main__":
    main()
