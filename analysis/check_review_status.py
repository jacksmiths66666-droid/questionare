import pandas as pd
df = pd.read_excel('outputs/screening_v3/review_batch_A_431.xlsx', sheet_name='BatchA_新增复核')
print('Shape:', df.shape)
print('review_status dtype:', df['review_status'].dtype)
vals = df['review_status'].value_counts(dropna=False)
print('review_status dist:')
print(vals.to_string())
# Show some samples
for _, r in df[df['review_status'].notna() & (df['review_status'].astype(str).str.strip() != '')].head(20).iterrows():
    rs = r['review_status']
    print(f'  #{r["row_id"]}: status={repr(rs)} tier={r["review_tier"]}')
