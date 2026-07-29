"""Quick data verification."""
import pandas as pd
from pathlib import Path
B = Path("D:/开山/收集数据/D081_TISP")
q = pd.read_csv(B/"outputs/screening_v3/tisp_v3_review_queue.csv", dtype=str, keep_default_na=False)
r = pd.read_csv(B/"outputs/screening_v3/tisp_v3_analysis_ready.csv", dtype=str, keep_default_na=False)

h = q[q["screening_tier"] == "HIGH"]
print("HIGH:", dict(h["final_decision"].value_counts()))

v = q[q["screening_tier"] == "VERIFY"]
print("VERIFY:", dict(v["final_decision"].value_counts()))

print("Total queue decisions:", dict(q["final_decision"].value_counts()))
print("Ready decisions:", dict(r["final_decision"].value_counts()))

u = ["35055","43310","43438","43508","43550","43647","43734","43796","44090"]
ur = q[q["row_id"].astype(str).isin(u)][["row_id","screening_tier","final_decision"]]
print("\n9 unsure:")
for _, row in ur.iterrows():
    print(f"  {str(row['row_id']):>6s} | {row['screening_tier']:>6s} | {row['final_decision']}")
v1 = len(ur[ur["final_decision"] == "valid1"])
iv = len(ur[ur["final_decision"] == "invalid"])
print(f"\n{len(ur)} total: {v1}->valid1, {iv}->invalid")
