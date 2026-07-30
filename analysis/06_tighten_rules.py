"""第六步：两规则收紧 — 基于 flags + queue 直接构建最终数据集

规则 A: BENEFIT_OPEN + TRUST_OPEN 合计字符数 ≤ 5 → invalid
规则 B: ls_max_run ≥ 17 → invalid

输入: tisp_v3_flags.csv + tisp_v3_review_queue.csv
输出: tisp_v3_analysis_ready.csv（最终分析就绪数据集，71,922 行）
"""
from __future__ import annotations
from pathlib import Path
import sys
import pandas as pd
import numpy as np
import math

PROJECT_DIR = Path(__file__).resolve().parents[1]
FLAGS_PATH = PROJECT_DIR / "outputs" / "screening_v3" / "tisp_v3_flags.csv"
QUEUE_PATH = PROJECT_DIR / "outputs" / "screening_v3" / "tisp_v3_review_queue.csv"
OUTPUT_DIR = PROJECT_DIR / "outputs" / "screening_v3"


def _shannon_entropy(s: str) -> float:
    if not s:
        return 0.0
    freq = {}
    for c in s:
        freq[c] = freq.get(c, 0) + 1
    n = len(s)
    return -sum((c / n) * math.log2(c / n) for c in freq.values() if c > 0)


def is_gibberish_text(s: str) -> bool:
    """判定单条文本是否为乱码（修正版逻辑）"""
    s = str(s).strip().lower()
    if s in ("", "nan", "-99", "none"):
        return False
    no_spaces = s.replace(" ", "").replace("\r", "").replace("\n", "").replace("\t", "")
    n = len(no_spaces)
    if n < 3:
        return False

    # E: entropy
    raw_entropy = _shannon_entropy(no_spaces)
    log_n = math.log2(n) if n > 0 else 0
    adj_entropy = raw_entropy / log_n if log_n > 0 else 0
    low_entropy = (adj_entropy < 0.3) and (raw_entropy < 2.0)

    # Repetitive: same char repeated 15+
    repetitive = len(set(no_spaces.lower())) <= 2 and n >= 15

    # S: symbol ratio
    sym_count = sum(1 for c in no_spaces if not c.isalnum() and not c.isspace())
    high_symbol = (sym_count / max(n, 1)) > 0.7 and n >= 5

    # D: digit ratio
    dig_count = sum(1 for c in no_spaces if c.isdigit())
    high_digit = (dig_count / max(n, 1)) > 0.8 and n >= 5

    # M: encoding garble
    has_ufffd = "\ufffd" in no_spaces
    control_ratio = sum(1 for c in no_spaces if ord(c) < 32 and ord(c) not in (9, 10, 13)) / max(n, 1)
    has_surrogate = any(0xD800 <= ord(c) <= 0xDFFF for c in no_spaces)

    return low_entropy or repetitive or high_symbol or high_digit or has_ufffd or (control_ratio > 0.3) or has_surrogate


def both_len(r: pd.Series) -> int:
    b = str(r["BENEFIT_OPEN"]).strip()
    t = str(r["TRUST_OPEN"]).strip()
    bl = 0 if not b or b.lower() in ("nan", "na", "-99", "none", "") else len(b)
    tl = 0 if not t or t.lower() in ("nan", "na", "-99", "none", "") else len(t)
    return bl + tl


