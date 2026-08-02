"""
VERIFY tier auto-review — tightened V3
Rule: max(answer length) >= 12 chars → valid, else invalid
"""
import pandas as pd, numpy as np
from pathlib import Path

BASE = Path.cwd()
Q_PATH = BASE / 'outputs' / 'screening_v3' / 'tisp_v3_review_queue.csv'
OUT_DIR = BASE / 'outputs' / 'screening_v3'

queue = pd.read_csv(Q_PATH, dtype=str, keep_default_na=False)
verify = queue[queue['screening_tier'] == 'VERIFY'].copy()
mask = queue['screening_tier'] == 'VERIFY'

def clean(t):
    t = str(t).strip()
    return '' if t.lower() in ('', 'nan', 'na', '-99', 'none') else t

verify['b'] = verify['BENEFIT_OPEN'].apply(clean)
verify['t'] = verify['TRUST_OPEN'].apply(clean)
verify['_len'] = verify[['b','t']].apply(lambda r: max(len(r['b']), len(r['t'])), axis=1)

# 判定
THRESHOLD = 12
verify['_valid'] = verify['_len'] >= THRESHOLD
verify['auto_decision'] = verify['_valid'].replace({True: 'valid', False: 'invalid'})
verify['auto_reason'] = verify.apply(lambda r:
    '' if r['auto_decision'] == 'valid'
    else f"两题最长仅{r['_len']}字(<{THRESHOLD})",
    axis=1
)

# 更新回原 queue
queue.loc[mask, 'auto_decision'] = verify['auto_decision'].values
queue.loc[mask, 'auto_reason']   = verify['auto_reason'].values

# 统计
n = len(verify)
nv = (verify['auto_decision'] == 'valid').sum()
ni = (verify['auto_decision'] == 'invalid').sum()
print(f"VERIFY 总计: {n}")
print(f"  valid:   {nv} ({nv/n*100:.1f}%)")
print(f"  invalid: {ni} ({ni/n*100:.1f}%)")

# 写出更新后的 queue
queue.to_csv(Q_PATH, index=False)
print(f"\n已更新: {Q_PATH}")

# 也写出 VERIFY 明细
out_file = OUT_DIR / 'verify_autoreview_results.csv'
verify[['row_id','COUNTRY_CODE','BENEFIT_OPEN','TRUST_OPEN','_len','auto_decision','auto_reason']]\
    .sort_values(['auto_decision','_len'])\
    .rename(columns={'_len':'max_len'})\
    .to_csv(out_file, index=False)
print(f"写入: {out_file}")

# 输出验证报告
invalid_rows = verify[verify['auto_decision'] == 'invalid']
valid_rows   = verify[verify['auto_decision'] == 'valid']

rpt = [
    "=" * 60,
    "VERIFY Tier Auto-Review Report (V3 — tightened)",
    "=" * 60,
    f"阈值: max(answer_char_len) >= {THRESHOLD} → valid",
    f"总行: {n}",
    f"valid:   {nv} ({nv/n*100:.1f}%)",
    f"invalid: {ni} ({ni/n*100:.1f}%)",
    "",
    "═" * 60,
    "INVALID ROWS",
    "═" * 60,
]
for _, r in invalid_rows.iterrows():
    rpt.append(f"id={r['row_id']} | {r['COUNTRY_CODE']} | L={r['_len']} | "
               f"B='{r['BENEFIT_OPEN']}' | T='{r['TRUST_OPEN']}'")

rpt += [
    "",
    "═" * 60,
    "VALID ROWS (by length ascending, first 30)",
    "═" * 60,
]
for _, r in valid_rows.sort_values('_len').head(30).iterrows():
    rpt.append(f"id={r['row_id']} | {r['COUNTRY_CODE']} | L={r['_len']:>3d} | "
               f"B='{str(r['BENEFIT_OPEN'])[:60]}'")

report_path = OUT_DIR / 'verify_autoreview_report.txt'
Path(report_path).write_text('\n'.join(rpt), encoding='utf-8')
print(f"报告: {report_path}")

# 同步到 DELIVERABLES
DELIV = BASE / '论文提交关键东西' / 'data'
import shutil
for f in ['tisp_v3_review_queue.csv', 'verify_autoreview_results.csv', 'verify_autoreview_report.txt']:
    shutil.copy2(OUT_DIR / f, DELIV / f)
    print(f"同步 → {DELIV / f}")
