import pandas as pd, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

queue = pd.read_csv('outputs/screening_v3/tisp_v3_review_queue.csv', dtype=str, keep_default_na=False)
ar = pd.read_csv('outputs/screening_v3/tisp_v3_analysis_ready.csv', dtype=str, keep_default_na=False)

med_q = queue[queue['screening_tier'] == 'MEDIUM'].copy()
med_id = set(med_q['row_id'])
ar_med = ar[ar['row_id'].isin(med_id)]

# 看 veto 状态
veto_cols = ['veto_any', 'veto_all_missing', 'veto_gibberish']
for c in veto_cols:
    if c in med_q.columns:
        vals = med_q[c].value_counts()
        print(f"{c}: {vals.to_dict()}")
print()

# 按 final_decision 分组看 veto 情况
for fd in ['invalid', 'valid1', 'normal', 'valid2']:
    sub = med_q[med_q['row_id'].isin(ar_med[ar_med['final_decision']==fd]['row_id'])]
    print(f"\nfinal_decision = {fd} ({len(sub)} rows)")
    print(f"  veto_any: {sub['veto_any'].value_counts().to_dict() if 'veto_any' in sub.columns else 'N/A'}")
    print(f"  signal组合: attention={sub['signal_attention'].sum()} longstring={sub['signal_longstring'].sum()} md={sub['signal_mahalanobis'].sum()} oe={sub['signal_odd_even'].sum()}")
