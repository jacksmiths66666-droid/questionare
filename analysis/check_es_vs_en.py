"""Check Spanish CSV - likely has numeric codes instead of text."""
import pandas as pd
from pathlib import Path

base = Path(r"D:\开山\收集数据\D081_TISP\D087_政治社会学_西班牙抗议参与_2019\02_官方原始数据")

es = pd.read_csv(base / "01_PROTEiCA_encuesta_ES.csv", dtype=str, keep_default_na=False)
en = pd.read_csv(base / "02_PROTEiCA_survey_EN.csv", dtype=str, keep_default_na=False)

print(f"ES cols: {len(es.columns)}, EN cols: {len(en.columns)}")
print(f"ES header: {list(es.columns)[:20]}")
print(f"EN header: {list(en.columns)[:20]}")

# Check Q11A-E in ES version
print("\n=== Q11A-E in ES CSV ===")
for c in ["P11A","P11B","P11C","P11D","P11E"]:
    print(f"  {c}: {list(es[c].unique())[:10]}")

# Check DUR
print(f"\nES DUR: {list(es['DUR'].unique())[:10]}")

# Check for differences between the two files
print(f"\nES ID type: {es['ID'].dtype}")
print(f"EN ID type: {en['ID'].dtype}")

# Check if rows match
print(f"\nES rows: {len(es)}, EN rows: {len(en)}")

# Check Q11A numeric coding
print("\n=== Q11A unique values (both versions) ===")
for c in ["P11A","P11B","P11C","P11D","P11E"]:
    es_vals = sorted(es[c].unique())
    en_vals = sorted(en[c].unique())
    print(f"  {c}: ES={es_vals} | EN={en_vals}")
