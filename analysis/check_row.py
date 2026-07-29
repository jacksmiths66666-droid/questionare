"""Check specific row"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import pandas as pd

df = pd.read_csv("outputs/screening_v3/tisp_v3_review_queue.csv")
r = df[df["row_id"] == 38869].iloc[0]

for col in df.columns:
    print(f"{col:30s}: {str(r[col])[:120]}")
