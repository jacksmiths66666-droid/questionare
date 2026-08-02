"""
把 HIGH 层人工审核结果写回 queue
decision: valid1 → valid, invalid → invalid
"""
import pandas as pd, shutil
from pathlib import Path

BASE = Path.cwd()
Q_PATH = BASE / 'outputs' / 'screening_v3' / 'tisp_v3_review_queue.csv'
OUT_DIR = BASE / 'outputs' / 'screening_v3'

queue = pd.read_csv(Q_PATH, dtype=str, keep_default_na=False)
high = pd.read_csv(OUT_DIR / 'high_review_results.csv', dtype=str)

# 映射 decision → 标准值
dec_map = {'valid1': 'valid', 'invalid': 'invalid'}
high['std_decision'] = high['decision'].map(dec_map)

for _, r in high.iterrows():
    rid = str(r['row_id'])
    mask = queue['row_id'] == rid
    queue.loc[mask, 'decision'] = r['std_decision']
    queue.loc[mask, 'reason'] = r.get('reason', '')

# 验证
q_high = queue[queue['screening_tier'] == 'HIGH']
print(f"HIGH: {len(q_high)} → valid={(q_high['decision']=='valid').sum()} invalid={(q_high['decision']=='invalid').sum()}")

queue.to_csv(Q_PATH, index=False)
print(f"已更新: {Q_PATH}")

DELIV = BASE / '论文提交关键东西' / 'data'
shutil.copy2(Q_PATH, DELIV / 'tisp_v3_review_queue.csv')
print("同步完成")
