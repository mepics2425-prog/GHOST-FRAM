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

    cutoff = float(d.iloc[k - 1][score_col]) if k > 0 and len(d) >= k else 0.0

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
        "cutoff_score": cutoff,
    }


def shadow_unlabeled(df: pd.DataFrame, score_col: str) -> dict:
    unlabeled = df[df["ground_truth_type"].isna()].copy()
    if unlabeled.empty:
        return {
            "shadow_unlabeled_count": 0,
            "shadow_top_user": "",
            "shadow_top_score": None,
            "shadow_top_rank": None,
        }

    unlabeled[score_col] = pd.to_numeric(unlabeled[score_col], errors="coerce").fillna(0.0)
    top = unlabeled.sort_values(score_col, ascending=False).iloc[0]
    rank_col = "cars_v2_rank" if "cars_v2_rank" in unlabeled.columns else None

    return {
        "shadow_unlabeled_count": int(len(unlabeled)),
        "shadow_top_user": str(top.get("user_id", "")),
        "shadow_top_score": float(top[score_col]),
        "shadow_top_rank": int(top[rank_col]) if rank_col and pd.notna(top[rank_col]) else None,
    }


def get_reference_f1() -> float | None:
    path = ROOT / "data" / "validation" / "unseen_02" / "analysis" / "cars_v2_account_scores.csv"
    if not path.exists():
        return None
    df = pd.read_csv(path)
    return evaluate_at_k(df, "cars_v2_score")["f1_at_k"]


def run_one(json_path: Path, label: str) -> dict:
    runner = ROOT / "src" / "run_unseen_validation_v2.py"
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

    print("\n" + "=" * 100)
    print(f"RED TEAM VALIDATION | {label}")
    print("=" * 100)

    result = subprocess.run(cmd, cwd=ROOT, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"{label} 검증 실패 (exit={result.returncode})")

    val_dir = ROOT / "data" / "validation" / label / "analysis"

    cars_path = val_dir / "cars_v2_account_scores.csv"
    baseline_path = val_dir / "baseline_v2_account_scores.csv"

    if not cars_path.exists():
        raise FileNotFoundError(f"CARS 결과 없음: {cars_path}")
    if not baseline_path.exists():
        raise FileNotFoundError(f"Baseline 결과 없음: {baseline_path}")

    cars = pd.read_csv(cars_path)
    baseline = pd.read_csv(baseline_path)

    cars_metrics = evaluate_at_k(cars, "cars_v2_score")
    baseline_metrics = evaluate_at_k(baseline, "baseline_risk_score")
    shadow = shadow_unlabeled(cars, "cars_v2_score")

    scenario = json_path.stem.replace("aetheria-redteam-", "")

    return {
        "scenario": scenario,
        **cars_metrics,
        "baseline_f1_at_k": baseline_metrics["f1_at_k"],
        **shadow,
        "validation_path": str(ROOT / "data" / "validation" / label),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Batch validation for frozen CARS V2 against GHOST FARM red-team snapshots"
    )
    parser.add_argument(
        "--indir",
        default=str(ROOT / "data" / "redteam"),
        help="red-team JSON directory",
    )
    parser.add_argument(
        "--output",
        default=str(ROOT / "data" / "redteam" / "redteam_results.csv"),
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
        label = f"redteam_{scenario}"
        row = run_one(path, label)
        row["heldout_reference_f1"] = reference_f1
        row["f1_delta_vs_unseen02"] = (
            row["f1_at_k"] - reference_f1 if reference_f1 is not None else None
        )
        rows.append(row)

    result_df = pd.DataFrame(rows)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    result_df.to_csv(output, index=False, encoding="utf-8-sig")

    md_path = output.with_suffix(".md")
    display_cols = [
        "scenario",
        "precision_at_k",
        "recall_at_k",
        "f1_at_k",
        "f1_delta_vs_unseen02",
        "baseline_f1_at_k",
        "tp",
        "fp",
        "fn",
        "tn",
        "detected_farm",
        "detected_mule",
        "detected_hub",
        "shadow_top_score",
        "shadow_top_rank",
    ]

    view = result_df[display_cols].copy()
    for col in [
        "precision_at_k",
        "recall_at_k",
        "f1_at_k",
        "f1_delta_vs_unseen02",
        "baseline_f1_at_k",
        "shadow_top_score",
    ]:
        view[col] = pd.to_numeric(view[col], errors="coerce").round(3)

    try:
        md = view.to_markdown(index=False)
    except Exception:
        md = view.to_string(index=False)

    md_path.write_text(
        "# GHOST FARM — CARS V2 Red-Team Robustness\n\n"
        "Detector: frozen CARS V2\n\n"
        "Evaluation positives: farm / mule / hub\n\n"
        "Evaluation negatives: normal / hardcore / guild\n\n"
        f"Held-out unseen_02 reference F1@K: "
        f"{reference_f1:.3f}\n\n" if reference_f1 is not None else
        "# GHOST FARM — CARS V2 Red-Team Robustness\n\n"
        + md
        + "\n",
        encoding="utf-8",
    )

    # Above conditional can make markdown awkward; rewrite cleanly.
    header = (
        "# GHOST FARM — CARS V2 Red-Team Robustness\n\n"
        "Detector: frozen CARS V2\n\n"
        "Evaluation positives: farm / mule / hub\n\n"
        "Evaluation negatives: normal / hardcore / guild\n\n"
    )
    if reference_f1 is not None:
        header += f"Held-out unseen_02 reference F1@K: {reference_f1:.3f}\n\n"

    md_path.write_text(header + md + "\n", encoding="utf-8")

    print("\n" + "#" * 100)
    print("RED TEAM SUMMARY")
    print("#" * 100)
    print(view.to_string(index=False))
    print("\nSaved:")
    print(output)
    print(md_path)


if __name__ == "__main__":
    main()
