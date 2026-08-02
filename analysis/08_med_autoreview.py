"""
MEDIUM tier auto-review — same tightened V3 rule
max(answer_char_len) >= 12 → valid, else invalid
"""
import pandas as pd, shutil
from pathlib import Path

BASE = Path.cwd()
Q_PATH = BASE / 'outputs' / 'screening_v3' / 'tisp_v3_review_queue.csv'
OUT_DIR = BASE / 'outputs' / 'screening_v3'

queue = pd.read_csv(Q_PATH, dtype=str, keep_default_na=False)
mask = queue['screening_tier'] == 'MEDIUM'
med = queue[mask].copy()

def clean(t):
    t = str(t).strip()
    return '' if t.lower() in ('', 'nan', 'na', '-99', 'none') else t

med['b'] = med['BENEFIT_OPEN'].apply(clean)
med['t'] = med['TRUST_OPEN'].apply(clean)
med['_len'] = med[['b','t']].apply(lambda r: max(len(r['b']), len(r['t'])), axis=1)

THRESHOLD = 12
med['auto_decision'] = med['_len'].ge(THRESHOLD).replace({True: 'valid', False: 'invalid'})
med['auto_reason'] = med.apply(lambda r:
    '' if r['auto_decision'] == 'valid'
    else f"两题最长仅{r['_len']}字(<{THRESHOLD})",
    axis=1
)

queue.loc[mask, 'auto_decision'] = med['auto_decision'].values
queue.loc[mask, 'auto_reason']   = med['auto_reason'].values

n = len(med)
nv = (med['auto_decision'] == 'valid').sum()
ni = (med['auto_decision'] == 'invalid').sum()
print(f"MEDIUM 总计: {n}")
print(f"  valid:   {nv} ({nv/n*100:.1f}%)")
print(f"  invalid: {ni} ({ni/n*100:.1f}%)")

queue.to_csv(Q_PATH, index=False)
print(f"已更新: {Q_PATH}")

# 明细
med[['row_id','COUNTRY_CODE','BENEFIT_OPEN','TRUST_OPEN','_len','auto_decision','auto_reason']]\
    .sort_values(['auto_decision','_len'])\
    .rename(columns={'_len':'max_len'})\
    .to_csv(OUT_DIR / 'med_autoreview_results.csv', index=False)

# 报告
inv = med[med['auto_decision'] == 'invalid'].sort_values('_len')
val = med[med['auto_decision'] == 'valid'].sort_values('_len')
lines = [
    "="*60,
    "MEDIUM Tier Auto-Review Report (V3 — tightened)",
    f"阈值: max(answer_char_len) >= {THRESHOLD} → valid",
    f"总行: {n}",
    f"valid:   {nv} ({nv/n*100:.1f}%)",
    f"invalid: {ni} ({ni/n*100:.1f}%)",
    "",
    "═"*60,
    f"INVALID ({ni} rows, showing all)",
    "═"*60,
]
for _, r in inv.iterrows():
    lines.append(f"id={r['row_id']:>8s} | {r['COUNTRY_CODE']} | L={r['_len']:>2d} | "
                 f"B='{str(r['BENEFIT_OPEN'])[:50]}' | T='{str(r['TRUST_OPEN'])[:50]}'")
lines += [
    "",
    "═"*60,
    "SAMPLE VALID (first 40, length ascending)",
    "═"*60,
]
for _, r in val.head(40).iterrows():
    lines.append(f"id={r['row_id']:>8s} | {r['COUNTRY_CODE']} | L={r['_len']:>3d} | "
                 f"B='{str(r['BENEFIT_OPEN'])[:50]}'")
lines += [
    "",
    f"... and {len(val)-40} more valid rows",
    "",
    "═"*60,
    "FINAL DATASET (71,922 rows) SUMMARY",
    "═"*60,
]
# 汇总全局 valid rate
# 非 queue 行: 直接用 final_decision
# queue 行   : 用 auto_decision（覆盖原 final_decision）
ar = pd.read_csv(BASE / 'outputs' / 'screening_v3' / 'tisp_v3_analysis_ready.csv', dtype=str, keep_default_na=False)
ar['_is_queued'] = ar['row_id'].isin(queue['row_id'])
ar['_queue_dec'] = ar['row_id'].map(queue.set_index('row_id')['auto_decision']).fillna('')
ar['_final'] = ar['_queue_dec'].where(ar['_is_queued'], ar['final_decision'])
ar['_valid'] = ar['_final'].isin(('valid', 'normal', 'valid1', 'valid2'))
valid_count = ar['_valid'].sum()
invalid_count = (~ar['_valid']).sum()
total = len(ar)

total = valid_count + invalid_count
lines += [
    f"total:  {total}",
    f"valid:  {valid_count} ({valid_count/total*100:.2f}%)",
    f"invalid:{invalid_count} ({invalid_count/total*100:.2f}%)",
]
Path(OUT_DIR / 'med_autoreview_report.txt').write_text('\n'.join(lines), encoding='utf-8')
print(f"报告: {OUT_DIR / 'med_autoreview_report.txt'}")

# 同步
DELIV = BASE / '论文提交关键东西' / 'data'
for f in ['tisp_v3_review_queue.csv', 'med_autoreview_results.csv', 'med_autoreview_report.txt']:
    shutil.copy2(OUT_DIR / f, DELIV / f)
    print(f"同步 → {DELIV / f}")
