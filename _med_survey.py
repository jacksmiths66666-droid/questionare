import pandas as pd, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

queue = pd.read_csv('outputs/screening_v3/tisp_v3_review_queue.csv', dtype=str, keep_default_na=False)
med = queue[queue['screening_tier'] == 'MEDIUM'].copy()

print(f"MEDIUM 行数: {len(med)}")
print()

# signals present
sig_cols = [c for c in med.columns if c.startswith('ls_') or c.startswith('lq_') or c.startswith('mc_') or c == 'signal_count']
present_sigs = [c for c in sig_cols if c in med.columns]

# signal_count distribution
med['sc'] = pd.to_numeric(med['signal_count'], errors='coerce').fillna(0).astype(int)
print("signal_count 分布:")
print(med['sc'].value_counts().sort_index().to_string())
print()

# 看看有哪些 signal 列
print("signal 列:", present_sigs)
print()

# 各个 signal 的触发频率
for col in sorted(present_sigs):
    if col == 'signal_count':
        continue
    n = (med[col].astype(str).str.strip().str.lower().isin(['true', '1', 't']) | 
         pd.to_numeric(med[col], errors='coerce').eq(1)).sum()
    print(f"  {col}: {n} rows")
