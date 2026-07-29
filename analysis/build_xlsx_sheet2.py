"""Append full analysis-ready dataset as Sheet 2 to the review queue xlsx."""
import pandas as pd
from pathlib import Path

BASE = Path(r"D:\开山\收集数据\D081_TISP")
XLSX_PATH = BASE / "outputs" / "screening_v3" / "tisp_v3_review_queue.xlsx"
DELIVER_PATH = BASE / "论文提交关键东西" / "tisp_v3_review_queue.xlsx"
READY_PATH = BASE / "outputs" / "screening_v3" / "tisp_v3_analysis_ready.csv"

# Load review queue (Sheet 1)
queue = pd.read_csv(
    BASE / "outputs" / "screening_v3" / "tisp_v3_review_queue.csv",
    dtype=str, keep_default_na=False, encoding="utf-8",
)

# Load analysis-ready (Sheet 2) - subset of columns for readability
ready = pd.read_csv(READY_PATH, dtype=str, keep_default_na=False, encoding="utf-8")

# Decide which columns to include in Sheet 2: key identifiers + decision
sheet2_cols = ["row_id", "COUNTRY_CODE", "COUNTRY_NAME",
               "screening_tier", "signal_count", "trigger_reason",
               "signal_attention", "signal_longstring", "signal_mahalanobis", "signal_odd_even",
               "final_decision"]
sheet2 = ready[[c for c in sheet2_cols if c in ready.columns]].copy()

# Write multi-sheet xlsx
with pd.ExcelWriter(XLSX_PATH, engine="openpyxl") as writer:
    queue.to_excel(writer, index=False, sheet_name="复核队列")
    sheet2.to_excel(writer, index=False, sheet_name="全量有效数据")

# Also sync to deliverable
with pd.ExcelWriter(DELIVER_PATH, engine="openpyxl") as writer:
    queue.to_excel(writer, index=False, sheet_name="复核队列")
    sheet2.to_excel(writer, index=False, sheet_name="全量有效数据")

print(f"Sheet 1 (复核队列): {len(queue)} rows")
print(f"Sheet 2 (全量有效): {len(sheet2)} rows")
print(f"Written to:")
print(f"  {XLSX_PATH}")
print(f"  {DELIVER_PATH}")
