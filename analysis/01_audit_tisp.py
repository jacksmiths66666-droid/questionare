"""第一阶段：只检查 TISP 数据，不修改、不删除任何记录。"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "D081_TISP" / "dataset.csv"
OUT = ROOT / "outputs" / "audit"

MISSING_TOKENS = {"", "NA", "N/A", "na", "n/a", "-99", "-98"}


def clean_text(series: pd.Series) -> pd.Series:
    """将列转成便于审计的字符串；不改变原始 df。"""
    return series.astype("string").str.strip()


def numeric_view(series: pd.Series) -> pd.Series:
    """把逗号小数和普通数字临时转成数字，仅用于检查。"""
    text = clean_text(series).str.replace(",", ".", regex=False)
    return pd.to_numeric(text, errors="coerce")


def missing_mask(series: pd.Series) -> pd.Series:
    text = clean_text(series)
    return series.isna() | text.isin(MISSING_TOKENS)


def range_spec(columns: list[str]) -> dict[str, tuple[float, float, str]]:
    specs: dict[str, tuple[float, float, str]] = {}

    def add(prefixes: list[str], low: float, high: float, label: str) -> None:
        for col in columns:
            if any(col == prefix or col.startswith(prefix) for prefix in prefixes):
                specs[col] = (low, high, label)

    add(["SCIINFO_", "SCIENGAGE_"], 1, 7, "1-7")
    add(["BENEFIT_ONESELF", "GOALS_PRIO_", "GOALS_TACKLE_", "NORMPERC_",
         "WILLVUL_", "TRUST_SCI_", "TRUST_METHOD", "TRUST_PEW",
         "OUTSPOKEN_", "SCIPOP_", "CLIM_TRUST", "CLIM_EMO_",
         "CLIM_GOV_", "CLIM_WEATHERPAST_", "CLIM_WEATHERFUTU_",
         "DEM_POL_", "DEM_RELIGIOUS"], 1, 5, "1-5")
    add(["BENEFIT_REGION_MOST", "BENEFIT_REGION_LEAST"], 1, 6, "1-6")
    add(["CLIM_POLSUPPORT_"], 1, 4, "1-4")
    add(["SDO_"], 1, 10, "1-10")
    add(["DEM_GENDER"], 0, 2, "0-2")
    # 这些是衍生/开放文本列，不按性别分类变量的数值范围检查。
    specs.pop("DEM_GENDER_2_TEXT", None)
    specs["DEM_GENDER_male"] = (0, 1, "0-1")
    add(["DEM_EDU"], 1, 4, "1-4")
    add(["DEM_RESIDENCE", "DEM_EDU_uni"], 0, 1, "0-1")
    add(["ATTCHECK_RES"], 1, 5, "1-5")
    return specs


def audit_ranges(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for col, (low, high, label) in range_spec(list(df.columns)).items():
        raw = df[col]
        missing = missing_mask(raw)
        numbers = numeric_view(raw)
        nonmissing = ~missing
        nonnumeric = nonmissing & numbers.isna()
        invalid = nonmissing & (nonnumeric | (numbers < low) | (numbers > high))
        observed = numbers[nonmissing & numbers.notna()]
        rows.append({
            "column": col,
            "expected_range": label,
            "missing_n": int(missing.sum()),
            "nonnumeric_n": int(nonnumeric.sum()),
            "out_of_range_n": int(invalid.sum()),
            "observed_min": None if observed.empty else float(observed.min()),
            "observed_max": None if observed.empty else float(observed.max()),
        })
    return pd.DataFrame(rows).sort_values(["out_of_range_n", "column"], ascending=[False, True])


def attention_audit(df: pd.DataFrame) -> pd.DataFrame:
    number = clean_text(df["ATTCHECK_NUMBER"])
    result = numeric_view(df["ATTCHECK_RES"])
    result[missing_mask(df["ATTCHECK_RES"])] = float("nan")
    frame = pd.DataFrame({"country_code": df["COUNTRY_CODE"], "number": number, "result": result})
    rows = []
    for country, group in frame.groupby("country_code", dropna=False):
        rows.append({
            "country_code": country,
            "n": int(len(group)),
            "number_213_n": int((group["number"] == "213").sum()),
            "number_not_213_n": int((group["number"] != "213").sum()),
            "result_1_n": int((group["result"] == 1).sum()),
            "result_not_1_n": int((group["result"] != 1).sum()),
            "number_missing_n": int(group["number"].isin(MISSING_TOKENS).sum()),
            "result_missing_n": int(group["result"].isna().sum()),
        })
    return pd.DataFrame(rows).sort_values("country_code")


def main() -> None:
    if not INPUT.exists():
        raise FileNotFoundError(f"找不到输入文件：{INPUT}")
    OUT.mkdir(parents=True, exist_ok=True)

    # dtype=object 保留原始编码；本脚本只在临时 Series 上做数字转换。
    df = pd.read_csv(INPUT, dtype=object, keep_default_na=False)

    column_rows = []
    for col in df.columns:
        raw = df[col]
        miss = missing_mask(raw)
        numbers = numeric_view(raw)
        nonmissing = ~miss
        column_rows.append({
            "column": col,
            "dtype_read_as": str(raw.dtype),
            "n": int(len(raw)),
            "missing_or_special_n": int(miss.sum()),
            "missing_or_special_pct": round(float(miss.mean()), 6),
            "numeric_parseable_n": int((nonmissing & numbers.notna()).sum()),
            "unique_nonmissing_n": int(raw[nonmissing].nunique(dropna=True)),
        })

    column_audit = pd.DataFrame(column_rows).sort_values(
        ["missing_or_special_pct", "column"], ascending=[False, True]
    )
    column_audit.to_csv(OUT / "column_audit.csv", index=False, encoding="utf-8-sig")

    country_counts = (
        df["COUNTRY_CODE"].value_counts(dropna=False)
        .rename_axis("country_code")
        .reset_index(name="n")
        .sort_values("country_code")
    )
    country_counts.to_csv(OUT / "country_counts.csv", index=False, encoding="utf-8-sig")

    ranges = audit_ranges(df)
    ranges.to_csv(OUT / "range_audit.csv", index=False, encoding="utf-8-sig")

    attention = attention_audit(df)
    attention.to_csv(OUT / "attention_audit.csv", index=False, encoding="utf-8-sig")

    consent = numeric_view(df["CONSENT"])
    age = numeric_view(df["DEM_AGE"])
    attention_result = numeric_view(df["ATTCHECK_RES"])
    attention_result[missing_mask(df["ATTCHECK_RES"])] = float("nan")
    overview = {
        "input": str(INPUT),
        "rows": int(len(df)),
        "columns": int(len(df.columns)),
        "countries": int(df["COUNTRY_CODE"].nunique(dropna=True)),
        "consent_not_1_n": int((consent != 1).sum()),
        "age_below_18_n": int((age < 18).sum()),
        "age_above_100_n": int((age > 100).sum()),
        "age_missing_or_unparseable_n": int(age.isna().sum()),
        "attention_number_not_213_n": int((clean_text(df["ATTCHECK_NUMBER"]) != "213").sum()),
        "attention_result_not_1_n": int(((attention_result.notna()) & (attention_result != 1)).sum()),
        "attention_result_missing_n": int(attention_result.isna().sum()),
        "benefit_open_missing_n": int(missing_mask(df["BENEFIT_OPEN"]).sum()),
        "trust_open_missing_n": int(missing_mask(df["TRUST_OPEN"]).sum()),
        "note": "本报告只审计，不修改、不删除任何记录。",
    }
    (OUT / "overview.json").write_text(
        json.dumps(overview, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(json.dumps(overview, ensure_ascii=False, indent=2))
    print(f"审计文件已写入：{OUT}")


if __name__ == "__main__":
    main()
