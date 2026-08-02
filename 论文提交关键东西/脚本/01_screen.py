# -*- coding: utf-8 -*-
"""D087 阶段 1｜信号筛选（论文提交包版）

对应 docs/review_rules_full.md 第〇节；阈值与 analysis/02_机械筛选.py 定标一致。
输出：data/signals.csv（全量 2,159 行 + 信号标记列）

用法（在包内执行，路径相对本包）：python 脚本/01_screen.py
"""

import sys
import io
from pathlib import Path

import numpy as np
import pandas as pd

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "data"
SRC = BASE / "原始数据dataset.csv"

LIKERT5 = {
    "Strongly disagree": 1, "Disagree": 2, "Neither agree nor disagree": 3,
    "Agree": 4, "Strongly agree": 5,
}
FREQ5 = {
    "Never": 1, "Less (almost never)": 2, "1 or 2 days/weekends": 3,
    "3 or 4 days (quite a lot)": 4, "Everyday or almost everyday (5-7)": 5,
}
FREQ_SM = {
    "Never": 1, "Less frequently": 2, "1-2 days a week/weekends": 3,
    "3-4 days a week": 4, "Every or almost every day": 5,
}
ORD4_MAP = {
    "P01":  {"Not at all": 1, "Hardly": 2, "Quite": 3, "Very": 4},
    "P04":  {"Not at all": 1, "Hardly": 2, "Quite": 3, "Very": 4},
    "P06":  {"Not capable": 1, "Little": 2, "Quite": 3, "Very capable": 4},
    "P07B": {"No interest": 1, "Hardly": 2, "Quite": 3, "A lot": 4},
    "P07D1": {"Not at all": 1, "Little": 2, "Quite": 3, "Very often": 4},
    "P07D2": {"Not at all": 1, "Little": 2, "Quite": 3, "Very often": 4},
    "P07D3": {"Not at all": 1, "Little": 2, "Quite": 3, "Very often": 4},
    "P07D4": {"Not at all": 1, "Little": 2, "Quite": 3, "Very often": 4},
    "P08":  {"Not at all necessary": 1, "Not very necessary": 2,
             "Quite necessary": 3, "Very necessary": 4},
    "P10B": {"No capable": 1, "Not very capable": 2,
             "Quite capable": 3, "Very capable": 4},
}
DKNA_SET = {
    "DK", "NA", "NC", "NS",
    "Can't say", "Can't remember", "No memories",
    "Doesn't use social networks", "Doesn't have social networks", "Have no networks",
    "",
}
LS_ITEMS = [
    ("P01",  ORD4_MAP["P01"],  4, False),
    ("P02A", FREQ5, 5, False), ("P02B", FREQ5, 5, False),
    ("P02C", FREQ5, 5, False), ("P02D", FREQ5, 5, False), ("P02E", FREQ5, 5, False),
    ("P04",  ORD4_MAP["P04"],  4, False),
    ("P06",  ORD4_MAP["P06"],  4, False),
    ("P07B", ORD4_MAP["P07B"], 4, False),
    ("P07D1", ORD4_MAP["P07D1"], 4, False), ("P07D2", ORD4_MAP["P07D2"], 4, False),
    ("P07D3", ORD4_MAP["P07D3"], 4, False), ("P07D4", ORD4_MAP["P07D4"], 4, False),
    ("P08",  ORD4_MAP["P08"],  4, False),
    ("P10B", ORD4_MAP["P10B"], 4, False),
    ("P11A", LIKERT5, 5, True), ("P11B", LIKERT5, 5, False),
    ("P11C", LIKERT5, 5, False), ("P11D", LIKERT5, 5, False), ("P11E", LIKERT5, 5, False),
    ("P21A", FREQ_SM, 5, False),
]
CORE_VARS = [
    "P01", "P02A", "P02B", "P02C", "P02D", "P02E",
    "P03", "P04", "P05", "P06",
    "P07", "P07B", "P07D1", "P07D2", "P07D3", "P07D4", "P07D5", "P07D6",
    "P08", "P09", "P09B", "P10B",
    "P11A", "P11B", "P11C", "P11D", "P11E",
    "P12", "P13", "P13B", "P13C",
    "P14", "P15", "P16", "P17", "P17B", "P17C",
    "P18", "P19", "P19B", "P20", "P20B",
    "P21A", "P21B", "P21C", "P21D", "P22", "P23", "P24", "P25",
    "P27", "P27B", "P27C", "P28", "P28B",
]

# 定标阈值（与 analysis/02_机械筛选.py THRESHOLDS 一致，2026-08-02）
DUR_Q, MD_Q, LS_K, DKNA_K, DUR_HIGH_Q = 0.10, 0.95, 6, 4, 0.99


def dkna_count(df):
    return df[CORE_VARS].apply(
        lambda row: sum(1 for v in row if isinstance(v, str) and v.strip() in DKNA_SET), axis=1)


def longstring_runs(df):
    encoded = pd.DataFrame(index=df.index, columns=[c for c, _, _, _ in LS_ITEMS], dtype=float)
    for col, dmap, max_val, rev in LS_ITEMS:
        v = df[col].map(dmap)
        if rev:
            v = max_val + 1 - v
        encoded[col] = round(v / max_val, 1)
    runs = []
    for _, row in encoded.iterrows():
        vals = row.dropna().values
        if len(vals) < 11:
            runs.append(0)
            continue
        mx = cur = 1
        for k in range(1, len(vals)):
            cur = cur + 1 if vals[k] == vals[k - 1] else 1
            mx = max(mx, cur)
        runs.append(mx)
    return pd.Series(runs, index=df.index)


