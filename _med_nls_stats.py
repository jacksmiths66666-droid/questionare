import pandas as pd, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

queue = pd.read_csv('outputs/screening_v3/tisp_v3_review_queue.csv', dtype=str, keep_default_na=False)
med = queue[queue['screening_tier'] == 'MEDIUM'].copy()

for c in ['signal_attention','signal_longstring','signal_mahalanobis','signal_odd_even']:
    med[c] = pd.to_numeric(med[c], errors='coerce').fillna(0).astype(int)

med_nls = med[(med['signal_longstring'] == 0) & 
              ((med['signal_odd_even'] == 1) | (med['signal_mahalanobis'] == 1) | (med['signal_attention'] == 1))].copy()

def clean(t):
    t = str(t).strip()
    return '' if t.lower() in ('', 'nan', 'na', '-99', 'none') else t

med_nls['b'] = med_nls['BENEFIT_OPEN'].apply(clean)
med_nls['t'] = med_nls['TRUST_OPEN'].apply(clean)

# signal 分布
sig_map = {}
for _, r in med_nls.iterrows():
    sig = []
    if r['signal_odd_even'] == 1: sig.append('OE')
    if r['signal_mahalanobis'] == 1: sig.append('MD')
    if r['signal_attention'] == 1: sig.append('AT')
    key = '+'.join(sig)
    sig_map[key] = sig_map.get(key, 0) + 1

print("信号分布:")
for k, v in sorted(sig_map.items()):
    print(f"  {k}: {v}")

# 国家分布
print("\nTop 10 国家:")
print(med_nls['COUNTRY_CODE'].value_counts().head(10).to_string())

# 两题都空
empty_both = ((med_nls['b'] == '') & (med_nls['t'] == '')).sum()
print(f"\n两题都空: {empty_both}")

# 单题有内容的分布
b_only = ((med_nls['b'] != '') & (med_nls['t'] == '')).sum()
t_only = ((med_nls['b'] == '') & (med_nls['t'] != '')).sum()
both = ((med_nls['b'] != '') & (med_nls['t'] != '')).sum()
print(f"B 题有内容: {b_only}")
print(f"T 题有内容: {t_only}")
print(f"两题都有: {both}")
