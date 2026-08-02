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

# 看看 ≥8 字的有多少，有没有明显垃圾
long = verify[verify['max_len'] >= 8].sort_values('max_len')
short = verify[verify['max_len'] < 8].sort_values('max_len')

print(f"VERIFY 总行数: {len(verify)}")
print(f"≥8 字: {len(long)} (~{len(long)/len(verify)*100:.0f}%)")
print(f"<8 字 (将判 invalid): {len(short)}")
print()

# 抽查 ≥8 字的边缘行（8-15 字）看看有没有垃圾
for _, r in long[long['max_len'] <= 15].iterrows():
    print(f"id={r['row_id']:>8s} | {r['COUNTRY_CODE']} | {r['max_len']:>2d} | "
          f"B='{r['b']}' | T='{r['t']}'")

print()

# 也看看 ≥8 字中是否有明显垃圾（长但无意义的）
suspicious = []
for _, r in long.iterrows():
    text = (r['b'] + ' ' + r['t']).lower()
    # 重复字母/无意义模式
    pass
# 手动看看最长的一些
for _, r in long.nlargest(10, 'max_len').iterrows():
    print(f"id={r['row_id']:>8s} | {r['COUNTRY_CODE']} | L={r['max_len']:>3d} | "
          f"B='{r['b']}' | T='{r['t']}'")
