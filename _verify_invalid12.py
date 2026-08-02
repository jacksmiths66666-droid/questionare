import pandas as pd, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

queue = pd.read_csv('outputs/screening_v3/tisp_v3_review_queue.csv', dtype=str, keep_default_na=False)
verify = queue[queue['screening_tier'] == 'VERIFY'].copy()

def clean(t):
    t = str(t).strip()
    return '' if t.lower() in ('', 'nan', 'na', '-99', 'none') else t

verify['b'] = verify['BENEFIT_OPEN'].apply(clean)
verify['t'] = verify['TRUST_OPEN'].apply(clean)
verify['b_len'] = verify['b'].str.len()
verify['t_len'] = verify['t'].str.len()
verify['max_len'] = verify[['b_len','t_len']].max(axis=1)

for threshold in [12]:
    inv = verify[verify['max_len'] < threshold].sort_values('max_len')
    print(f"≥{threshold}: {len(inv)} invalid rows\n")
    for _, r in inv.iterrows():
        print(f"id={r['row_id']:>8s} | {r['COUNTRY_CODE']} | L={r['max_len']:>2d} | "
              f"B='{r['b']}' | T='{r['t']}'")