def main():
    print("=" * 50)
    print("第六步：两规则收紧")
    print("=" * 50)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    flags = pd.read_csv(FLAGS_PATH, dtype=str, keep_default_na=False, encoding="utf-8")
    flags["row_id"] = flags["row_id"].astype(int)
    queue = pd.read_csv(QUEUE_PATH, dtype=str, keep_default_na=False, encoding="utf-8")
    queue["row_id"] = queue["row_id"].astype(int)
    q_ids = set(int(x) for x in queue["row_id"])
    print(f"  flags: {len(flags)} 行, queue: {len(queue)} 行")

    # Step 1: 合并复核队列决策
    merged = flags.merge(
        queue[["row_id", "final_decision", "BENEFIT_OPEN_ZH"]],
        on="row_id", how="left", suffixes=("", "_q"),
    )
    merged["final_decision"] = merged["final_decision"].fillna("normal")

    # Step 2: 运行修正版乱码检测
    text_cols = ["BENEFIT_OPEN", "TRUST_OPEN"]
    combined_gib = pd.Series(False, index=merged.index)
    for col in text_cols:
        combined_gib = combined_gib | merged[col].apply(is_gibberish_text)
    merged.loc[combined_gib, "final_decision"] = "invalid"
    n_gib = combined_gib.sum()
    print(f"  真乱码 (gibberish): {n_gib} 行")

    # Step 3: 两规则计算
    merged["both_len"] = merged.apply(both_len, axis=1)
    rule_A = merged["both_len"] <= 5
    rule_B = merged["ls_max_run"].astype(float) >= 17
    rule_any = rule_A | rule_B

    # Step 4: 记录规则命中前的已有 invalid（队列 + gibberish）
    existing_invalid = set(merged[merged["final_decision"] == "invalid"]["row_id"])

    # Step 5: 规则命中 → 标记 invalid
    merged.loc[rule_any, "final_decision"] = "invalid"

    # Step 6: 标记来源
    merged["invalid_source"] = "none"
    a_only = set(merged[rule_A & ~rule_B]["row_id"]) - existing_invalid
    b_only = set(merged[rule_B & ~rule_A]["row_id"]) - existing_invalid
    ab_both = set(merged[rule_A & rule_B]["row_id"]) - existing_invalid

    for rid in a_only:
        merged.loc[merged["row_id"] == rid, "invalid_source"] = "rule_A_only"
    for rid in b_only:
        merged.loc[merged["row_id"] == rid, "invalid_source"] = "rule_B_only"
    for rid in ab_both:
        merged.loc[merged["row_id"] == rid, "invalid_source"] = "rule_A+B"
    for rid in existing_invalid:
        merged.loc[merged["row_id"] == rid, "invalid_source"] = "existing"

    # 删除多余的合并列
    for c in merged.columns:
        if c.endswith("_q") or c.endswith("_from_ready"):
            merged.drop(columns=[c], inplace=True, errors="ignore")

    # 列重排：row_id + final_decision + invalid_source + both_len 在前
    first_cols = ["row_id", "final_decision", "invalid_source", "both_len"]
    first_cols = [c for c in first_cols if c in merged.columns]
    rest = [c for c in merged.columns if c not in first_cols]
    merged = merged[first_cols + rest]

    # 输出：最终数据集
    out_path = OUTPUT_DIR / "tisp_v3_analysis_ready.csv"
    merged.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"\n  -> {out_path.name}")

    # 输出：复核队列（原人工复核的 1,552 条，含最终决策标注）
    review = merged[merged["row_id"].isin(q_ids)].copy()
    qcols = ["row_id", "COUNTRY_CODE", "COUNTRY_NAME", "final_decision", "invalid_source",
             "both_len", "screening_tier", "trigger_reason",
             "signal_count", "signal_attention", "signal_longstring",
             "signal_mahalanobis", "signal_odd_even",
             "ls_max_run", "md_score", "oe_r",
             "BENEFIT_OPEN", "TRUST_OPEN", "BENEFIT_OPEN_ZH",
             "ATTCHECK_NUMBER", "ATTCHECK_RES",
             "DEM_AGE", "DEM_GENDER", "DEM_EDU", "DEM_AGEGRP"]
    qcols = [c for c in qcols if c in merged.columns]
    review = review[qcols].sort_values(["screening_tier", "row_id"])
    review.to_csv(OUTPUT_DIR / "tisp_v3_review_annotated.csv", index=False, encoding="utf-8-sig")
    print(f"  -> tisp_v3_review_annotated.csv ({len(review)} rows, 复核队列含最终决策)")

    # 输出：规则收紧捕获清单（供第二轮复核参考）
    new_inv = merged[merged["invalid_source"].isin(["rule_A_only", "rule_B_only", "rule_A+B"])].copy()
    new_inv = new_inv[qcols].sort_values(["invalid_source", "row_id"])
    new_inv.to_csv(OUTPUT_DIR / "tisp_v3_tighten_captures.csv", index=False, encoding="utf-8-sig")
    print(f"  -> tisp_v3_tighten_captures.csv ({len(new_inv)} rows, 两规则新增)")

    # 输出：决策分布概况
    vc = merged["final_decision"].value_counts().reset_index()
    vc.columns = ["final_decision", "n"]
    vc["pct"] = (vc["n"].astype(float) / len(merged) * 100).round(2)
    vc = vc.sort_values("n", ascending=False)
    vc.to_csv(OUTPUT_DIR / "tisp_v3_decision_summary.csv", index=False, encoding="utf-8-sig")
    print(f"  -> tisp_v3_decision_summary.csv")

    # 输出：各国决策分布
    country = merged.groupby(["COUNTRY_CODE", "COUNTRY_NAME"], dropna=False)["final_decision"] \
        .value_counts().reset_index(name="n")
    total = merged.groupby("COUNTRY_CODE", dropna=False).size().rename("total")
    country = country.merge(total, on="COUNTRY_CODE")
    country["pct"] = (country["n"].astype(float) / country["total"] * 100).round(2)
    country = country.sort_values(["COUNTRY_CODE", "final_decision"])
    country.to_csv(OUTPUT_DIR / "tisp_v3_country_summary.csv", index=False, encoding="utf-8-sig")
    print(f"  -> tisp_v3_country_summary.csv")

    # 输出：信号分布概况
    sig = merged.groupby("trigger_reason", dropna=False)["final_decision"] \
        .value_counts().reset_index(name="n")
    sig = sig.sort_values(["trigger_reason", "final_decision"])
    sig.to_csv(OUTPUT_DIR / "tisp_v3_signal_summary.csv", index=False, encoding="utf-8-sig")
    print(f"  -> tisp_v3_signal_summary.csv")

    # 终端打印
    vc_d = merged["final_decision"].value_counts()
    src = merged[merged["final_decision"] == "invalid"]["invalid_source"].value_counts()
    valid = len(merged) - vc_d.get("invalid", 0)
    pct = valid / len(merged) * 100
    status = "达标" if 80 <= pct <= 90 else "略高" if pct > 90 else "偏低"

    print(f"\n  final_decision:")
    for v in ["normal", "valid1", "valid2", "invalid"]:
        n = vc_d.get(v, 0)
        print(f"    {v:>10s}: {n:>6d}  ({n / len(merged) * 100:.2f}%)")
    print(f"\n  invalid 来源:")
    for s, n in src.items():
        print(f"    {s:>15s}: {n}")
    print(f"\n  有效率: {valid} / {len(merged)} = {pct:.2f}%  [{status}]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
