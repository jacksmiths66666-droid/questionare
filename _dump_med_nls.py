import pandas as pd, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

queue = pd.read_csv('outputs/screening_v3/tisp_v3_review_queue.csv', dtype=str, keep_default_na=False)
med = queue[queue['screening_tier'] == 'MEDIUM'].copy()

sig_cols = ['signal_attention', 'signal_longstring', 'signal_mahalanobis', 'signal_odd_even']
for c in sig_cols:
    med[c] = pd.to_numeric(med[c], errors='coerce').fillna(0).astype(int)

# 非 longstring 的信号行: longstring=0, 其他至少一项=1
med_nls = med[(med['signal_longstring'] == 0) & 
              ((med['signal_odd_even'] == 1) | (med['signal_mahalanobis'] == 1) | (med['signal_attention'] == 1))].copy()

print(f"非 longstring MEDIUM: {len(med_nls)}")
print()

def clean(t):
    t = str(t).strip()
    return '' if t.lower() in ('', 'nan', 'na', '-99', 'none') else t

med_nls['b'] = med_nls['BENEFIT_OPEN'].apply(clean)
med_nls['t'] = med_nls['TRUST_OPEN'].apply(clean)

for _, r in med_nls.iterrows():
    signals = []
    if r['signal_odd_even'] == 1: signals.append('OE')
    if r['signal_mahalanobis'] == 1: signals.append('MD')
    if r['signal_attention'] == 1: signals.append('AT')
    sig_str = '+'.join(signals)
    print(f"id={r['row_id']:>8s} | {r['COUNTRY_CODE']} | [{sig_str}] | B='{r['b']}' | T='{r['t']}'")

# 也输出到文件方便查看
output = []
for _, r in med_nls.iterrows():
    signals = []
    if r['signal_odd_even'] == 1: signals.append('OE')
    if r['signal_mahalanobis'] == 1: signals.append('MD')
    if r['signal_attention'] == 1: signals.append('AT')
    output.append("id=%s | %s | [%s] | B='%s' | T='%s'" % (
        r['row_id'], r['COUNTRY_CODE'], '+'.join(signals), r['b'], r['t']))

with open('outputs/screening_v3/med_nls_817_rows.txt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(output))
print("\n已写入 outputs/screening_v3/med_nls_817_rows.txt")
