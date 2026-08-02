"""聚合全量复核队列 + 自动标注 HIGH 层"""
import pandas as pd
import numpy as np
import sys, io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

queue = pd.read_csv('outputs/screening_v3/tisp_v3_review_queue.csv', dtype=str, keep_default_na=False)

# 标记已审批次的旧决策（1,552 行旧队列）
old = pd.read_csv('outputs/screening_v3/tisp_v3_review_annotated.csv', dtype=str, keep_default_na=False)
old['row_id'] = old['row_id'].astype(int)
queue['row_id_int'] = queue['row_id'].astype(int)
old_decisions = dict(zip(old['row_id'], old['final_decision']))
queue['old_final'] = queue['row_id_int'].map(old_decisions).fillna('')

# 自动标注 HIGH 层
high_mask = queue['screening_tier'] == 'HIGH'
ben_len = queue['BENEFIT_OPEN'].fillna('').str.len()
tru_len = queue['TRUST_OPEN'].fillna('').str.len()
queue['total_len'] = ben_len + tru_len

queue['auto_decision'] = ''
queue.loc[high_mask & (queue['total_len'] >= 30), 'auto_decision'] = 'valid2'
queue.loc[high_mask & (queue['total_len'] < 30) & (queue['total_len'] >= 10), 'auto_decision'] = 'valid1'
queue.loc[high_mask & (queue['total_len'] < 10), 'auto_decision'] = 'invalid'

# 输出列
out_cols = [
    'row_id', 'screening_tier', 'trigger_reason',
    'signal_count', 'signal_attention', 'signal_longstring',
    'signal_mahalanobis', 'signal_odd_even',
    'ls_max_run', 'md_score', 'oe_r',
    'BENEFIT_OPEN', 'TRUST_OPEN',
    'total_len',
    'old_final', 'auto_decision', 'final_decision'
]
out_cols = [c for c in out_cols if c in queue.columns]

out = queue[out_cols].copy()
tier_order = {'HIGH': 0, 'VERIFY': 1, 'MEDIUM': 2}
out['_sort'] = out['screening_tier'].map(tier_order).fillna(9)
out = out.sort_values(['_sort', 'row_id']).drop(columns=['_sort'])

out.to_excel('outputs/screening_v3/full_review_queue.xlsx', index=False)
print(f"OK: full_review_queue.xlsx ({len(out)} rows)")
print(f"  HIGH: {(out['screening_tier']=='HIGH').sum()}")
print(f"  VERIFY: {(out['screening_tier']=='VERIFY').sum()}")
print(f"  MEDIUM: {(out['screening_tier']=='MEDIUM').sum()}")
print()
print("HIGH auto decision:")
print(out[out['screening_tier']=='HIGH']['auto_decision'].value_counts().to_string())