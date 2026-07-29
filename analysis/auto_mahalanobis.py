"""mahalanobis_outlier 自动处理 + 分类"""
import pandas as pd, math

CSV = 'outputs/screening_v3/tisp_v3_review_queue.csv'
csv = pd.read_csv(CSV)
csv['final_decision'] = csv['final_decision'].astype(object)

md = csv[csv['trigger_reason'] == 'mahalanobis_outlier'].copy()

def olen(x):
    if pd.isna(x): return 0
    return len(str(x).strip())

def gib_code(x):
    if pd.isna(x): return False
    x = str(x).strip()
    if x in ('-99','-99.','99','.','..','...','/'): return True
    if len(x) <= 2 and not any(c.isalpha() for c in x): return True
    return False

# 计算长度
md = md.copy()
md['b_len'] = md['BENEFIT_OPEN'].apply(olen)
md['t_len'] = md['TRUST_OPEN'].apply(olen)
md['max_len'] = md[['b_len','t_len']].max(axis=1)

# 乱码 → invalid
md['b_gib'] = md['BENEFIT_OPEN'].apply(gib_code)
md['t_gib'] = md['TRUST_OPEN'].apply(gib_code)
md['is_gib'] = md['b_gib'] | md['t_gib']

# 自动写入
auto_invalid = md[md['is_gib']]['row_id'].values
for rid in auto_invalid:
    csv.loc[csv['row_id'] == rid, 'final_decision'] = 'invalid'

# 剩余分类
rest = md[~md['is_gib']].copy()

def classify(row):
    ml = row['max_len']
    if ml >= 50:
        return 'A-有效倾向'
    elif ml >= 20:
        return 'B-需判断(中长)'
    else:
        return 'C-需判断(短回答)'

rest['cat'] = rest.apply(classify, axis=1)
print('自动 invalid:', len(auto_invalid))
print()

for cat in ['A-有效倾向', 'B-需判断(中长)', 'C-需判断(短回答)']:
    sub = rest[rest['cat'] == cat]
    print(f'{cat}: {len(sub)} 条')
    if cat == 'A-有效倾向':
        # 写空白
        for rid in sub['row_id'].values:
            csv.loc[csv['row_id'] == rid, 'final_decision'] = ''
        print('  -> 已自动填入空白')

# 验证
csv.to_csv(CSV, index=False, encoding='utf-8-sig')
print()
print('写入完成')
