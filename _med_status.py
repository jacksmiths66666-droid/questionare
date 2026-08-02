import pandas as pd, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

queue = pd.read_csv('outputs/screening_v3/tisp_v3_review_queue.csv', dtype=str, keep_default_na=False)
ar = pd.read_csv('outputs/screening_v3/tisp_v3_analysis_ready.csv', dtype=str, keep_default_na=False)

med_in_queue = queue[queue['screening_tier'] == 'MEDIUM'].copy()
med_ids = set(med_in_queue['row_id'])

# 这些 row_id 在 analysis_ready 中的 final_decision
ar_med = ar[ar['row_id'].isin(med_ids)]
print(f"MEDIUM rows in queue: {len(med_ids)}")
print(f"MEDIUM rows in analysis_ready: {len(ar_med)}")

fd = ar_med['final_decision'].value_counts()
print(f"\nfinal_decision in analysis_ready for MEDIUM rows:")
print(fd.to_string())

# 再看非 MEDIUM 的分布
non_med_queue = queue[queue['screening_tier'] != 'MEDIUM']
print(f"\n非 MEDIUM queue rows: {len(non_med_queue)}")
print(f"  HIGH: {(queue['screening_tier']=='HIGH').sum()}")
print(f"  VERIFY: {(queue['screening_tier']=='VERIFY').sum()}")
print(f"  LOW: {(queue['screening_tier']=='LOW').sum()}" if 'LOW' in queue['screening_tier'].values else "")

# 全部 71,922 的最终分布
all_fd = ar['final_decision'].value_counts()
print(f"\nanalysis_ready 全部 final_decision:")
print(all_fd.to_string())
print(f"\nTotal: {len(ar)}")
