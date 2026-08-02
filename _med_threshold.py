import pandas as pd, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

queue = pd.read_csv('outputs/screening_v3/tisp_v3_review_queue.csv', dtype=str, keep_default_na=False)
ar = pd.read_csv('outputs/screening_v3/tisp_v3_analysis_ready.csv', dtype=str, keep_default_na=False)

med = queue[queue['screening_tier'] == 'MEDIUM'].copy()

def clean(t):
    t = str(t).strip()
    return '' if t.lower() in ('', 'nan', 'na', '-99', 'none') else t

med['b'] = med['BENEFIT_OPEN'].apply(clean)
med['t'] = med['TRUST_OPEN'].apply(clean)
med['_len'] = med[['b','t']].apply(lambda r: max(len(r['b']), len(r['t'])), axis=1)

print("MEDIUM len distribution:")
for v in sorted(med['_len'].unique()):
    if v <= 40:
        print(f"  L={v:>2d}: {(med['_len']==v).sum()}")

# 计算不同阈值下的全局 valid rate
queue_val = pd.Series(queue['auto_decision'].values, index=queue['row_id']).to_dict()
queue_auto = queue.set_index('row_id')['auto_decision']

for thresh in [12, 15, 20, 25, 30, 35, 40, 50]:
    med_d = med['_len'] >= thresh
    med_d = med_d.replace({True: 'valid', False: 'invalid'})
    
    ar['_qdec'] = ar['row_id'].map(queue_auto).fillna('')
    ar.loc[ar['row_id'].isin(med['row_id']), '_qdec'] = med_d.values
    
    ar['_final'] = ar['_qdec'].where(ar['_qdec'] != '', ar['final_decision'])
    ar['_ok'] = ar['_final'].isin(('valid', 'normal', 'valid1', 'valid2'))
    vr = ar['_ok'].sum() / len(ar) * 100
    print(f"\n≥{thresh:>2d}: valid={ar['_ok'].sum():>5d}  invalid={(~ar['_ok']).sum():>5d}  rate={vr:.1f}%")