def mahalanobis_sq(df):
    enc = pd.DataFrame(index=df.index)
    for col in ["P11A", "P11B", "P11C", "P11D", "P11E"]:
        v = df[col].map(LIKERT5)
        if col == "P11A":
            v = 6 - v
        enc[col] = v
    complete = enc.dropna()
    if len(complete) == 0:
        return pd.Series(np.nan, index=df.index)
    mu = complete.mean()
    cov = complete.cov()
    try:
        inv = np.linalg.inv(cov.values)
    except np.linalg.LinAlgError:
        inv = np.linalg.pinv(cov.values)
    diff = (complete - mu).values
    d2 = np.einsum("ij,jk,ik->i", diff, inv, diff)
    out = pd.Series(np.nan, index=df.index)
    out.loc[complete.index] = d2
    return out


def main():
    en = pd.read_csv(SRC, encoding="utf-8-sig")
    en["row_id"] = en["ID"].astype(str)
    n_all = len(en)
    print(f"载入: {n_all} 行 × {len(en.columns)} 列")

    # ---------- 通道二：一票否决（跳题违规 R1/R2）----------
    r1 = (en["P12"] == "No") & en["P12Btx"].notna() & (en["P12Btx"].astype(str).str.strip() != "")
    r2 = (~en["P27"].isin(["Yes", ""])) & en["P27C"].isin(["Man", "Woman"])
    veto = (r1 | r2).values
    print(f"通道二 跳题违规: {veto.sum()}（R1={r1.sum()} + R2={r2.sum()}）→ 直接剔除，不计信号")

    # ---------- 通道一：四信号（仅非跳题样本）----------
    w = en[~veto].copy()
    w["DKNA_count"] = dkna_count(w)
    w["LS_run"] = longstring_runs(w)
    w["MD_d2"] = mahalanobis_sq(w)
    w["DUR"] = pd.to_numeric(w["DUR"], errors="coerce")
    mode_of = w["MODE"].where(w["MODE"].isin(["CATI", "CAWI"]), "CAWI")
    w["_mode"] = mode_of

    dur_short_thr = w.groupby(mode_of)["DUR"].quantile(DUR_Q).to_dict()
    dur_high_thr = w["DUR"].quantile(DUR_HIGH_Q)
    md_thr = w["MD_d2"].quantile(MD_Q)

    w["flag_dur_low"] = (w["DUR"] < w["_mode"].map(pd.Series(dur_short_thr))).astype(int)
    w["flag_dur_high"] = (w["DUR"] > dur_high_thr).astype(int)
    w["flag_md"] = ((w["MD_d2"] > md_thr) & w["MD_d2"].notna()).astype(int)
    w["flag_long"] = ((w["LS_run"] >= LS_K) & (w["LS_run"] > 0)).astype(int)
    w["flag_dkna"] = (w["DKNA_count"] >= DKNA_K).astype(int)
    w["CI"] = (w["flag_dur_low"] + w["flag_dur_high"] + w["flag_md"] +
               w["flag_long"] + w["flag_dkna"])

    def trigger(sig):
        parts = []
        if sig["flag_dur_low"]:  parts.append("DUR_short")
        if sig["flag_dur_high"]: parts.append("DUR_long")
        if sig["flag_md"]:       parts.append("MD")
        if sig["flag_long"]:     parts.append("longstring")
        if sig["flag_dkna"]:     parts.append("DKNA")
        return "+".join(parts) if parts else ""

    w["trigger_reason"] = w.apply(trigger, axis=1)
    w["screening_tier"] = np.where(w["CI"] >= 2, "HIGH",
                          np.where(w["CI"] == 1, "MEDIUM", "NORMAL"))
    w["signal_count"] = w["CI"].astype(int)

    # ---------- 合并回全量（跳题行：信号列置 0，veto_any=1）----------
    flag_cols = ["flag_dur_low", "flag_dur_high", "flag_md", "flag_long", "flag_dkna"]
    sig = en.copy()
    sig["veto_any"] = 0
    sig = sig.merge(
        w[["row_id"] + flag_cols + ["CI", "signal_count", "trigger_reason",
                                    "screening_tier", "DKNA_count", "LS_run", "MD_d2"]],
        on="row_id", how="left")
    for c in flag_cols + ["CI", "signal_count", "DKNA_count", "LS_run"]:
        sig[c] = sig[c].fillna(0).astype(int)
    sig["veto_any"] = veto.astype(int)
    sig.loc[sig["veto_any"] == 1, "screening_tier"] = "VETO"
    sig["trigger_reason"] = sig["trigger_reason"].fillna("")
    sig["screening_tier"] = sig["screening_tier"].fillna("NORMAL")

    # 列重排：标记列前置
    first_cols = ["row_id", "veto_any", "screening_tier", "signal_count", "trigger_reason",
                  "CI", "flag_dur_low", "flag_dur_high", "flag_md", "flag_long", "flag_dkna",
                  "DUR", "MD_d2", "LS_run", "DKNA_count"]
    rest = [c for c in sig.columns if c not in first_cols and c != "ID"]
    sig = sig[first_cols + ["ID"] + rest]

    OUT.mkdir(exist_ok=True)
    sig.to_csv(OUT / "signals.csv", index=False, encoding="utf-8-sig")
    print(f"Saved: {OUT / 'signals.csv'}（{len(sig)} 行）")
    print("分层:", dict(sig["screening_tier"].value_counts()))
    print("信号命中:", {k: int(v) for k, v in sig[flag_cols].sum().items()})


if __name__ == "__main__":
    main()
