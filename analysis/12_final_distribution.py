"""
最终分布汇总: 用 queue auto_decision 覆盖 analysis_ready final_decision
"""
import pandas as pd, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

q = pd.read_csv('outputs/screening_v3/tisp_v3_review_queue.csv', dtype=str, keep_default_na=False)
ar = pd.read_csv('outputs/screening_v3/tisp_v3_analysis_ready.csv', dtype=str, keep_default_na=False)

q['row_id'] = q['row_id'].astype(str)
ar['row_id'] = ar['row_id'].astype(str)

q_dec = q.set_index('row_id')[['auto_decision', 'auto_reason', 'screening_tier']]
ar = ar.set_index('row_id')

# 非队列行: 用 final_decision
ar['_in_queue'] = ar.index.isin(q_dec.index)
ar['_qdec'] = ar.index.map(q_dec['auto_decision']).fillna('')
ar['_qreason'] = ar.index.map(q_dec['auto_reason']).fillna('')
ar['_qtier'] = ar.index.map(q_dec['screening_tier']).fillna('NON-QUEUE')

def eff_dec(row):
    if row['_in_queue']:
        return row['_qdec']
    return 'valid' if row['final_decision'] in ('normal', 'valid1', 'valid2') else 'invalid'

ar['_eff'] = ar.apply(eff_dec, axis=1)

print("=" * 70)
print("最终有效/无效分布")
print("=" * 70)
valid = (ar['_eff'] == 'valid').sum()
invalid = (ar['_eff'] == 'invalid').sum()
total = len(ar)
print(f"有效 (valid):   {valid:>6d}  ({valid/total*100:.2f}%)")
print(f"无效 (invalid): {invalid:>6d}  ({invalid/total*100:.2f}%)")
print(f"总计:           {total:>6d}")
print()

print("=" * 70)
print("按层级分布")
print("=" * 70)
for tier in ['NON-QUEUE', 'HIGH', 'VERIFY', 'MEDIUM']:
    sub = ar[ar['_qtier'] == tier]
    v = (sub['_eff'] == 'valid').sum()
    i = (sub['_eff'] == 'invalid').sum()
    print(f"{tier:<10s}: n={len(sub):>6d} | valid={v:>6d} ({v/len(sub)*100:5.1f}%) | invalid={i:>6d} ({i/len(sub)*100:5.1f}%)")
print()

# 按信号
print("=" * 70)
print("信号分布")
print("=" * 70)
sig_map = {'0': 'NORMAL(无信号)', '1': 'MEDIUM(1信号)', '2': 'HIGH(2+信号)', '3': 'HIGH(3+信号)'}
for sc in ['0', '1', '2', '3']:
    sub = ar[ar['signal_count'] == sc]
    v = (sub['_eff'] == 'valid').sum()
    i = (sub['_eff'] == 'invalid').sum()
    print(f"signal_count={sc} ({sig_map.get(sc, '')}): n={len(sub):>6d} | valid={v:>6d} | invalid={i:>6d}")
