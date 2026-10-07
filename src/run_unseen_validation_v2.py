from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
ACTIVE_JSON = RAW_DIR / "aetheria-all.json"

PIPELINE = [
    "inspect_logs.py",
    "eda_baseline_v2.py",
    "transaction_network.py",
    "behavior_sync.py",
    "cars_v2.py",
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
    "cars_v2_account_scores.csv",
    "cars_v2_metrics.csv",
    "cars_v2_false_positives.csv",
    "cars_v2_false_negatives.csv",
]

PROCESSED_FILES = [
    "account_features_v1.csv",
    "action_type_counts.csv",
    "transaction_edges.csv",
    "suspicious_price_transactions.csv",
]


def run_script(name: str):
    path = ROOT / "src" / name
    if not path.exists():
        raise FileNotFoundError(f"필수 스크립트 없음: {path}")

    print("\n" + "#" * 88)
    print(f"RUN: {name}")
    print("#" * 88)

    result = subprocess.run(
        [sys.executable, str(path)],
        cwd=ROOT,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"{name} 실행 실패 (exit code={result.returncode})")


def copy_if_exists(src: Path, dst: Path):
    if src.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def main():
    parser = argparse.ArgumentParser(
        description="GHOST FARM unseen validation runner for frozen CARS V2"
    )
    parser.add_argument("--input", required=True)
    parser.add_argument("--label", required=True)
    args = parser.parse_args()

    input_json = Path(args.input).resolve()
    if not input_json.exists():
        raise FileNotFoundError(f"입력 JSON 없음: {input_json}")

    RAW_DIR.mkdir(parents=True, exist_ok=True)

    backup = None
    if ACTIVE_JSON.exists():
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = RAW_DIR / f"_backup_aetheria-all_{stamp}.json"
        shutil.copy2(ACTIVE_JSON, backup)
        print(f"[BACKUP] {backup}")

    shutil.copy2(input_json, ACTIVE_JSON)
    print(f"[INPUT]  {input_json}")
    print(f"[ACTIVE] {ACTIVE_JSON}")

    try:
        for script in PIPELINE:
            run_script(script)

        val_dir = ROOT / "data" / "validation" / args.label
        p_dir = val_dir / "processed"
        a_dir = val_dir / "analysis"
        f_dir = a_dir / "figures"

        val_dir.mkdir(parents=True, exist_ok=True)
        copy_if_exists(input_json, val_dir / input_json.name)

        for name in PROCESSED_FILES:
            copy_if_exists(ROOT / "data" / "processed" / name, p_dir / name)

        for name in ANALYSIS_FILES:
            copy_if_exists(ROOT / "data" / "analysis" / name, a_dir / name)

        src_fig = ROOT / "data" / "analysis" / "figures"
        if src_fig.exists():
            for p in src_fig.iterdir():
                if p.is_file():
                    copy_if_exists(p, f_dir / p.name)

        print("\n" + "=" * 88)
        print("CARS V2 UNSEEN VALIDATION COMPLETE")
        print("=" * 88)
        print(f"결과 저장: {val_dir}")
        print(f"- {a_dir / 'baseline_v2_metrics.csv'}")
        print(f"- {a_dir / 'network_role_evaluation.csv'}")
        print(f"- {a_dir / 'cars_v2_metrics.csv'}")
        print(f"- {a_dir / 'cars_v2_false_positives.csv'}")
        print(f"- {a_dir / 'cars_v2_false_negatives.csv'}")
        print("=" * 88)

    finally:
        if backup and backup.exists():
            shutil.copy2(backup, ACTIVE_JSON)
            print(f"\n[RESTORE] {ACTIVE_JSON}")


if __name__ == "__main__":
    main()
