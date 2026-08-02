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

print("VERIFY max_len 分布:")
print(verify['max_len'].value_counts().sort_index().to_string())
print()

for threshold in [8, 10, 12, 15, 20]:
    inv = (verify['max_len'] < threshold).sum()
    val = (verify['max_len'] >= threshold).sum()
    print(f"≥{threshold:>2d}: valid={val:>3d}  invalid={inv:>3d}")
