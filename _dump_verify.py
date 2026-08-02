import pandas as pd, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

queue = pd.read_csv('outputs/screening_v3/tisp_v3_review_queue.csv', dtype=str, keep_default_na=False)
v = queue[queue['screening_tier'] == 'VERIFY'].copy()

def clean(t):
    t = str(t).strip()
    return '' if t.lower() in ('', 'nan', 'na', '-99', 'none') else t

v['b'] = v['BENEFIT_OPEN'].apply(clean)
v['t'] = v['TRUST_OPEN'].apply(clean)

# 全量输出
for _, r in v.iterrows():
    print(f"id={r['row_id']:>8s} | {r['COUNTRY_CODE']} | B='{r['b']}' | T='{r['t']}'")
