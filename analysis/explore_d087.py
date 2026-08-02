"""Explore D087 data structure for screening plan."""
import pandas as pd, numpy as np
from pathlib import Path

f = Path(r"D:\开山\收集数据\D081_TISP\D087_政治社会学_西班牙抗议参与_2019\02_官方原始数据\02_PROTEiCA_survey_EN.csv")
df = pd.read_csv(f, dtype=str, keep_default_na=False)

print("=== DUR distribution ===")
dur = pd.to_numeric(df["DUR"], errors="coerce")
print(f"  Range: {dur.min():.1f} - {dur.max():.1f}")
print(f"  Mean: {dur.mean():.1f}, Median: {dur.median():.1f}")
for p in [1, 5, 10, 25, 50, 75, 90, 95, 99]:
    print(f"  P{p}: {np.percentile(dur.dropna(), p):.1f}")

print("\n=== Interviewer (CODINT) ===")
print(f"  Unique: {df['CODINT'].nunique()}")
grp = df.groupby("CODINT").size()
print(f"  Min: {grp.min()}, Max: {grp.max()}, Mean: {grp.mean():.0f}")

print("\n=== MODE ===")
print(df["MODE"].value_counts().to_string())

print("\n=== Open-ended non-empty ===")
for col in ["P07Ctx", "P10tx", "P12Btx", "P16Btx"]:
    ne = (df[col] != "").sum()
    print(f"  {col}: {ne} / {len(df)}")
    if ne > 0:
        lens = df.loc[df[col] != "", col].str.len()
        print(f"    len: min={lens.min()}, med={lens.median():.0f}, max={lens.max()}")

# Scale items
print("\n=== Q11A-E (Gender equality, 1-5 scale) ===")
for c in ["P11A","P11B","P11C","P11D","P11E"]:
    print(f"  {c}: {dict(df[c].value_counts().head(8))}")

print("\n=== Q21A-D (Social media, 1-5 scale) ===")
for c in ["P21A","P21B","P21C","P21D"]:
    print(f"  {c}: {dict(df[c].value_counts().head(8))}")

# Check for any reverse-coded items
print("\n=== Check P01-P29 response patterns ===")
q_cols = [c for c in df.columns if c.startswith("P") and c[1:].isdigit() and len(c) <= 4]
print(f"  Main question columns ({len(q_cols)}): {q_cols}")

# Also check P02A-E which are sub-questions
qsub = [c for c in df.columns if c.startswith("P") and not c[1:].isdigit() and c != "P24tx"]
print(f"\n  Sub-question columns ({len(qsub)}): {qsub}")
