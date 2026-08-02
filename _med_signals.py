import pandas as pd, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

queue = pd.read_csv('outputs/screening_v3/tisp_v3_review_queue.csv', dtype=str, keep_default_na=False)
med = queue[queue['screening_tier'] == 'MEDIUM'].copy()

print(f"MEDIUM 行数: {len(med)}")

sig_cols = ['signal_attention', 'signal_longstring', 'signal_mahalanobis', 'signal_odd_even']

for col in sig_cols:
    if col not in med.columns:
        print(f"  {col}: 列不存在")
        continue
    n = pd.to_numeric(med[col], errors='coerce').fillna(0).astype(int).sum()
    n_any = (pd.to_numeric(med[col], errors='coerce').fillna(0).astype(int) > 0).sum()
    print(f"  {col}: {int(n)} triggers ({n_any} rows)")

print()
# 这些信号是怎么组合成 signal_count=1 的
med['sc'] = pd.to_numeric(med['signal_count'], errors='coerce').fillna(0).astype(int)
med['sa'] = pd.to_numeric(med['signal_attention'], errors='coerce').fillna(0).astype(int)
med['sl'] = pd.to_numeric(med['signal_longstring'], errors='coerce').fillna(0).astype(int)
med['sm'] = pd.to_numeric(med['signal_mahalanobis'], errors='coerce').fillna(0).astype(int)
med['so'] = pd.to_numeric(med['signal_odd_even'], errors='coerce').fillna(0).astype(int)

# 信号组合分布
combo = med.groupby(['sa','sl','sm','so']).size().reset_index(name='count')
combo = combo.sort_values('count', ascending=False)
print("信号组合分布 (attention, longstring, mahalanobis, odd_even):")
for _, r in combo.iterrows():
    print(f"  ({r['sa']},{r['sl']},{r['sm']},{r['so']}) → {r['count']}")
