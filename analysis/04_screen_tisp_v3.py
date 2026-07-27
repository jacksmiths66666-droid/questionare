"""TISP V3 第一轮机械筛查——信号叠加方案。

两轮筛选的第一轮，自动化计算 4 个信号指标：
  ① 注意力题异常
  ② Global Longstring（全局连续同选）
  ③ 马氏距离（按国家分组）
  ④ 奇偶一致性（仅 TRUST_SCI）

输出信号叠加结果（0→NORMAL, 1→MEDIUM, ≥2→HIGH），
以及一票无效标记（全量表缺失 OR 开放题纯乱码）。
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from numpy.linalg import LinAlgError


PROJECT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = PROJECT_DIR / "D081_TISP" / "dataset.csv"
DEFAULT_OUTPUT_DIR = PROJECT_DIR / "outputs" / "screening_v3"
SPECIAL_MISSING = frozenset({"", "NA", "N/A", "-98", "-99"})

# ── 题项清单 ──────────────────────────────────────────────

SCIINFO = [
    "SCIINFO_newspapersmags", "SCIINFO_tvradio", "SCIINFO_newswebsitesapps",
    "SCIINFO_videospodcasts", "SCIINFO_filmsseries", "SCIINFO_books",
    "SCIINFO_socialmedia", "SCIINFO_messengers", "SCIINFO_museumszoos",
    "SCIINFO_rlconversations",
]
NORMPERC = [
    "NORMPERC_integrate", "NORMPERC_advocate", "NORMPERC_communicate",
    "NORMPERC_involved", "NORMPERC_outreach", "NORMPERC_independent",
]
TRUST_SCI = [
    "TRUST_SCI_expert", "TRUST_SCI_honest", "TRUST_SCI_concerned",
    "TRUST_SCI_open", "TRUST_SCI_intellig", "TRUST_SCI_ethical",
    "TRUST_SCI_improve", "TRUST_SCI_trans", "TRUST_SCI_qualified",
    "TRUST_SCI_sincere", "TRUST_SCI_otherint", "TRUST_SCI_otherviews",
]
SCIPOP = [
    "SCIPOP_common", "SCIPOP_good", "SCIPOP_advantage", "SCIPOP_cahoots",
    "SCIPOP_influence", "SCIPOP_involved", "SCIPOP_lifeexp", "SCIPOP_rely",
]
CLIM_EMO = [
    "CLIM_EMO_helpless", "CLIM_EMO_anxious", "CLIM_EMO_optimistic",
    "CLIM_EMO_angry", "CLIM_EMO_guilty", "CLIM_EMO_ashamed",
    "CLIM_EMO_depressed", "CLIM_EMO_pessimistic", "CLIM_EMO_indifferent",
]
CLIM_GOV = [
    "CLIM_GOV_concerns", "CLIM_GOV_doingenough", "CLIM_GOV_dismisspeople",
    "CLIM_GOV_science", "CLIM_GOV_futuregens", "CLIM_GOV_trustworthy",
    "CLIM_GOV_lying",
]
CLIM_WEATHERPAST = [
    "CLIM_WEATHERPAST_floods", "CLIM_WEATHERPAST_heatwaves",
    "CLIM_WEATHERPAST_heavystorms", "CLIM_WEATHERPAST_wildfires",
    "CLIM_WEATHERPAST_heavyrain", "CLIM_WEATHERPAST_droughts",
]
CLIM_WEATHERFUTU = [
    "CLIM_WEATHERFUTU_floods", "CLIM_WEATHERFUTU_heatwaves",
    "CLIM_WEATHERFUTU_heavystorms", "CLIM_WEATHERFUTU_wildfires",
    "CLIM_WEATHERFUTU_heavyrain", "CLIM_WEATHERFUTU_droughts",
]
OUTSPOKEN = ["OUTSPOKEN_othersthink", "OUTSPOKEN_isolate", "OUTSPOKEN_against"]
SDO = ["SDO_allgroupsconsider", "SDO_notpushequality", "SDO_equalityideal", "SDO_superiordominate"]

# Global Longstring 所用全部封闭题，按问卷呈现顺序排列
GLOBAL_LS_ITEMS = SCIINFO + NORMPERC + TRUST_SCI + SCIPOP + CLIM_EMO + CLIM_GOV + CLIM_WEATHERPAST + CLIM_WEATHERFUTU + OUTSPOKEN + SDO

# 马氏距离核心题集（27 题）
CORE_MD_COLS = TRUST_SCI + SCIPOP + OUTSPOKEN + SDO

# 各题取值范围
ITEM_RANGES: dict[str, tuple[int, int]] = {}
for col in SCIINFO:
    ITEM_RANGES[col] = (1, 7)
for col in NORMPERC + TRUST_SCI + SCIPOP + CLIM_EMO + CLIM_GOV + CLIM_WEATHERPAST + CLIM_WEATHERFUTU + OUTSPOKEN:
    ITEM_RANGES[col] = (1, 5)
for col in SDO:
    ITEM_RANGES[col] = (1, 10)

# ── 马氏距离参数 ──
MIN_COUNTRY_N_FOR_MD = 135
MAX_MD_MISSING = 5
MD_QUANTILE = 0.995

# 奇偶一致性阈值（数据驱动：取 r 分布底部的 1% 分位数）
ODD_EVEN_PERCENTILE = 0.01
ODD_EVEN_MIN_PAIRS = 4

# IDN/PRT 降级
VERIFY_COUNTRIES = frozenset({"IDN", "PRT"})

# 开放题列
OPEN_ENDED_COLS = ["BENEFIT_OPEN", "TRUST_OPEN"]


# ── 工具函数 ──────────────────────────────────────────────

def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def normalize_text(series: pd.Series) -> pd.Series:
    return series.astype("string").fillna("").str.strip()


def is_special_missing(text: pd.Series) -> pd.Series:
    return text.str.upper().isin(SPECIAL_MISSING)


def _shannon_entropy(s: str) -> float:
    """计算字符串的香农熵 H = -Σ p(c)·log₂(p(c))。"""
    import math
    if not s:
        return 0.0
    n = len(s)
    unique = set(s)
    if len(unique) == 1:
        return 0.0
    return -sum((s.count(c) / n) * math.log2(s.count(c) / n) for c in unique)


def is_gibberish(text: pd.Series, entropy_threshold: float | None = None) -> tuple[pd.Series, float]:
    """判定开放题是否为纯乱码（通用统计法）。

    4 个通用指标，任一达标即标记乱码：
      E: 字符熵 < 5% 分位数（数据驱动）→ 重复性乱码
      S: 符号占比 > 0.5 且长度≥3 → 纯符号乱码
      D: 数字占比 > 0.8 且长度≥5 → 纯数字乱码
      M: 含 Unicode 替换字符(\ufffd) 或高位字符占比 > 0.3 → 编码乱码

    返回：(is_gibberish_mask, entropy_threshold)
    """
    trimmed = normalize_text(text)
    empty = trimmed == ""
    no_spaces = trimmed.str.replace(r"\s", "", regex=True)
    n = no_spaces.str.len()

    # 指标 E: 字符熵（仅长度≥5 的文本）
    long_text = n >= 5
    entropy = pd.Series(np.nan, index=text.index)
    entropy[long_text] = no_spaces[long_text].apply(_shannon_entropy)
    valid_entropy = entropy[~entropy.isna()]

    if entropy_threshold is None:
        if len(valid_entropy) > 0:
            entropy_threshold = float(np.quantile(valid_entropy, 0.05))
        else:
            entropy_threshold = -1.0
    rE = entropy.notna() & (entropy <= entropy_threshold)

    # 指标 S: 符号占比（长度≥3）
    def symbol_ratio(s: str) -> float:
        if not s:
            return 0.0
        sym_count = sum(1 for c in s if not c.isalnum())
        return sym_count / len(s)
    sym_ratio = no_spaces.apply(symbol_ratio)
    rS = (sym_ratio > 0.5) & (n >= 3)

    # 指标 D: 数字占比（长度≥5）
    def digit_ratio(s: str) -> float:
        if not s:
            return 0.0
        dig_count = sum(1 for c in s if c.isdigit())
        return dig_count / len(s)
    dig_ratio = no_spaces.apply(digit_ratio)
    rD = (dig_ratio > 0.8) & (n >= 5)

    # 指标 M: 编码乱码
    def has_encoding_garble(s: str) -> bool:
        if not s:
            return False
        if '\ufffd' in s:
            return True
        high_count = sum(1 for c in s if ord(c) > 0x00FF and c.isalpha())
        return high_count >= 3 and high_count / len(s) > 0.3
    rM = no_spaces.apply(has_encoding_garble)

    is_gib = (rE | rS | rD | rM) & (~empty)
    return pd.Series(is_gib, index=text.index), entropy_threshold


def numeric_with_range(raw: pd.Series, low: int, high: int) -> pd.Series:
    """转换为数值，约定缺失和越界值变为 NaN。"""
    text = normalize_text(raw)
    is_special = is_special_missing(text)
    numeric = pd.to_numeric(text.where(~is_special), errors="coerce").astype(float)
    range_bad = (~is_special) & (numeric.isna() | (numeric < low) | (numeric > high))
    numeric = numeric.where(~range_bad)
    return numeric


def build_calculation_frame(raw: pd.DataFrame) -> pd.DataFrame:
    """建立全部封闭题的计算副本。"""
    numeric: dict[str, pd.Series] = {}
    for col, (low, high) in ITEM_RANGES.items():
        numeric[col] = numeric_with_range(raw[col], low, high)
    return pd.DataFrame(numeric, index=raw.index)


# ── 指标 ① 注意力题异常 ──────────────────────────────────

def compute_attention_signals(raw: pd.DataFrame, numeric: pd.DataFrame) -> pd.DataFrame:
    """计算注意力题异常信号。

    规则：
      - 数字题≠213 或 结果题≠1 → 记 1 次信号
      - IDN/PRT 的结果题异常 → 降级为 VERIFY（不记信号）
      - IDN/PRT 的数字题异常 → 降级为 VERIFY

    返回列：signal_attention, attention_verification, 等
    """
    num_raw = normalize_text(raw["ATTCHECK_NUMBER"])
    res_raw = normalize_text(raw["ATTCHECK_RES"])
    country = normalize_text(raw["COUNTRY_CODE"])

    # 数字题：正确答案 213
    num_fail = (~is_special_missing(num_raw)) & (num_raw != "213")
    # 结果题：正确答案 1
    res_val = pd.to_numeric(res_raw.where(~is_special_missing(res_raw)), errors="coerce")
    res_fail = res_val.notna() & (res_val != 1)

    # 任一失败即视为注意力异常
    any_fail = num_fail | res_fail

    # IDN/PRT 降级
    is_verify = any_fail & country.isin(VERIFY_COUNTRIES)

    result = pd.DataFrame(index=raw.index)
    result["attention_number_fail"] = num_fail.astype("int8")
    result["attention_response_fail"] = res_fail.astype("int8")
    result["attention_any_fail"] = any_fail.astype("int8")
    result["attention_verification"] = is_verify.astype("int8")
    # 记信号：任一失败 且 非降级国家
    result["signal_attention"] = (any_fail & ~is_verify).astype("int8")
    return result


# ── 指标 ② Global Longstring ─────────────────────────────

def longest_run_length(values: np.ndarray) -> int:
    """一维数组中最长连续相同值长度（缺失即打断）。"""
    best = 0
    current = 0
    prev = None
    for v in values:
        if pd.isna(v):
            current = 0
            prev = None
            continue
        if current > 0 and v == prev:
            current += 1
        else:
            current = 1
        if current > best:
            best = current
        prev = v
    return best


def compute_longstring_signals(numeric: pd.DataFrame) -> pd.DataFrame:
    """计算全局 Longstring 信号。

    阈值：数据驱动 — 99 分位数。
    """
    array = numeric[GLOBAL_LS_ITEMS].to_numpy(dtype=float)
    runs = np.array([longest_run_length(row) for row in array], dtype=float)

    threshold = float(np.quantile(runs, 0.99))

    result = pd.DataFrame(index=numeric.index)
    result["ls_max_run"] = runs
    result["ls_threshold"] = threshold
    result["signal_longstring"] = (runs >= threshold).astype("int8")
    return result


# ── 指标 ③ 马氏距离 ──────────────────────────────────────

def _quantile(values: np.ndarray, q: float) -> float:
    try:
        return float(np.quantile(values, q, method="linear"))
    except TypeError:
        return float(np.quantile(values, q, interpolation="linear"))


def compute_md_signals(numeric: pd.DataFrame, countries: pd.Series) -> tuple[pd.DataFrame, list[dict]]:
    """按国家计算马氏距离信号。

    27 核心题、corrcoef + solve、0.995 分位数阈值（数据驱动）。
    """
    result = pd.DataFrame(index=numeric.index)
    result["md_score"] = np.nan
    result["md_threshold"] = np.nan
    result["md_flag"] = 0
    result["md_not_computable"] = 0
    result["signal_mahalanobis"] = 0

    details: list[dict] = []
    country_key = normalize_text(countries).replace("", "__MISSING_COUNTRY__")

    for country, idx_group in country_key.groupby(country_key, sort=True).groups.items():
        idx = pd.Index(idx_group)
        block = numeric.loc[idx, CORE_MD_COLS]
        eligible = block.notna().sum(axis=1) >= (len(CORE_MD_COLS) - MAX_MD_MISSING)
        too_missing_idx = eligible.index[~eligible]
        result.loc[too_missing_idx, "md_not_computable"] = 1

        use_idx = eligible.index[eligible]
        detail: dict = {
            "country_code": str(country), "country_n": int(len(idx)),
            "eligible_n": int(len(use_idx)), "computable": False,
            "reason": "", "threshold_p995": None,
        }

        if len(use_idx) < MIN_COUNTRY_N_FOR_MD:
            result.loc[use_idx, "md_not_computable"] = 1
            detail["reason"] = "eligible_sample_below_135"
            details.append(detail)
            continue

        working = block.loc[use_idx].copy()
        working = working.fillna(working.median(axis=0))
        std = working.std(axis=0, ddof=0)
        usable_cols = std.index[std > 0].tolist()
        if len(usable_cols) < 10:
            result.loc[use_idx, "md_not_computable"] = 1
            detail["reason"] = "fewer_than_10_nonconstant_items"
            details.append(detail)
            continue

        arr = working[usable_cols].values
        z = (arr - arr.mean(axis=0)) / arr.std(axis=0, ddof=0)
        try:
            R = np.corrcoef(arr, rowvar=False)
            distances = np.sqrt(np.sum(z * np.linalg.solve(R, z.T).T, axis=1))
        except LinAlgError as exc:
            result.loc[use_idx, "md_not_computable"] = 1
            detail["reason"] = f"corr_singular:{type(exc).__name__}"
            details.append(detail)
            continue

        threshold = _quantile(distances, MD_QUANTILE)
        flags = distances > threshold
        result.loc[use_idx, "md_score"] = distances
        result.loc[idx, "md_threshold"] = threshold
        result.loc[use_idx, "md_flag"] = flags.astype("int8")
        result.loc[use_idx, "signal_mahalanobis"] = flags.astype("int8")
        detail.update({
            "computable": True, "reason": "", "threshold_p995": threshold,
            "flagged_n": int(flags.sum()),
        })
        details.append(detail)

    return result, details


# ── 指标 ④ 奇偶一致性（仅 TRUST_SCI）─────────────────────

def compute_odd_even_signals(numeric: pd.DataFrame) -> pd.DataFrame:
    """计算 TRUST_SCI 奇偶一致性。

    按原题序（第1/2, 3/4, ...）做配对 Pearson r。
    阈值取 r 分布底部 ODD_EVEN_PERCENTILE 分位数（数据驱动）。
    """
    result = pd.DataFrame(index=numeric.index)
    array = numeric[TRUST_SCI].to_numpy(dtype=float)
    left, right = array[:, 0::2], array[:, 1::2]
    keep = ~(np.isnan(left) | np.isnan(right))
    n_pairs = keep.sum(axis=1)
    x = np.where(keep, left, 0.0)
    y = np.where(keep, right, 0.0)
    sx, sy = x.sum(axis=1), y.sum(axis=1)
    sxx, syy, sxy = (x * x).sum(axis=1), (y * y).sum(axis=1), (x * y).sum(axis=1)
    numerator = n_pairs * sxy - sx * sy
    denominator_sq = (n_pairs * sxx - sx * sx) * (n_pairs * syy - sy * sy)
    valid = (n_pairs >= ODD_EVEN_MIN_PAIRS) & (denominator_sq > 0)
    r_values = np.full(len(array), np.nan)
    r_values[valid] = numerator[valid] / np.sqrt(denominator_sq[valid])

    # 数据驱动阈值：取有效 r 的底部百分位数
    valid_r = r_values[valid]
    if len(valid_r) > 0:
        threshold = float(np.quantile(valid_r, ODD_EVEN_PERCENTILE))
    else:
        threshold = -1.0

    result["oe_r"] = r_values
    result["oe_pairs_n"] = n_pairs
    result["oe_not_computable"] = (~valid).astype("int8")
    result["oe_threshold"] = threshold
    result["signal_odd_even"] = ((r_values <= threshold) & valid).astype("int8")
    return result


# ── 一票无效 ──────────────────────────────────────────────

def compute_one_vote_veto(raw: pd.DataFrame) -> tuple[pd.DataFrame, float]:
    """一票无效检查：全量表缺失 OR 开放题纯乱码。

    返回：(veto_df, entropy_threshold)
    """
    result = pd.DataFrame(index=raw.index)

    # 全量表缺失：所有封闭题均为空/约定缺失
    closed_cols = list(ITEM_RANGES)
    text = raw[closed_cols].astype("string").fillna("")
    is_empty_mask = text.apply(lambda s: s.str.strip().eq("") | s.str.upper().isin(SPECIAL_MISSING))
    all_missing = is_empty_mask.all(axis=1)
    result["veto_all_missing"] = all_missing.astype("int8")

    # 开放题纯乱码（逐列检测，任一列乱码即标记）
    open_cols_exist = [c for c in OPEN_ENDED_COLS if c in raw.columns]
    entropy_threshold = -1.0
    if open_cols_exist:
        gibberish = pd.DataFrame(index=raw.index)
        for col in open_cols_exist:
            gib_mask, entropy_threshold = is_gibberish(raw[col])
            gibberish[col] = gib_mask
        result["veto_gibberish"] = gibberish.any(axis=1).astype("int8")
    else:
        result["veto_gibberish"] = 0

    result["veto_any"] = (result["veto_all_missing"] | result["veto_gibberish"]).astype("int8")
    return result, entropy_threshold


# ── 信号叠加 ──────────────────────────────────────────────

def stack_signals(attention: pd.DataFrame, longstring: pd.DataFrame, md: pd.DataFrame, odd_even: pd.DataFrame) -> pd.DataFrame:
    """叠加 4 个信号，输出可疑等级。

    规则：
      0 信号 → NORMAL（不进复核）
      1 信号 → MEDIUM
      ≥2 信号 → HIGH

    同时生成 trigger_reason 列（触发原因说明）。
    """
    result = pd.DataFrame(index=attention.index)
    signals = pd.DataFrame({
        "attention": attention["signal_attention"],
        "longstring": longstring["signal_longstring"],
        "mahalanobis": md["signal_mahalanobis"],
        "odd_even": odd_even["signal_odd_even"],
    }, index=attention.index).astype("int8")

    result["signal_count"] = signals.sum(axis=1).astype("int8")
    result["screening_tier"] = np.select(
        [result["signal_count"] >= 2, result["signal_count"] == 1],
        ["HIGH", "MEDIUM"], default="NORMAL",
    )

    # 生成 trigger_reason
    def make_trigger_reason(row):
        reasons = []
        if row["attention"] == 1:
            reasons.append("attention_fail")
        if row["longstring"] == 1:
            reasons.append("longstring_exceed")
        if row["mahalanobis"] == 1:
            reasons.append("mahalanobis_outlier")
        if row["odd_even"] == 1:
            reasons.append("odd_even_low")
        return ";".join(reasons)
    result["trigger_reason"] = signals.apply(make_trigger_reason, axis=1)

    return result


# ── 主流程 ────────────────────────────────────────────────

def preflight(raw: pd.DataFrame) -> None:
    required = {"COUNTRY_CODE", "ATTCHECK_NUMBER", "ATTCHECK_RES", *ITEM_RANGES}
    missing = sorted(required.difference(raw.columns))
    if missing:
        raise ValueError("数据缺少必要列：" + ", ".join(missing))


def run_screening(input_path: Path = DEFAULT_INPUT, output_dir: Path = DEFAULT_OUTPUT_DIR) -> dict[str, Path]:
    input_path, output_dir = Path(input_path), Path(output_dir)
    raw = pd.read_csv(input_path, dtype=str, keep_default_na=False, encoding="utf-8")
    preflight(raw)
    original_columns = raw.columns.tolist()

    # 建立计算副本
    numeric = build_calculation_frame(raw)

    # 4 个信号并行计算
    attention = compute_attention_signals(raw, numeric)
    longstring = compute_longstring_signals(numeric)
    md, md_details = compute_md_signals(numeric, raw["COUNTRY_CODE"])
    odd_even = compute_odd_even_signals(numeric)

    # 信号叠加
    stacking = stack_signals(attention, longstring, md, odd_even)

    # 一票无效
    veto, entropy_threshold = compute_one_vote_veto(raw)

    # VERIFY 标记（IDN/PRT 降级 + MD 不可计算等记录备忘）
    is_verify = attention["attention_verification"] == 1

    # ── 组装输出 ──
    flags = raw.copy()
    flags.insert(0, "row_id", np.arange(1, len(raw) + 1, dtype=np.int64))

    for frame in (attention, longstring, md, odd_even, stacking, veto):
        flags = pd.concat([flags, frame], axis=1)

    flags["is_verify"] = is_verify.astype("int8")
    flags["entropy_threshold"] = entropy_threshold

    if flags.columns.duplicated().any():
        raise AssertionError("输出列名重复")
    if len(flags) != len(raw) or flags[original_columns].astype(str).equals(raw.astype(str)) is False:
        raise AssertionError("原始数据行数或原始值在内存中发生变化")

    # ── 写入 ──
    output_dir.mkdir(parents=True, exist_ok=True)
    flags_path = output_dir / "tisp_v3_flags.csv"
    summary_path = output_dir / "tisp_v3_signal_summary.csv"
    queue_path = output_dir / "tisp_v3_review_queue.csv"
    metadata_path = output_dir / "tisp_v3_metadata.json"

    flags.to_csv(flags_path, index=False, encoding="utf-8-sig")

    # 国家汇总
    summary = flags.groupby("COUNTRY_CODE", dropna=False).agg(
        n=("row_id", "size"),
        signal_attention_n=("signal_attention", "sum"),
        signal_longstring_n=("signal_longstring", "sum"),
        signal_mahalanobis_n=("signal_mahalanobis", "sum"),
        signal_odd_even_n=("signal_odd_even", "sum"),
        normal_n=("screening_tier", lambda x: int((x == "NORMAL").sum())),
        medium_n=("screening_tier", lambda x: int((x == "MEDIUM").sum())),
        high_n=("screening_tier", lambda x: int((x == "HIGH").sum())),
        veto_n=("veto_any", "sum"),
        verify_n=("is_verify", "sum"),
    ).reset_index()
    summary.to_csv(summary_path, index=False, encoding="utf-8-sig")

    # 复核队列（MEDIUM + HIGH + VERIFY，排除一票无效）
    in_queue = ((flags["screening_tier"] != "NORMAL") | (flags["is_verify"] == 1)) & (flags["veto_any"] == 0)
    queue_cols = [
        "row_id", "COUNTRY_CODE", "COUNTRY_NAME",
        "screening_tier", "signal_count", "is_verify",
        "trigger_reason",
        "signal_attention", "signal_longstring", "signal_mahalanobis", "signal_odd_even",
        "veto_any", "veto_all_missing", "veto_gibberish",
        "attention_number_fail", "attention_response_fail", "attention_any_fail",
        "ls_max_run", "md_score", "oe_r",
        "BENEFIT_OPEN", "TRUST_OPEN",
        "ATTCHECK_NUMBER", "ATTCHECK_RES",
        "DEM_AGE", "DEM_GENDER", "DEM_EDU", "DEM_AGEGRP",
        "COUNTRY_CONT",
    ]
    queue = flags.loc[in_queue, [c for c in queue_cols if c in flags.columns]].copy()
    queue["final_decision"] = ""
    queue.to_csv(queue_path, index=False, encoding="utf-8-sig")

    # 元数据
    metadata = {
        "run_utc": datetime.now(timezone.utc).isoformat(),
        "script": str(Path(__file__).resolve()),
        "script_sha256": sha256_file(Path(__file__)),
        "input_path": str(input_path.resolve()),
        "input_sha256": sha256_file(input_path),
        "input_rows": int(len(raw)),
        "input_columns": int(len(raw.columns)),
        "country_n": int(raw["COUNTRY_CODE"].nunique(dropna=False)),
        "params": {
            "md": {
                "core_items": CORE_MD_COLS,
                "min_country_n": MIN_COUNTRY_N_FOR_MD,
                "max_missing": MAX_MD_MISSING,
                "quantile": MD_QUANTILE,
                "method": "corrcoef per country; sqrt(mahalanobis)",
            },
            "global_longstring": {
                "n_items": len(GLOBAL_LS_ITEMS),
                "threshold_method": "0.99 quantile (data-driven)",
                "threshold_value": float(flags["ls_threshold"].iloc[0]),
            },
            "odd_even": {
                "scale": "TRUST_SCI",
                "percentile": ODD_EVEN_PERCENTILE,
                "min_pairs": ODD_EVEN_MIN_PAIRS,
                "threshold_value": float(flags["oe_threshold"].iloc[0]),
            },
            "attention": {
                "verify_countries": sorted(VERIFY_COUNTRIES),
                "rule": "ATTCHECK_NUMBER!=213 OR ATTCHECK_RES!=1 → signal; IDN/PRT → verify",
            },
            "signal_stacking": {
                "0": "NORMAL (no review)",
                "1": "MEDIUM",
                ">=2": "HIGH",
            },
            "one_vote_veto": {
                "all_missing": "all closed-end items empty",
                "gibberish": "entropy<5pct | symbol_ratio>0.5 | digit_ratio>0.8 | encoding_garble",
                "gibberish_entropy_threshold": float(flags["entropy_threshold"].iloc[0]) if "entropy_threshold" in flags.columns else None,
            },
        },
        "counts": {
            "signal_attention": int(flags["signal_attention"].sum()),
            "signal_longstring": int(flags["signal_longstring"].sum()),
            "signal_mahalanobis": int(flags["signal_mahalanobis"].sum()),
            "signal_odd_even": int(flags["signal_odd_even"].sum()),
            "normal": int((flags["screening_tier"] == "NORMAL").sum()),
            "medium": int((flags["screening_tier"] == "MEDIUM").sum()),
            "high": int((flags["screening_tier"] == "HIGH").sum()),
            "veto": int(flags["veto_any"].sum()),
            "verify": int(flags["is_verify"].sum()),
            "review_queue": int(len(queue)),
        },
        "md_country_details": md_details,
        "output_files": {
            "flags": str(flags_path.resolve()),
            "summary": str(summary_path.resolve()),
            "review_queue": str(queue_path.resolve()),
        },
    }
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8"
    )

    return {"flags": flags_path, "summary": summary_path, "queue": queue_path, "metadata": metadata_path}


def main() -> int:
    parser = argparse.ArgumentParser(description="TISP V3 第一轮机械筛查（信号叠加方案）")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    paths = run_screening(args.input, args.output_dir)
    print("V3 第一轮机械筛查完成（信号叠加方案）：")
    for label, path in paths.items():
        print(f"  {label}: {path}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
