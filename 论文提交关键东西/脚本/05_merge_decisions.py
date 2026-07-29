"""将人工复核 final_decision 合并回全量数据，输出分析就绪数据集。

输出：
1. tisp_v3_analysis_ready.csv     — valid1+valid2 有效数据集
2. tisp_v3_decision_summary.csv   — final_decision 分布概况
3. tisp_v3_country_summary.csv    — 各国决策分布
4. tisp_v3_signal_summary.csv     — 各信号 trigger_reason 分布
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_DIR = Path(__file__).resolve().parents[1]
FLAGS_PATH = PROJECT_DIR / "outputs" / "screening_v3" / "tisp_v3_flags.csv"
QUEUE_PATH = PROJECT_DIR / "outputs" / "screening_v3" / "tisp_v3_review_queue.csv"
OUTPUT_DIR = PROJECT_DIR / "outputs" / "screening_v3"


def load_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    flags = pd.read_csv(FLAGS_PATH, dtype=str, keep_default_na=False, encoding="utf-8")
    queue = pd.read_csv(QUEUE_PATH, dtype=str, keep_default_na=False, encoding="utf-8")
    flags["row_id"] = flags["row_id"].astype(np.int64)
    queue["row_id"] = queue["row_id"].astype(np.int64)
    return flags, queue


def merge_decisions(flags: pd.DataFrame, queue: pd.DataFrame) -> pd.DataFrame:
    """将人工复核的 final_decision 合并回全量数据。"""
    merged = flags.merge(
        queue[["row_id", "final_decision"]],
        on="row_id",
        how="left",
    )
    merged["final_decision"] = merged["final_decision"].fillna("normal")
    merged["final_decision"] = merged["final_decision"].astype("string")

    for col in ["signal_attention", "signal_longstring", "signal_mahalanobis",
                "signal_odd_even", "veto_any", "is_verify", "signal_count"]:
        if col in merged.columns:
            merged[col] = merged[col].astype(int)

    return merged


def verify_merge(merged: pd.DataFrame, queue: pd.DataFrame) -> None:
    """验证 queue 中的决策已正确合并。"""
    q_dec = queue[queue["final_decision"].isin(["valid1", "valid2", "invalid"])].copy()
    check = q_dec.merge(merged[["row_id", "final_decision"]], on="row_id", suffixes=("_q", "_m"))
    mismatch = check[check["final_decision_q"] != check["final_decision_m"]]
    print(f"  合并验证: {'通过' if len(mismatch) == 0 else f'失败（错配 {len(mismatch)} 行）'}")
    if len(mismatch) > 0:
        print(mismatch[["row_id", "final_decision_q", "final_decision_m"]].head())


def output_analysis_ready(merged: pd.DataFrame) -> Path:
    """输出分析就绪数据集（normal + valid1 + valid2，即排除 invalid 和 unsure）。"""
    keep = merged[merged["final_decision"].isin(["normal", "valid1", "valid2"])].copy()
    path = OUTPUT_DIR / "tisp_v3_analysis_ready.csv"
    keep.to_csv(path, index=False, encoding="utf-8-sig")
    print(f"  分析就绪数据集: {len(keep)} 行（normal={int((keep['final_decision']=='normal').sum())}, "
          f"valid1={int((keep['final_decision']=='valid1').sum())}, "
          f"valid2={int((keep['final_decision']=='valid2').sum())}）→ {path.name}")
    return path


def output_decision_summary(merged: pd.DataFrame) -> Path:
    """输出 final_decision 分布概况。"""
    vc = merged["final_decision"].value_counts().reset_index()
    vc.columns = ["final_decision", "n"]
    vc["pct"] = (vc["n"].astype(float) / len(merged) * 100).round(2)
    vc = vc.sort_values("n", ascending=False)
    path = OUTPUT_DIR / "tisp_v3_decision_summary.csv"
    vc.to_csv(path, index=False, encoding="utf-8-sig")
    print(f"  决策分布概况 → {path.name}")
    for _, r in vc.iterrows():
        print(f"    {r['final_decision']:>12s}: {r['n']:>6d} ({r['pct']:5.2f}%)")
    return path


def output_country_summary(merged: pd.DataFrame) -> Path:
    """输出各国 final_decision 分布。"""
    country_dec = merged.groupby(["COUNTRY_CODE", "COUNTRY_NAME"], dropna=False)["final_decision"] \
        .value_counts().reset_index(name="n")
    total = merged.groupby("COUNTRY_CODE", dropna=False).size().rename("total")
    country_dec = country_dec.merge(total, on="COUNTRY_CODE")
    country_dec["pct"] = (country_dec["n"].astype(float) / country_dec["total"] * 100).round(2)
    country_dec = country_dec.sort_values(["COUNTRY_CODE", "final_decision"])

    path = OUTPUT_DIR / "tisp_v3_country_summary.csv"
    country_dec.to_csv(path, index=False, encoding="utf-8-sig")
    print(f"  各国决策分布 → {path.name} ({country_dec['COUNTRY_CODE'].nunique()} 国)")
    return path


def output_signal_summary(merged: pd.DataFrame) -> Path:
    """输出各信号 trigger_reason 分布。"""
    sig_dec = merged.groupby("trigger_reason", dropna=False)["final_decision"] \
        .value_counts().reset_index(name="n")
    sig_dec = sig_dec.sort_values(["trigger_reason", "final_decision"])

    path = OUTPUT_DIR / "tisp_v3_signal_summary.csv"
    sig_dec.to_csv(path, index=False, encoding="utf-8-sig")
    print(f"  信号分布概况 → {path.name}")
    return path


def main():
    print("=== TISP V3 决策合并 ===")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    flags, queue = load_data()
    print(f"  全量数据: {len(flags)} 行")
    print(f"  复核队列: {len(queue)} 行")

    merged = merge_decisions(flags, queue)
    print(f"  合并完成: {len(merged)} 行")

    verify_merge(merged, queue)
    output_analysis_ready(merged)
    output_decision_summary(merged)
    output_country_summary(merged)
    output_signal_summary(merged)

    print("\n  完成！")


if __name__ == "__main__":
    main()
