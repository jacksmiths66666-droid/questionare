import pandas as pd
q = pd.read_csv('outputs/screening_v3/tisp_v3_review_queue.csv', dtype=str)
v = q[q['screening_tier'] == 'VERIFY']
n = len(v)
nv = (v['auto_decision'] == 'valid').sum()
ni = (v['auto_decision'] == 'invalid').sum()
print("VERIFY: %d -> valid=%d invalid=%d" % (n, nv, ni))
for _, r in v[v['auto_decision']=='invalid'].iterrows():
    rid = r['row_id']
    cc = r['COUNTRY_CODE']
    reason = r['auto_reason']
    b = str(r['BENEFIT_OPEN'])
    t = str(r['TRUST_OPEN'])
    print("  id=%s | %s | %s | B='%s' | T='%s'" % (rid, cc, reason, b, t))
