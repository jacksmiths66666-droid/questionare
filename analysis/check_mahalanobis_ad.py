"""检查 mahalanobis A/D 自动处理是否有疏漏"""
import pandas as pd

csv = pd.read_csv('outputs/screening_v3/tisp_v3_review_queue.csv')
md = csv[csv['trigger_reason'] == 'mahalanobis_outlier'].copy()

def olen(x):
    if pd.isna(x): return 0
    return len(str(x).strip())

def gib_code(x):
    if pd.isna(x): return False
    x = str(x).strip()
    if x in ('-99', '-99.', '99', '.', '..', '...', '/'): return True
    if len(x) <= 2 and not any(c.isalpha() for c in x): return True
    return False

md['b_gib'] = md['BENEFIT_OPEN'].apply(gib_code)
md['t_gib'] = md['TRUST_OPEN'].apply(gib_code)
md['is_gib'] = md['b_gib'] | md['t_gib']
md['b_len'] = md['BENEFIT_OPEN'].apply(olen)
md['t_len'] = md['TRUST_OPEN'].apply(olen)
md['max_len'] = md[['b_len', 't_len']].max(axis=1)

# ── D 检查 ──
d = md[md['is_gib']]
d_ok = d[d['final_decision'] == 'invalid']
d_miss = d[d['final_decision'] != 'invalid']
print('=== D-无效倾向 ===')
print('应标invalid:', len(d))
print('已标invalid:', len(d_ok))
print('漏掉:', len(d_miss))
if len(d_miss) > 0:
    for _, r in d_miss.iterrows():
        rid = int(r['row_id'])
        dec = str(r['final_decision'])
        b = str(r['BENEFIT_OPEN']).strip() if pd.notna(r['BENEFIT_OPEN']) else '(空)'
        t = str(r['TRUST_OPEN']).strip() if pd.notna(r['TRUST_OPEN']) else '(空)'
        print('  漏:', rid, r['COUNTRY_CODE'], 'BEN=' + b, 'TRU=' + t, 'dec=' + dec)

# ── A 检查 ──
a = md[(~md['is_gib']) & (md['max_len'] >= 50)]
a_ok = a[a['final_decision'].isna() | (a['final_decision'] == '')]
a_miss = a[a['final_decision'].notna() & (a['final_decision'] != '')]
print()
print('=== A-有效倾向 ===')
print('应标空白:', len(a))
print('已标空白:', len(a_ok))
print('有值(需检查):', len(a_miss))
if len(a_miss) > 0:
    for _, r in a_miss.iterrows():
        rid = int(r['row_id'])
        dec = str(r['final_decision'])
        print('  ', rid, r['COUNTRY_CODE'], 'dec=' + dec)

# ── 交叉检查 ──
print()
print('=== 交叉检查 ===')
a_gib = md[md['is_gib'] & (md['max_len'] >= 50)]
print('既是gib又是>50字:', len(a_gib), '(应为0)')

non_gib_short_blank = md[(~md['is_gib']) & (md['max_len'] < 50) & (md['final_decision'].isna() | (md['final_decision'] == ''))]
print('非gib且<50字但已标空白:', len(non_gib_short_blank), '(应为0)')

# ── D 中有没有短于50字但没被识别为gib的 ──
d_short = md[(md['is_gib']) & (md['max_len'] < 50)]
print('gib且<50字:', len(d_short), '(正常)')

# ── 全量数据最终分布 ──
print()
print('=== mahalanobis 最终分布 ===')
print(md['final_decision'].value_counts(dropna=False))
