"""Check correlation between DUR and open-ended quality, and MD sub-scores."""
import pandas as pd, numpy as np
from pathlib import Path

f = Path(r"D:\开山\收集数据\D081_TISP\D087_政治社会学_西班牙抗议参与_2019\02_官方原始数据\02_PROTEiCA_survey_EN.csv")
df = pd.read_csv(f, dtype=str, keep_default_na=False)

dur = pd.to_numeric(df["DUR"], errors="coerce")

# === 1. Open-ended text length per field ===
print("=== Open-ended text length (real text only) ===")
for col in ["P07Ctx", "P10tx", "P12Btx", "P16Btx"]:
    # Count fields with real text (letters or >1 char)
    has_text = (df[col].str.contains(r"[a-zA-Záéíóúñ]", na=False) | (df[col].str.len() > 1)).astype(int)
    print(f"  {col}: {has_text.sum()} / {len(df)} have real text")

# Combined: how many of 4 fields have real text?
oe_cols = ["P07Ctx", "P10tx", "P12Btx", "P16Btx"]
oe_count = df[oe_cols].apply(lambda row: sum(
    1 for c in oe_cols if (pd.notna(row[c]) and len(str(row[c]).strip()) > 1 and 
                           any(ch.isalpha() for ch in str(row[c])))
), axis=1)
print(f"\nReal text field count distribution:")
print(f"  0 fields: {(oe_count == 0).sum()}")
print(f"  1 field: {(oe_count == 1).sum()}")
print(f"  2 fields: {(oe_count == 2).sum()}")
print(f"  3 fields: {(oe_count == 3).sum()}")
print(f"  4 fields: {(oe_count == 4).sum()}")

# === 2. DUR vs open-ended correlation ===
print("\n=== DUR vs open-ended text count ===")
for oe_n in range(5):
    sub = dur[oe_count == oe_n]
    if len(sub) > 0:
        print(f"  {oe_n} fields: n={len(sub)}, avg_DUR={sub.mean():.1f}, P5={sub.quantile(0.05):.1f}")

# === 3. MD on Q11A-E: check if 5 items are enough ===
print("\n=== Q11A-E correlations ===")
agree_map = {"Strongly agree":5, "Agree":4, "Neither agree nor disagree":3, 
             "Disagree":2, "Strongly disagree":1, "DK":np.nan, "NA":np.nan}
q11 = df[["P11A","P11B","P11C","P11D","P11E"]].apply(lambda x: x.map(agree_map))
print(f"  Completeness: {q11.dropna().shape[0]} / {len(df)} rows have all 5 items")
print(f"  Correlation matrix:")
print(q11.corr().round(3).to_string())

# === 4. MD on P07D1-D4: check feasibility ===
print("\n=== P07D1-D4 correlations ===")
freq_map = {"Very often":4, "Quite":3, "Little":2, "Not at all":1,
            "Doesn't use social networks":np.nan, "Doesn't have social networks":np.nan,
            "DK":np.nan, "NA":np.nan, "":np.nan}
p07d = df[["P07D1","P07D2","P07D3","P07D4"]].apply(lambda x: x.map(freq_map))
print(f"  Completeness: {p07d.dropna().shape[0]} / {len(df)} rows have all 4 items")
print(f"  Correlation matrix:")
print(p07d.corr().round(3).to_string())

# === 5. Combined MD feasibility ===
print("\n=== Combined Q11 + P07D MD ===")
combined = pd.concat([q11, p07d], axis=1)
complete = combined.dropna()
print(f"  Rows with all 9 items: {len(complete)} / {len(df)} ({len(complete)/len(df):.1%})")

# === 6. Item nonresponse detail ===
print("\n=== Nonresponse detail ===")
p_cols = [c for c in df.columns if c.startswith("P") and c not in ["P24tx","P07Ctx","P10tx","P12Btx","P16Btx"]]
dk_na_vals = ["DK", "NA", "NC", "NS", "Can't say", "Can't remember", 
              "Doesn't use social networks", "Doesn't have social networks", 
              "Have no networks", ""]
nonresp = df[p_cols].apply(lambda x: x.isin(dk_na_vals)).sum(axis=1)
print(f"  Mean: {nonresp.mean():.1f}, P95: {nonresp.quantile(0.95):.0f}, P99: {nonresp.quantile(0.99):.0f}")
print(f"  Top 10 nonresponse rows:")
top = nonresp.nlargest(10)
for idx, val in top.items():
    dur_val = dur.loc[idx]
    print(f"    ID={df.loc[idx,'ID']}, nonresp={val}/{len(p_cols)}, DUR={dur_val}")

# === 7. Logical consistency check ===
print("\n=== P07 vs P07B consistency ===")
# P07: awareness of March 8, P07B: attention/participation
p07_vals = df["P07"].value_counts()
print(f"  P07: {dict(p07_vals)}")
p07b_vals = df["P07B"].value_counts()
print(f"  P07B: {dict(p07b_vals)}")
