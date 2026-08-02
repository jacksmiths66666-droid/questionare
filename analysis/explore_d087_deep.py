"""Deep exploration of D087 for screening methodology design."""
import pandas as pd, numpy as np
from pathlib import Path

f = Path(r"D:\开山\收集数据\D081_TISP\D087_政治社会学_西班牙抗议参与_2019\02_官方原始数据\02_PROTEiCA_survey_EN.csv")
df = pd.read_csv(f, dtype=str, keep_default_na=False)

# === 1. Open-ended: what are the "1-char" responses? ===
print("=== Open-ended: 1-char content ===")
for col in ["P07Ctx", "P10tx", "P12Btx", "P16Btx"]:
    short = df[df[col].str.len() == 1][col]
    vc = short.value_counts().head(20)
    print(f"\n{col} (1-char, n={len(short)}):")
    print(f"  {vc.to_string()}")

# === 2. DUR vs engagement ===
print("\n\n=== DUR analysis ===")
dur = pd.to_numeric(df["DUR"], errors="coerce")

# How many open-ended chars vs DUR?
for col in ["P07Ctx", "P10tx", "P12Btx", "P16Btx"]:
    df["_len_" + col] = df[col].str.len()

total_text_len = df["_len_P07Ctx"] + df["_len_P10tx"] + df["_len_P12Btx"] + df["_len_P16Btx"]
dur_bins = pd.cut(dur, bins=[0, 7.5, 10, 13, 20, 100], labels=["<7.5min", "7.5-10min", "10-13min", "13-20min", ">20min"])
print("\nTotal text length by DUR bin:")
print(total_text_len.groupby(dur_bins, observed=False).describe().to_string())

# === 3. Interviewer patterns ===
print("\n\n=== Interviewer analysis ===")
for intr in sorted(df["CODINT"].unique()):
    sub = df[df["CODINT"] == intr]
    avg_dur = pd.to_numeric(sub["DUR"], errors="coerce").mean()
    avg_text = sub["_len_P07Ctx"].mean() + sub["_len_P10tx"].mean() + sub["_len_P12Btx"].mean() + sub["_len_P16Btx"].mean()
    print(f"  CODINT {intr:>2s}: n={len(sub):>4d}, avg_dur={avg_dur:.1f}, avg_text_len={avg_text:.0f}")

# === 4. Longstring candidate items ===
# Identify all single-response ordinal items
ordinal_cols = []
for c in df.columns:
    if c.startswith("P") and c not in ["P24tx", "P07Ctx", "P10tx", "P12Btx", "P16Btx"]:
        if c in ["PHASE20", "PHASE2", "P07C1","P07C2","P07C3","P07C4","P10_1","P10_2","P10_3","P10_4",
                 "P12B_1","P12B_2","P12B_3","P12B_4","P16B_1","P16B_2","P16B_3","P16B_4",
                 "P28_1","P28_2","P28_3","P28_4"]:
            continue  # multi-select binary flags
        if c in ["P07D1","P07D2","P07D3","P07D4","P07D5","P07D6",
                 "P11A","P11B","P11C","P11D","P11E",
                 "P21A","P21B","P21C","P21D"]:
            ordinal_cols.append(c)
            continue
        if c in ["P02A","P02B","P02C","P02D","P02E"]:
            ordinal_cols.append(c)
            continue
        # Single questions
        single_qs = ["P01","P03","P04","P05","P06","P07","P08","P09","P12","P13","P14","P15",
                     "P16","P17","P18","P22","P23","P25","P27","P28","P29","P09B","P13B","P17B"]
        if c in single_qs:
            ordinal_cols.append(c)
            continue

print(f"\n=== Longstring candidate columns: {len(ordinal_cols)} ===")
print(f"  {ordinal_cols}")

# Check unique values per column for ordinal coding
print("\n=== Unique values per ordinal col ===")
for c in ordinal_cols:
    uniq = df[c].unique()
    print(f"  {c}: {len(uniq)} values -> {uniq[:6]}")

# === 5. Q11A-E distribution for Mahalanobis ===
print("\n\n=== Q11A-E value mapping ===")
# Map text values to numbers
agree_map = {
    "Strongly agree": 5, "Agree": 4, "Neither agree nor disagree": 3,
    "Disagree": 2, "Strongly disagree": 1,
    "DK": np.nan, "NA": np.nan
}
for c in ["P11A","P11B","P11C","P11D","P11E"]:
    mapped = df[c].map(agree_map)
    print(f"  {c}: mean={mapped.mean():.2f}, std={mapped.std():.2f}, missing={mapped.isna().sum()}")

# === 6. Mode comparison ===
print("\n\n=== Mode comparison ===")
for mode in df["MODE"].unique():
    sub = df[df["MODE"] == mode]
    avg_dur = pd.to_numeric(sub["DUR"], errors="coerce").mean()
    avg_text = (sub["_len_P07Ctx"].mean() + sub["_len_P10tx"].mean() + 
                sub["_len_P12Btx"].mean() + sub["_len_P16Btx"].mean())
    short_dur = (pd.to_numeric(sub["DUR"], errors="coerce") < 7.5).mean()
    print(f"  {mode:12s}: n={len(sub):>4d}, avg_dur={avg_dur:.1f}, avg_text={avg_text:.0f}, pct_DUR<7.5={short_dur:.1%}")
