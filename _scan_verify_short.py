import pandas as pd
import sys, io
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
verify['single'] = verify[['b_len','t_len']].max(axis=1)
verify['content'] = verify.apply(lambda r: r['b'] if r['b'] else r['t'], axis=1)

# 只答一题且 single <= 15 的行
short = verify[(verify['single'] <= 15) & (verify['single'] > 0)].sort_values('single')

print(f"单题 ≤15 字且非空的行: {len(short)}")
print()
for _, r in short.iterrows():
    print(f"id={r['row_id']} | {r['COUNTRY_CODE']} | max_len={r['single']:>2d} | "
          f"B='{r['b']}' | T='{r['t']}'")
