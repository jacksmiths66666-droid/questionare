"""
MEDIUM non-longstring: 应用审核结果到 queue + 处理 longstring 行
"""
import pandas as pd, shutil
from pathlib import Path

BASE = Path.cwd()
Q_PATH = BASE / 'outputs' / 'screening_v3' / 'tisp_v3_review_queue.csv'
OUT_DIR = BASE / 'outputs' / 'screening_v3'

queue = pd.read_csv(Q_PATH, dtype=str, keep_default_na=False)
med = queue[queue['screening_tier'] == 'MEDIUM'].copy()

for c in ['signal_attention','signal_longstring','signal_mahalanobis','signal_odd_even']:
    med[c] = pd.to_numeric(med[c], errors='coerce').fillna(0).astype(int)

# 非 longstring 行: 应用审核结果
nls = med[(med['signal_longstring'] == 0) & 
          ((med['signal_odd_even'] == 1) | (med['signal_mahalanobis'] == 1) | (med['signal_attention'] == 1))].copy()

review = pd.read_csv(OUT_DIR / 'med_nls_review_results.csv', dtype=str)
decisions = dict(zip(review['row_id'], review['decision']))
reasons = dict(zip(review['row_id'], review['reason']))

# 修正边界: 33867 nvt → valid
decisions['33867'] = 'valid'

for rid, dec in decisions.items():
    mask = queue['row_id'] == rid
    queue.loc[mask, 'decision'] = dec
    queue.loc[mask, 'reason'] = reasons.get(rid, '')

nls_valid = sum(1 for d in decisions.values() if d == 'valid')
nls_invalid = sum(1 for d in decisions.values() if d == 'invalid')
print(f"非 longstring: {len(decisions)} 行 → valid={nls_valid} invalid={nls_invalid}")

# longstring 行: 保持 Rule B 结果（invalid）
ls = med[med['signal_longstring'] == 1].copy()
print(f"\nlongstring 行: {len(ls)} → 全部标记 invalid（Rule B）")

ls_ids = set(ls['row_id'])
med_mask = queue['screening_tier'] == 'MEDIUM'
queue.loc[med_mask & queue['row_id'].isin(ls_ids), 'decision'] = 'invalid'
queue.loc[med_mask & queue['row_id'].isin(ls_ids), 'reason'] = 'longstring（straightlining）'

# 最终 MEDIUM 统计
med_updated = queue[queue['screening_tier'] == 'MEDIUM']
mv = (med_updated['decision'] == 'valid').sum()
mi = (med_updated['decision'] == 'invalid').sum()
print(f"\nMEDIUM 最终: {len(med_updated)} → valid={mv} invalid={mi} (rate={mv/len(med_updated)*100:.1f}%)")

queue.to_csv(Q_PATH, index=False)
print(f"已更新: {Q_PATH}")

# 同步 deliverable
DELIV = BASE / '论文提交关键东西' / 'data'
shutil.copy2(Q_PATH, DELIV / 'tisp_v3_review_queue.csv')
print("同步完成")
