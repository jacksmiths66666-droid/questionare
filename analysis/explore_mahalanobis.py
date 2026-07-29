"""mahalanobis_outlier 数据探索"""
import pandas as pd

pd.set_option('display.max_colwidth', 80)
pd.set_option('display.width', 300)

csv = pd.read_csv('outputs/screening_v3/tisp_v3_review_queue.csv')
md = csv[csv['trigger_reason'] == 'mahalanobis_outlier'].copy()

def open_len(row):
    b = str(row['BENEFIT_OPEN']).strip() if pd.notna(row['BENEFIT_OPEN']) else ''
    t = str(row['TRUST_OPEN']).strip() if pd.notna(row['TRUST_OPEN']) else ''
    return max(len(b), len(t))

md['olen'] = md.apply(open_len, axis=1)

print('=== 短回答 <10字 ===')
short = md[md['olen'] <= 10]
print(f'共 {len(short)} 条')
for _, r in short.head(8).iterrows():
    rid = int(r['row_id']); cc = r['COUNTRY_CODE']; sc = round(r['md_score'], 2)
    b = str(r['BENEFIT_OPEN']).strip() if pd.notna(r['BENEFIT_OPEN']) else ''
    t = str(r['TRUST_OPEN']).strip() if pd.notna(r['TRUST_OPEN']) else ''
    text = (b if b else t)[:40]
    b_zh = str(r['BENEFIT_OPEN_ZH']).strip() if pd.notna(r['BENEFIT_OPEN_ZH']) else ''
    t_zh = str(r['TRUST_OPEN_ZH']).strip() if pd.notna(r['TRUST_OPEN_ZH']) else ''
    text_zh = (b_zh if b_zh else t_zh)[:40]
    print(f'  {rid} {cc} MD={sc} | 原文: {text:40s} | 翻译: {text_zh}')

print()
print('=== 中等回答 15-50字 ===')
mid = md[(md['olen'] >= 15) & (md['olen'] <= 50)]
print(f'共 {len(mid)} 条，展示前6:')
for _, r in mid.head(6).iterrows():
    rid = int(r['row_id']); cc = r['COUNTRY_CODE']; sc = round(r['md_score'], 2)
    b = str(r['BENEFIT_OPEN']).strip() if pd.notna(r['BENEFIT_OPEN']) else ''
    t = str(r['TRUST_OPEN']).strip() if pd.notna(r['TRUST_OPEN']) else ''
    text = (b if b else t)[:60]
    print(f'  {rid} {cc} MD={sc} | {text}')

print()
print('=== 长回答 >50字 ===')
long = md[md['olen'] > 50]
print(f'共 {len(long)} 条，展示前6:')
for _, r in long.head(6).iterrows():
    rid = int(r['row_id']); cc = r['COUNTRY_CODE']; sc = round(r['md_score'], 2)
    b = str(r['BENEFIT_OPEN']).strip() if pd.notna(r['BENEFIT_OPEN']) else ''
    t = str(r['TRUST_OPEN']).strip() if pd.notna(r['TRUST_OPEN']) else ''
    text = (b if b else t)[:60]
    print(f'  {rid} {cc} MD={sc} | {text}')

print()
print('=== 翻译看不太懂的 ===')
for _, r in md.iterrows():
    b_zh = str(r['BENEFIT_OPEN_ZH']).strip() if pd.notna(r['BENEFIT_OPEN_ZH']) else ''
    t_zh = str(r['TRUST_OPEN_ZH']).strip() if pd.notna(r['TRUST_OPEN_ZH']) else ''
    text_zh = b_zh if b_zh else t_zh
    if text_zh and len(text_zh) <= 8:
        rid = int(r['row_id']); cc = r['COUNTRY_CODE']; sc = round(r['md_score'], 2)
        print(f'  {rid} {cc} MD={sc} | ZH: {text_zh}')
