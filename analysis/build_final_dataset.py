import pandas as pd
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "outputs", "screening_v3")
OUTPUT_FILE = os.path.join(BASE, "tisp_v3_final_all_data.csv")

flags = pd.read_csv(os.path.join(OUT, "tisp_v3_flags.csv"), low_memory=False)
ready = pd.read_csv(os.path.join(OUT, "tisp_v3_analysis_ready.csv"), low_memory=False)
queue = pd.read_csv(os.path.join(OUT, "tisp_v3_review_queue.csv"), low_memory=False)

print(f"flags rows: {len(flags)}")
print(f"analysis_ready rows: {len(ready)}")
print(f"review_queue rows: {len(queue)}")

# Step 1: merge final_decision from analysis_ready into flags
decision_map = ready[["row_id", "final_decision"]].drop_duplicates("row_id")
flags = flags.merge(decision_map, on="row_id", how="left", suffixes=("", "_from_ready"))

# Step 2: fill missing final_decision from review_queue
queue_map = queue[["row_id", "final_decision"]].drop_duplicates("row_id")
queue_map.columns = ["row_id", "final_decision_queue"]
flags = flags.merge(queue_map, on="row_id", how="left")

# fill gaps
flags["final_decision"] = flags["final_decision"].fillna(flags["final_decision_queue"])

# Step 3: remaining rows without final_decision → invalid
flags["final_decision"] = flags["final_decision"].fillna("invalid")

# Step 4: add translations from analysis_ready
trans_cols = [c for c in ready.columns if c.endswith("_ZH")]
trans_map = ready[["row_id"] + trans_cols].drop_duplicates("row_id")
flags = flags.merge(trans_map, on="row_id", how="left")

# Step 5: add translations from review_queue only if not already present
queue_trans = [c for c in queue.columns if c.endswith("_ZH")]
need_from_queue = [c for c in queue_trans if c not in flags.columns]
if need_from_queue:
    queue_map2 = queue[["row_id"] + need_from_queue].drop_duplicates("row_id")
    flags = flags.merge(queue_map2, on="row_id", how="left")

# Step 6: sort by classification then row_id
cat_order = {"valid2": 0, "valid1": 1, "normal": 2, "invalid": 3}
flags["_sort"] = flags["final_decision"].map(cat_order).fillna(9)
flags.sort_values(["_sort", "row_id"], inplace=True)
flags.drop(columns=["_sort", "final_decision_queue"], inplace=True)

# Step 7: reorder columns - put final_decision, translations at front
first_cols = ["row_id", "final_decision"] + trans_cols
rest = [c for c in flags.columns if c not in first_cols]
flags = flags[first_cols + rest]

# Step 8: save
flags.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")

print(f"\nFinal file saved: {OUTPUT_FILE}")
print(f"Total rows: {len(flags)}")
print("\nClassification breakdown:")
print(flags["final_decision"].value_counts().to_string())
print(f"\nTotal: {flags['final_decision'].value_counts().sum()}")
