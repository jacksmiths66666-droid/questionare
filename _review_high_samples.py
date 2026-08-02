import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pandas as pd
pd.set_option('display.max_colwidth', 120)
pd.set_option('display.width', 200)

queue = pd.read_csv('outputs/screening_v3/tisp_v3_review_queue.csv', dtype=str, keep_default_na=False)
high = queue[queue['screening_tier'] == 'HIGH'].copy()

# 加翻译列（如果有旧队列有翻译）
try:
    old = pd.read_csv('outputs/screening_v3/tisp_v3_review_annotated.csv', dtype=str, keep_default_na=False)
    old['row_id'] = old['row_id'].astype(int)
    high['row_id'] = high['row_id'].astype(int)
    # 有翻译的合并
    if 'BENEFIT_OPEN_ZH' in old.columns:
        high = high.merge(old[['row_id', 'BENEFIT_OPEN_ZH']], on='row_id', how='left')
except:
    pass

for reason in high['trigger_reason'].unique():
    sub = high[high['trigger_reason'] == reason]
    print(f"{'='*80}")
    print(f"  {reason}  ({len(sub)} 行)")
    print(f"{'='*80}")
    cols = ['row_id', 'COUNTRY_CODE', 'ls_max_run', 'md_score', 'oe_r',
            'BENEFIT_OPEN', 'TRUST_OPEN']
    if 'BENEFIT_OPEN_ZH' in high.columns:
        cols.append('BENEFIT_OPEN_ZH')
    show = sub[cols].head(5)
    for _, row in show.iterrows():
        print(f"\n  row_id={row['row_id']}  {row['COUNTRY_CODE']}  ls={row['ls_max_run']}  "
              f"md={row.get('md_score','?')}  oe={row.get('oe_r','?')}")
        print(f"  BENEFIT: {str(row['BENEFIT_OPEN'])[:100]}")
        print(f"  TRUST:   {str(row['TRUST_OPEN'])[:100]}")
        if 'BENEFIT_OPEN_ZH' in row.index and pd.notna(row['BENEFIT_OPEN_ZH']):
            print(f"  翻译:    {str(row['BENEFIT_OPEN_ZH'])[:100]}")
    print()
