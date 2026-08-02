import pandas as pd
q = pd.read_csv('outputs/screening_v3/tisp_v3_review_queue.csv', dtype=str)
v = q[q['screening_tier'] == 'VERIFY']
n = len(v)
nv = (v['auto_decision'] == 'valid').sum()
ni = (v['auto_decision'] == 'invalid').sum()
print("VERIFY: %d -> valid=%d invalid=%d" % (n, nv, ni))
for _, r in v[v['auto_decision']=='invalid'].iterrows():
    print("  id=%s | %s | %s" % (r['row_id'], r['auto_reason'], r['auto_decision']))
