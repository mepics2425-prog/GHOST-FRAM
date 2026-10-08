from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

POSITIVE_TYPES = {"farm", "mule", "hub"}
NEGATIVE_TYPES = {"normal", "hardcore", "guild"}
EVAL_TYPES = POSITIVE_TYPES | NEGATIVE_TYPES


def evaluate_at_k(df: pd.DataFrame, score_col: str) -> dict:
    d = df[df["ground_truth_type"].isin(EVAL_TYPES)].copy()
    d[score_col] = pd.to_numeric(d[score_col], errors="coerce").fillna(0.0)
    d = d.sort_values(score_col, ascending=False).reset_index(drop=True)

    k = int(d["ground_truth_type"].isin(POSITIVE_TYPES).sum())
    d["pred_positive"] = False
    if k > 0:
        d.loc[: k - 1, "pred_positive"] = True

    actual = d["ground_truth_type"].isin(POSITIVE_TYPES)
    pred = d["pred_positive"]

    tp = int((actual & pred).sum())
    fp = int((~actual & pred).sum())
    fn = int((actual & ~pred).sum())
    tn = int((~actual & ~pred).sum())

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall)
        else 0.0
    )

    detected = d[d["pred_positive"] & actual]
    by_type = detected["ground_truth_type"].value_counts().to_dict()

    return {
        "evaluation_accounts": len(d),
        "positive_accounts": k,
        "precision_at_k": precision,
        "recall_at_k": recall,
        "f1_at_k": f1,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "detected_farm": int(by_type.get("farm", 0)),
        "detected_mule": int(by_type.get("mule", 0)),
        "detected_hub": int(by_type.get("hub", 0)),
    }


def get_reference_f1() -> float | None:
    path = ROOT / "data" / "validation" / "unseen_03" / "analysis" / "cars_v3_account_scores.csv"
    if not path.exists():
        return None
    df = pd.read_csv(path)
    return evaluate_at_k(df, "cars_v3_score")["f1_at_k"]


def run_one(json_path: Path, label: str) -> dict:
    runner = ROOT / "src" / "run_unseen_validation_v3.py"
    if not runner.exists():
        raise FileNotFoundError(f"runner 없음: {runner}")

    cmd = [
        sys.executable,
        str(runner),
        "--input",
        str(json_path),
        "--label",
        label,
    ]

    print("\n" + "=" * 104)
    print(f"CARS V3 RED TEAM VALIDATION | {label}")
    print("=" * 104)

    result = subprocess.run(cmd, cwd=ROOT, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"{label} 검증 실패 (exit={result.returncode})")

    a_dir = ROOT / "data" / "validation" / label / "analysis"

    v3_path = a_dir / "cars_v3_account_scores.csv"
    v2_path = a_dir / "cars_v2_account_scores.csv"
    baseline_path = a_dir / "baseline_v2_account_scores.csv"

    if not v3_path.exists():
        raise FileNotFoundError(f"CARS V3 결과 없음: {v3_path}")

    v3 = pd.read_csv(v3_path)
    v2 = pd.read_csv(v2_path)
    baseline = pd.read_csv(baseline_path)

    v3_m = evaluate_at_k(v3, "cars_v3_score")
    v2_m = evaluate_at_k(v2, "cars_v2_score")
    base_m = evaluate_at_k(baseline, "baseline_risk_score")

    scenario = json_path.stem.replace("aetheria-redteam-", "")

    return {
        "scenario": scenario,
        **v3_m,
        "cars_v2_f1_at_k": v2_m["f1_at_k"],
        "baseline_f1_at_k": base_m["f1_at_k"],
        "validation_path": str(ROOT / "data" / "validation" / label),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Batch red-team validation for frozen CARS V3"
    )
    parser.add_argument(
        "--indir",
        default=str(ROOT / "data" / "redteam_v3"),
        help="red-team JSON directory",
    )
    parser.add_argument(
        "--output",
        default=str(ROOT / "data" / "redteam_v3" / "redteam_v3_results.csv"),
        help="summary CSV path",
    )
    args = parser.parse_args()

    indir = Path(args.indir)
    files = sorted(indir.glob("aetheria-redteam-*.json"))
    if not files:
        raise FileNotFoundError(f"red-team JSON 없음: {indir}")

    preferred = [
        "time_jitter",
        "mule_split",
        "micro_tx",
        "normal_mix",
        "behavior_noise",
        "composite",
    ]
    order = {name: i for i, name in enumerate(preferred)}
    files.sort(key=lambda p: order.get(p.stem.replace("aetheria-redteam-", ""), 999))

    reference_f1 = get_reference_f1()
    rows = []

    for path in files:
        scenario = path.stem.replace("aetheria-redteam-", "")
        label = f"redteam_v3_{scenario}"
        row = run_one(path, label)
        row["heldout_reference_f1"] = reference_f1
        row["f1_delta_vs_unseen03"] = (
            row["f1_at_k"] - reference_f1 if reference_f1 is not None else None
        )
        rows.append(row)

    result_df = pd.DataFrame(rows)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    result_df.to_csv(output, index=False, encoding="utf-8-sig")

    display_cols = [
        "scenario",
        "precision_at_k",
        "recall_at_k",
        "f1_at_k",
        "f1_delta_vs_unseen03",
        "cars_v2_f1_at_k",
        "baseline_f1_at_k",
        "tp",
        "fp",
        "fn",
        "tn",
        "detected_farm",
        "detected_mule",
        "detected_hub",
    ]

    view = result_df[display_cols].copy()
    for col in [
        "precision_at_k",
        "recall_at_k",
        "f1_at_k",
        "f1_delta_vs_unseen03",
        "cars_v2_f1_at_k",
        "baseline_f1_at_k",
    ]:
        view[col] = pd.to_numeric(view[col], errors="coerce").round(3)

    try:
        md = view.to_markdown(index=False)
    except Exception:
        md = view.to_string(index=False)

    md_path = output.with_suffix(".md")
    header = (
        "# GHOST FARM — CARS V3 Red-Team Robustness\n\n"
        "Detector: frozen CARS V3\n\n"
        "Base snapshot: unseen_03\n\n"
        "Evaluation positives: farm / mule / hub\n\n"
        "Evaluation negatives: normal / hardcore / guild\n\n"
    )
    if reference_f1 is not None:
        header += f"Held-out unseen_03 reference F1@K: {reference_f1:.3f}\n\n"

    md_path.write_text(header + md + "\n", encoding="utf-8")

    print("\n" + "#" * 104)
    print("CARS V3 RED TEAM SUMMARY")
    print("#" * 104)
    print(view.to_string(index=False))
    print("\nSaved:")
    print(output)
    print(md_path)


if __name__ == "__main__":
    main()
