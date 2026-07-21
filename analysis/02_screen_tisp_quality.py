"""TISP 第一轮机械筛查（只标记，不删除）。

该脚本的全部阈值和变量清单来自 docs/TISP第一轮机械筛查优化实施计划.md。
原始 dataset.csv 只读；运行结果写入 outputs/screening/。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.covariance import LedoitWolf


PROJECT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = PROJECT_DIR / "D081_TISP" / "dataset.csv"
DEFAULT_OUTPUT_DIR = PROJECT_DIR / "outputs" / "screening"
SPECIAL_MISSING = {"", "NA", "N/A", "-98", "-99"}
MIN_COUNTRY_N_FOR_MD = 135  # 5 * 27 个核心题
MAX_MD_MISSING = 5
MD_QUANTILE = 0.995

TRUST = [
    "TRUST_SCI_expert", "TRUST_SCI_honest", "TRUST_SCI_concerned",
    "TRUST_SCI_open", "TRUST_SCI_intellig", "TRUST_SCI_ethical",
    "TRUST_SCI_improve", "TRUST_SCI_trans", "TRUST_SCI_qualified",
    "TRUST_SCI_sincere", "TRUST_SCI_otherint", "TRUST_SCI_otherviews",
]
SCIPOP = [
    "SCIPOP_common", "SCIPOP_good", "SCIPOP_advantage", "SCIPOP_cahoots",
    "SCIPOP_influence", "SCIPOP_involved", "SCIPOP_lifeexp", "SCIPOP_rely",
]
OUTSPOKEN = ["OUTSPOKEN_othersthink", "OUTSPOKEN_isolate", "OUTSPOKEN_against"]
SDO = ["SDO_allgroupsconsider", "SDO_notpushequality", "SDO_equalityideal", "SDO_superiordominate"]
CORE_MD_COLS = TRUST + SCIPOP + OUTSPOKEN + SDO

LONG_BLOCKS: dict[str, tuple[list[str], int]] = {
    "sciinfo": ([
        "SCIINFO_newspapersmags", "SCIINFO_tvradio", "SCIINFO_newswebsitesapps",
        "SCIINFO_videospodcasts", "SCIINFO_filmsseries", "SCIINFO_books",
        "SCIINFO_socialmedia", "SCIINFO_messengers", "SCIINFO_museumszoos",
        "SCIINFO_rlconversations",
    ], 8),
    "normperc": ([
        "NORMPERC_integrate", "NORMPERC_advocate", "NORMPERC_communicate",
        "NORMPERC_involved", "NORMPERC_outreach", "NORMPERC_independent",
    ], 5),
    "trust_sci": (TRUST, 10),
    "scipop": (SCIPOP, 7),
    "clim_emo": ([
        "CLIM_EMO_helpless", "CLIM_EMO_anxious", "CLIM_EMO_optimistic",
        "CLIM_EMO_angry", "CLIM_EMO_guilty", "CLIM_EMO_ashamed",
        "CLIM_EMO_depressed", "CLIM_EMO_pessimistic", "CLIM_EMO_indifferent",
    ], 8),
    "clim_gov": ([
        "CLIM_GOV_concerns", "CLIM_GOV_doingenough", "CLIM_GOV_dismisspeople",
        "CLIM_GOV_science", "CLIM_GOV_futuregens", "CLIM_GOV_trustworthy",
        "CLIM_GOV_lying",
    ], 6),
    "clim_weatherpast": ([
        "CLIM_WEATHERPAST_floods", "CLIM_WEATHERPAST_heatwaves",
        "CLIM_WEATHERPAST_heavystorms", "CLIM_WEATHERPAST_wildfires",
        "CLIM_WEATHERPAST_heavyrain", "CLIM_WEATHERPAST_droughts",
    ], 5),
    "clim_weatherfutu": ([
        "CLIM_WEATHERFUTU_floods", "CLIM_WEATHERFUTU_heatwaves",
        "CLIM_WEATHERFUTU_heavystorms", "CLIM_WEATHERFUTU_wildfires",
        "CLIM_WEATHERFUTU_heavyrain", "CLIM_WEATHERFUTU_droughts",
    ], 5),
}

ITEM_RANGES: dict[str, tuple[int, int]] = {}
for _cols, _threshold in LONG_BLOCKS.values():
    for _col in _cols:
        ITEM_RANGES[_col] = (1, 5)
# SCIINFO 是使用频率量表，原问卷范围为 1--7；其余上方 Longstring 题块为 1--5。
for _col in LONG_BLOCKS["sciinfo"][0]:
    ITEM_RANGES[_col] = (1, 7)
for _col in OUTSPOKEN:
    ITEM_RANGES[_col] = (1, 5)
for _col in SDO:
    ITEM_RANGES[_col] = (1, 10)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def normalize_text(series: pd.Series) -> pd.Series:
    """保留原值不动，只为规则比较生成去空格文本。"""
    return series.astype("string").fillna("").str.strip()


def numeric_with_range(
    raw: pd.Series, low: int, high: int
) -> tuple[pd.Series, pd.Series]:
    """将约定缺失、非数字和越界值仅在计算副本中视为 NA。

    返回 (清洗后的数值, 需要记录的范围/编码异常标记)。
    """
    text = normalize_text(raw)
    is_special = text.str.upper().isin(SPECIAL_MISSING)
    # 马氏距离中需要填入可能为 3.5 的国家中位数，故计算副本固定为浮点数。
    numeric = pd.to_numeric(text.where(~is_special), errors="coerce").astype(float)
    range_issue = (~is_special) & (numeric.isna() | (numeric < low) | (numeric > high))
    return numeric.where(~range_issue), range_issue.astype("int8")


def build_calculation_frame(raw: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """建立计算副本并汇总任一量表题的越界/编码异常。"""
    numeric: dict[str, pd.Series] = {}
    issues = pd.Series(0, index=raw.index, dtype="int8")
    for col, (low, high) in ITEM_RANGES.items():
        values, issue = numeric_with_range(raw[col], low, high)
        numeric[col] = values
        issues = np.maximum(issues, issue).astype("int8")
    return pd.DataFrame(numeric, index=raw.index), issues


def attention_statuses(raw: pd.DataFrame) -> pd.DataFrame:
    number = normalize_text(raw["ATTCHECK_NUMBER"])
    response_text = normalize_text(raw["ATTCHECK_RES"])
    response = pd.to_numeric(response_text.where(~response_text.str.upper().isin(SPECIAL_MISSING)), errors="coerce")
    result = pd.DataFrame(index=raw.index)
    result["attention_number_status"] = np.select(
        [number.str.upper().isin(SPECIAL_MISSING), number.eq("213")],
        ["missing", "pass"], default="fail",
    )
    result["attention_response_status"] = np.select(
        [response_text.str.upper().isin(SPECIAL_MISSING), response.eq(1).fillna(False)],
        ["missing", "pass"], default="anomaly",
    )
    result["attention_flag"] = (
        (result["attention_number_status"] != "pass")
        | (result["attention_response_status"] != "pass")
    ).astype("int8")
    return result


def _quantile(values: np.ndarray, q: float) -> float:
    """显式固定线性分位数算法，便于复现。"""
    try:
        return float(np.quantile(values, q, method="linear"))
    except TypeError:  # 兼容旧版 numpy
        return float(np.quantile(values, q, interpolation="linear"))


def calculate_country_mahalanobis(
    numeric: pd.DataFrame, countries: pd.Series
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    """按国家分别计算核心 27 题 Ledoit-Wolf 马氏距离；绝不跨国合并。"""
    result = pd.DataFrame(index=numeric.index)
    result["md_score"] = np.nan
    result["md_rank_percentile"] = np.nan
    result["md_country_threshold"] = np.nan
    result["md_flag"] = 0
    result["md_n_missing"] = numeric[CORE_MD_COLS].isna().sum(axis=1).astype("int16")
    result["md_core_n_items_used"] = 0
    result["md_dropped_constant_item_n"] = 0
    result["md_not_computable"] = 0
    result["md_not_computable_reason"] = ""
    details: list[dict[str, Any]] = []

    country_key = normalize_text(countries).replace("", "__MISSING_COUNTRY__")
    for country, index in country_key.groupby(country_key, sort=True).groups.items():
        idx = pd.Index(index)
        block = numeric.loc[idx, CORE_MD_COLS]
        eligible = block.notna().sum(axis=1) >= (len(CORE_MD_COLS) - MAX_MD_MISSING)
        too_missing_idx = eligible.index[~eligible]
        result.loc[too_missing_idx, "md_not_computable"] = 1
        result.loc[too_missing_idx, "md_not_computable_reason"] = "more_than_5_core_items_missing"

        use_idx = eligible.index[eligible]
        detail: dict[str, Any] = {
            "country_code": str(country), "country_n": int(len(idx)),
            "eligible_n": int(len(use_idx)), "items_used": 0,
            "dropped_constant_item_n": 0, "computable": False,
            "reason": "", "threshold_p995": None,
            "p99": None, "p9975": None, "flagged_n": 0,
        }
        if len(use_idx) < MIN_COUNTRY_N_FOR_MD:
            reason = "eligible_sample_below_135"
            result.loc[use_idx, "md_not_computable"] = 1
            result.loc[use_idx, "md_not_computable_reason"] = reason
            detail["reason"] = reason
            details.append(detail)
            continue

        working = block.loc[use_idx].copy()
        working = working.fillna(working.median(axis=0))
        std = working.std(axis=0, ddof=0)
        usable_cols = std.index[std > 0].tolist()
        detail["items_used"] = len(usable_cols)
        detail["dropped_constant_item_n"] = len(CORE_MD_COLS) - len(usable_cols)
        result.loc[idx, "md_core_n_items_used"] = len(usable_cols)
        result.loc[idx, "md_dropped_constant_item_n"] = len(CORE_MD_COLS) - len(usable_cols)
        if len(usable_cols) < 10:
            reason = "fewer_than_10_nonconstant_items"
            result.loc[use_idx, "md_not_computable"] = 1
            result.loc[use_idx, "md_not_computable_reason"] = reason
            detail["reason"] = reason
            details.append(detail)
            continue

        z = (working[usable_cols] - working[usable_cols].mean(axis=0)) / working[usable_cols].std(axis=0, ddof=0)
        try:
            distances = np.sqrt(LedoitWolf().fit(z).mahalanobis(z))
        except Exception as exc:  # 保留样本，记录不可计算的原因
            reason = f"ledoitwolf_error:{type(exc).__name__}"
            result.loc[use_idx, "md_not_computable"] = 1
            result.loc[use_idx, "md_not_computable_reason"] = reason
            detail["reason"] = reason
            details.append(detail)
            continue

        threshold = _quantile(distances, MD_QUANTILE)
        ranks = pd.Series(distances, index=use_idx).rank(method="max", pct=True) * 100
        flags = distances > threshold
        result.loc[use_idx, "md_score"] = distances
        result.loc[use_idx, "md_rank_percentile"] = ranks
        result.loc[idx, "md_country_threshold"] = threshold
        result.loc[use_idx, "md_flag"] = flags.astype("int8")
        detail.update({
            "computable": True, "reason": "", "threshold_p995": threshold,
            "p99": _quantile(distances, 0.99), "p9975": _quantile(distances, 0.9975),
            "flagged_n": int(flags.sum()),
        })
        details.append(detail)
    return result, details


def odd_even_correlation(values: pd.DataFrame, minimum_pairs: int) -> tuple[float, int, str]:
    """按原题序 (第1/2、3/4...) 做配对；缺失配对不参与计算。"""
    left = values.iloc[:, 0::2].to_numpy(dtype=float).ravel()
    right = values.iloc[:, 1::2].to_numpy(dtype=float).ravel()
    keep = ~(np.isnan(left) | np.isnan(right))
    left, right = left[keep], right[keep]
    pairs_n = len(left)
    if pairs_n < minimum_pairs:
        return np.nan, pairs_n, "insufficient_pairs"
    if np.std(left) == 0 or np.std(right) == 0:
        return np.nan, pairs_n, "constant_vector"
    return float(np.corrcoef(left, right)[0, 1]), pairs_n, ""


def calculate_odd_even(numeric: pd.DataFrame) -> pd.DataFrame:
    result = pd.DataFrame(index=numeric.index)
    for label, cols, minimum in (("trust", TRUST, 4), ("scipop", SCIPOP, 3)):
        # 每行将 (第1,2)、(第3,4)... 的有效配对拼接后计算 Pearson r。
        array = numeric[cols].to_numpy(dtype=float)
        left, right = array[:, 0::2], array[:, 1::2]
        keep = ~(np.isnan(left) | np.isnan(right))
        n_pairs = keep.sum(axis=1)
        x = np.where(keep, left, 0.0)
        y = np.where(keep, right, 0.0)
        sx, sy = x.sum(axis=1), y.sum(axis=1)
        sxx, syy, sxy = (x * x).sum(axis=1), (y * y).sum(axis=1), (x * y).sum(axis=1)
        numerator = n_pairs * sxy - sx * sy
        denominator_sq = (n_pairs * sxx - sx * sx) * (n_pairs * syy - sy * sy)
        valid = (n_pairs >= minimum) & (denominator_sq > 0)
        r_values = np.full(len(array), np.nan)
        r_values[valid] = numerator[valid] / np.sqrt(denominator_sq[valid])
        reasons = np.where(n_pairs < minimum, "insufficient_pairs", np.where(denominator_sq <= 0, "constant_vector", ""))
        result[f"{label}_eo_r"] = r_values
        result[f"{label}_eo_pairs_n"] = n_pairs
        result[f"{label}_eo_not_computable"] = (~valid).astype("int8")
        result[f"{label}_eo_reason"] = reasons
        result[f"{label}_eo_low_flag"] = (r_values < 0.10).astype("int8")
    both_low = (result["trust_eo_low_flag"] == 1) & (result["scipop_eo_low_flag"] == 1)
    both_computable = (result["trust_eo_not_computable"] == 0) & (result["scipop_eo_not_computable"] == 0)
    result["odd_even_flag"] = (both_low & both_computable).astype("int8")
    return result


def longest_run(values: list[float]) -> tuple[float, int | None, float]:
    """缺失立即打断；相同的最长连续作答返回长度、起始题序和答案。"""
    best_length = 0
    best_start: int | None = None
    best_value = np.nan
    current_length = 0
    current_start: int | None = None
    current_value = np.nan
    for position, value in enumerate(values, start=1):
        if pd.isna(value):
            current_length, current_start, current_value = 0, None, np.nan
            continue
        if current_length and value == current_value:
            current_length += 1
        else:
            current_length, current_start, current_value = 1, position, value
        if current_length > best_length:
            best_length, best_start, best_value = current_length, current_start, current_value
    return (np.nan, None, np.nan) if best_length == 0 else (best_length, best_start, best_value)


def calculate_longstrings(numeric: pd.DataFrame) -> pd.DataFrame:
    result = pd.DataFrame(index=numeric.index)
    block_flags: list[str] = []
    for label, (cols, threshold) in LONG_BLOCKS.items():
        array = numeric[cols].to_numpy(dtype=float)
        n_rows = len(array)
        current_len = np.zeros(n_rows, dtype=int)
        current_start = np.full(n_rows, -1, dtype=int)
        best_len = np.zeros(n_rows, dtype=int)
        best_start = np.full(n_rows, -1, dtype=int)
        best_value = np.full(n_rows, np.nan)
        previous = np.full(n_rows, np.nan)
        previous_valid = np.zeros(n_rows, dtype=bool)
        for position in range(array.shape[1]):
            value = array[:, position]
            valid = ~np.isnan(value)
            same = valid & previous_valid & (value == previous)
            new_run = valid & ~same
            current_len = np.where(valid, np.where(same, current_len + 1, 1), 0)
            current_start = np.where(new_run, position + 1, current_start)
            better = current_len > best_len
            best_len = np.where(better, current_len, best_len)
            best_start = np.where(better, current_start, best_start)
            best_value = np.where(better, value, best_value)
            previous, previous_valid = value, valid
        max_run = np.where(best_len == 0, np.nan, best_len.astype(float))
        start_item = np.where(best_len == 0, np.nan, best_start.astype(float))
        answer_value = np.where(best_len == 0, np.nan, best_value)
        result[f"long_{label}_max_run"] = max_run
        result[f"long_{label}_start_item"] = start_item
        result[f"long_{label}_answer_value"] = answer_value
        result[f"long_{label}_threshold"] = threshold
        result[f"long_{label}_not_computable"] = (best_len == 0).astype("int8")
        result[f"long_{label}_flag"] = (result[f"long_{label}_max_run"] >= threshold).fillna(False).astype("int8")
        block_flags.append(f"long_{label}_flag")
    result["longstring_flag"] = result[block_flags].any(axis=1).astype("int8")
    result["longstring_trigger_blocks"] = result.apply(
        lambda row: ";".join(name.removeprefix("long_").removesuffix("_flag") for name in block_flags if row[name] == 1),
        axis=1,
    )
    return result


def aggregate_flags(attention: pd.DataFrame, md: pd.DataFrame, eo: pd.DataFrame, long: pd.DataFrame) -> pd.DataFrame:
    result = pd.DataFrame(index=attention.index)
    families = pd.DataFrame({
        "attention": attention["attention_flag"], "mahalanobis": md["md_flag"],
        "odd_even": eo["odd_even_flag"], "longstring": long["longstring_flag"],
    }, index=attention.index).astype("int8")
    result["flag_count"] = families.sum(axis=1).astype("int8")
    result["mechanical_flag"] = (result["flag_count"] > 0).astype("int8")

    non_attention_count = families[["mahalanobis", "odd_even", "longstring"]].sum(axis=1)
    all_non_attention_unavailable = (
        (md["md_not_computable"] == 1)
        & (eo["trust_eo_not_computable"] == 1)
        & (eo["scipop_eo_not_computable"] == 1)
        & (long.filter(like="_not_computable").all(axis=1))
    )
    priority = np.select(
        [families["attention"].eq(1), non_attention_count.ge(2), families["mahalanobis"].eq(1),
         families["longstring"].eq(1), families["odd_even"].eq(1), all_non_attention_unavailable],
        ["HIGH", "HIGH", "MEDIUM", "MEDIUM", "LOW", "NOT_COMPUTABLE"], default="NONE",
    )
    result["review_priority"] = priority

    reasons: list[str] = []
    for idx in result.index:
        item_reasons: list[str] = []
        if attention.at[idx, "attention_number_status"] == "fail": item_reasons.append("attention_number_fail")
        if attention.at[idx, "attention_number_status"] == "missing": item_reasons.append("attention_number_missing")
        if attention.at[idx, "attention_response_status"] == "anomaly": item_reasons.append("attention_response_anomaly")
        if attention.at[idx, "attention_response_status"] == "missing": item_reasons.append("attention_response_missing")
        if md.at[idx, "md_flag"] == 1: item_reasons.append("mahalanobis_extreme")
        if eo.at[idx, "odd_even_flag"] == 1: item_reasons.append("odd_even_low_both_scales")
        if long.at[idx, "longstring_flag"] == 1:
            item_reasons.extend(f"longstring:{x}" for x in long.at[idx, "longstring_trigger_blocks"].split(";") if x)
        reasons.append(";".join(item_reasons))
    result["trigger_reason"] = reasons
    return result


def make_country_summary(
    flags: pd.DataFrame, md_details: list[dict[str, Any]]
) -> pd.DataFrame:
    detail_frame = pd.DataFrame(md_details).rename(columns={"country_code": "COUNTRY_CODE"})
    summary = flags.groupby("COUNTRY_CODE", dropna=False).agg(
        n=("row_id", "size"), attention_flag_n=("attention_flag", "sum"),
        attention_number_fail_n=("attention_number_status", lambda x: int((x == "fail").sum())),
        attention_response_anomaly_n=("attention_response_status", lambda x: int((x == "anomaly").sum())),
        range_issue_n=("range_issue_flag", "sum"), md_flag_n=("md_flag", "sum"),
        odd_even_flag_n=("odd_even_flag", "sum"), longstring_flag_n=("longstring_flag", "sum"),
        mechanical_flag_n=("mechanical_flag", "sum"), high_priority_n=("review_priority", lambda x: int((x == "HIGH").sum())),
    ).reset_index()
    return summary.merge(detail_frame, on="COUNTRY_CODE", how="left").sort_values("COUNTRY_CODE")


def make_longstring_sensitivity(long: pd.DataFrame) -> dict[str, dict[str, dict[str, float | int]]]:
    """记录阈值上下各一格的标记数/比例；仅作敏感性信息，不改变正式判断。"""
    total = len(long)
    report: dict[str, dict[str, dict[str, float | int]]] = {}
    for label, (_, threshold) in LONG_BLOCKS.items():
        values = long[f"long_{label}_max_run"]
        alternatives: dict[str, dict[str, float | int]] = {}
        for candidate in (threshold - 1, threshold, threshold + 1):
            n = int((values >= candidate).fillna(False).sum())
            alternatives[str(candidate)] = {"flagged_n": n, "flagged_rate": n / total}
        report[label] = alternatives
    return report


def preflight(raw: pd.DataFrame) -> None:
    required = {"COUNTRY_CODE", "ATTCHECK_NUMBER", "ATTCHECK_RES", *ITEM_RANGES}
    missing = sorted(required.difference(raw.columns))
    if missing:
        raise ValueError("数据缺少必要列：" + ", ".join(missing))
    if len(CORE_MD_COLS) != 27:
        raise AssertionError("核心马氏距离题目数必须为 27")


def run_screening(input_path: Path = DEFAULT_INPUT, output_dir: Path = DEFAULT_OUTPUT_DIR) -> dict[str, Path]:
    input_path, output_dir = Path(input_path), Path(output_dir)
    raw = pd.read_csv(input_path, dtype=str, keep_default_na=False, encoding="utf-8")
    preflight(raw)
    original_columns = raw.columns.tolist()
    numeric, range_issues = build_calculation_frame(raw)
    attention = attention_statuses(raw)
    md, md_details = calculate_country_mahalanobis(numeric, raw["COUNTRY_CODE"])
    eo = calculate_odd_even(numeric)
    long = calculate_longstrings(numeric)
    aggregate = aggregate_flags(attention, md, eo, long)

    flags = raw.copy()
    flags.insert(0, "row_id", np.arange(1, len(raw) + 1, dtype=np.int64))
    flags["range_issue_flag"] = range_issues
    for frame in (attention, md, eo, long, aggregate):
        flags = pd.concat([flags, frame], axis=1)
    if flags.columns.duplicated().any():
        raise AssertionError("输出列名重复")
    if len(flags) != len(raw) or flags[original_columns].astype(str).equals(raw.astype(str)) is False:
        raise AssertionError("原始数据行数或原始值在内存中发生变化")

    output_dir.mkdir(parents=True, exist_ok=True)
    all_flags_path = output_dir / "tisp_mechanical_screen_flags.csv"
    summary_path = output_dir / "tisp_mechanical_screen_country_summary.csv"
    queue_path = output_dir / "tisp_mechanical_screen_review_queue.csv"
    metadata_path = output_dir / "tisp_mechanical_screen_run_metadata.json"
    flags.to_csv(all_flags_path, index=False, encoding="utf-8-sig")
    summary = make_country_summary(flags, md_details)
    summary.to_csv(summary_path, index=False, encoding="utf-8-sig")
    queue_columns = [
        "row_id", "COUNTRY_CODE", "COUNTRY_NAME", "DEM_AGE", "DEM_GENDER",
        "BENEFIT_OPEN", "TRUST_OPEN", "review_priority", "flag_count", "trigger_reason",
        "attention_number_status", "attention_response_status", "range_issue_flag",
        "md_score", "md_country_threshold", "md_flag", "trust_eo_r", "scipop_eo_r",
        "odd_even_flag", "longstring_trigger_blocks", "longstring_flag",
    ]
    queue = flags.loc[flags["review_priority"] != "NONE", [x for x in queue_columns if x in flags.columns]].copy()
    queue["final_decision"] = ""
    queue["decision_reason"] = ""
    queue["reviewer"] = ""
    queue.to_csv(queue_path, index=False, encoding="utf-8-sig")

    metadata = {
        "run_utc": datetime.now(timezone.utc).isoformat(),
        "script": str(Path(__file__).resolve()),
        "script_sha256": sha256_file(Path(__file__)),
        "input_path": str(input_path.resolve()), "input_sha256": sha256_file(input_path),
        "input_bytes": input_path.stat().st_size, "input_rows": int(len(raw)), "input_columns": int(len(raw.columns)),
        "country_n": int(raw["COUNTRY_CODE"].nunique(dropna=False)), "output_rows": int(len(flags)),
        "special_missing_tokens": sorted(SPECIAL_MISSING), "core_md_cols": CORE_MD_COLS,
        "md": {"method": "LedoitWolf by COUNTRY_CODE; sqrt(mahalanobis)", "quantile": MD_QUANTILE,
               "quantile_method": "numpy linear", "min_country_eligible_n": MIN_COUNTRY_N_FOR_MD,
               "max_missing_core_items": MAX_MD_MISSING, "country_details": md_details},
        "odd_even": {"threshold_r": 0.10, "trust_min_pairs": 4, "scipop_min_pairs": 3,
                     "family_rule": "both scales computable and r < .10"},
        "longstring": {label: {"columns": cols, "threshold": threshold} for label, (cols, threshold) in LONG_BLOCKS.items()},
        "longstring_sensitivity": make_longstring_sensitivity(long),
        "counts": {"attention_flag": int(flags["attention_flag"].sum()), "range_issue": int(flags["range_issue_flag"].sum()),
                   "md_flag": int(flags["md_flag"].sum()), "odd_even_flag": int(flags["odd_even_flag"].sum()),
                   "longstring_flag": int(flags["longstring_flag"].sum()), "mechanical_flag": int(flags["mechanical_flag"].sum()),
                   "review_queue": int(len(queue))},
        "output_files": {"all_flags": str(all_flags_path.resolve()), "country_summary": str(summary_path.resolve()),
                         "review_queue": str(queue_path.resolve())},
        "data_handling": "第一轮仅标记；未删除、未改写任何原始作答值；COUNTRY_CODE仅用于分组计算马氏距离。",
    }
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    return {"flags": all_flags_path, "summary": summary_path, "queue": queue_path, "metadata": metadata_path}


def main() -> int:
    parser = argparse.ArgumentParser(description="TISP 第一轮机械筛查：仅标记，不删除")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    paths = run_screening(args.input, args.output_dir)
    print("第一轮机械筛查完成（仅生成标记和复核队列，未删除数据）：")
    for label, path in paths.items():
        print(f"  {label}: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
