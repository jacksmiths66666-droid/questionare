"""Check VERIFY composition"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import pandas as pd

df = pd.read_csv("outputs/screening_v3/tisp_v3_review_queue.csv")
v = df[df["screening_tier"] == "VERIFY"]

print("VERIFY共", len(v))
print("国家:", dict(v["COUNTRY_CODE"].value_counts()))
print("trigger_reason:", v["trigger_reason"].unique())
print("BENEFIT非空:", v["BENEFIT_OPEN"].notna().sum(), "/", len(v))
print("TRUST非空:", v["TRUST_OPEN"].notna().sum(), "/", len(v))

print("\n=== 短文本抽样 ===")
short = v[v["BENEFIT_OPEN"].notna() & (v["BENEFIT_OPEN"].astype(str).str.len() < 30)]
for _, r in short.head(8).iterrows():
    src = str(r["BENEFIT_OPEN"])[:50]
    tgt = str(r["BENEFIT_OPEN_ZH"])[:50]
    print(" ", r["COUNTRY_CODE"], "|", src, "->", tgt)

print("\n=== 空开放题比例 ===")
both_na = v["BENEFIT_OPEN"].isna() & v["TRUST_OPEN"].isna()
print("两道都空:", both_na.sum(), "/", len(v))
benefit_only = v["BENEFIT_OPEN"].notna() & v["TRUST_OPEN"].isna()
print("只答BENEFIT:", benefit_only.sum())
trust_only = v["BENEFIT_OPEN"].isna() & v["TRUST_OPEN"].notna()
print("只答TRUST:", trust_only.sum())
both_filled = v["BENEFIT_OPEN"].notna() & v["TRUST_OPEN"].notna()
print("两道都答:", both_filled.sum())
