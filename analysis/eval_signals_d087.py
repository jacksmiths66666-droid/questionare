"""Evaluate signal viability for D087."""
import pandas as pd, numpy as np
from pathlib import Path

f = Path(r"D:\开山\收集数据\D081_TISP\D087_政治社会学_西班牙抗议参与_2019\02_官方原始数据\02_PROTEiCA_survey_EN.csv")
df = pd.read_csv(f, dtype=str, keep_default_na=False)

# === 1. Longstring: actual distribution ===
print("=== LONGSTRING FEASIBILITY ===")
# Map ordinal items to numeric
ordinal_cols = ["P01","P02A","P02B","P02C","P02D","P02E","P03","P04","P05","P06","P07",
                "P07D1","P07D2","P07D3","P07D4","P07D5","P07D6",
                "P08","P09","P09B","P11A","P11B","P11C","P11D","P11E",
                "P12","P13","P13B","P14","P15","P16","P17","P17B",
                "P18","P21A","P21B","P21C","P21D","P22","P23","P25","P27","P28","P29"]

# Count unique values per column
print("Scale diversity (unique values per column):")
scales = {}
for c in ordinal_cols:
    n = df[c].nunique()
    key = n if n <= 10 else "10+"
    scales[key] = scales.get(key, 0) + 1
for k in sorted(scales.keys(), key=lambda x: str(x)):
    print(f"  {k} unique values: {scales[k]} cols")

# === 2. DUR distribution by mode ===
print("\n=== DUR BY MODE ===")
dur = pd.to_numeric(df["DUR"], errors="coerce")
for mode in ["CATI", "CAWI"]:
    sub = dur[df["MODE"] == mode]
    print(f"  {mode}: n={len(sub)}, P1={np.percentile(sub, 1):.1f}, P5={np.percentile(sub, 5):.1f}, P10={np.percentile(sub, 10):.1f}")

# === 3. Item nonresponse analysis ===
print("\n=== ITEM NONRESPONSE ===")
# Count DK/NA across all P-variables
p_cols = [c for c in df.columns if c.startswith("P") and c not in ["P24tx","P07Ctx","P10tx","P12Btx","P16Btx"]]
dk_na_vals = ["DK", "NA", "NC", "NS", "Can't say", "Can't remember", "Doesn't use social networks", "Doesn't have social networks", "Have no networks", ""]

nonresp = df[p_cols].apply(lambda x: x.isin(dk_na_vals)).sum(axis=1)
print(f"  Non-response per row: mean={nonresp.mean():.1f}, median={nonresp.median():.0f}")
print(f"  Rows with >50% nonresponse: {(nonresp > len(p_cols)*0.5).sum()}")
print(f"  Rows with >75% nonresponse: {(nonresp > len(p_cols)*0.75).sum()}")
print(f"  Top percentiles: P95={nonresp.quantile(0.95):.0f}, P99={nonresp.quantile(0.99):.0f}")

# === 4. Open-ended: actual text vs codes ===
print("\n=== OPEN-ENDED: text vs codes ===")
for col in ["P07Ctx", "P10tx", "P12Btx", "P16Btx"]:
    total = len(df)
    empty = (df[col].str.strip() == "").sum()
    # Detect coding-only responses (single digit, common codes)
    coding = df[col].str.match(r"^\d$", na=False).sum()
    # Also check "0" as code
    zero = (df[col].str.strip() == "0").sum()
    # Real text = has multiple chars OR has letters
    real_text = ((df[col].str.len() > 1) | df[col].str.contains(r"[a-zA-Záéíóúñ]", na=False)).sum()
    print(f"  {col}: empty={empty}, coding={coding}, zero={zero}, real_text={real_text}")

# === 5. Mode × interviewer effects on quality ===
print("\n=== MODE × INTERVIEWER ===")
for mode in ["CATI", "CAWI"]:
    sub = df[df["MODE"] == mode]
    avg_dur = pd.to_numeric(sub["DUR"], errors="coerce").mean()
    print(f"  {mode}: n={len(sub)}, avg_DUR={avg_dur:.1f}")
    if mode == "CATI":
        for intr in sorted(sub["CODINT"].unique()):
            s = sub[sub["CODINT"] == intr]
            d = pd.to_numeric(s["DUR"], errors="coerce")
            n = len(s)
            print(f"    Interviewer {intr:>12s}: n={n:>3d}, avg_DUR={d.mean():.1f}")
