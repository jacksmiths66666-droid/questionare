"""
VERIFY 层内容审核（176 行）
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import pandas as pd, shutil
from pathlib import Path

BASE = Path.cwd()
Q_PATH = BASE / 'outputs' / 'screening_v3' / 'tisp_v3_review_queue.csv'
OUT_DIR = BASE / 'outputs' / 'screening_v3'

queue = pd.read_csv(Q_PATH, dtype=str, keep_default_na=False)
mask = queue['screening_tier'] == 'VERIFY'
v = queue[mask].copy()

def clean(t):
    t = str(t).strip()
    return '' if t.lower() in ('', 'nan', 'na', '-99', 'none') else t

v['b'] = v['BENEFIT_OPEN'].apply(clean)
v['t'] = v['TRUST_OPEN'].apply(clean)

# 明确无效模式
VAGUE_WORDS = frozenset({'ada','bisa','dapat','ok','okay','ya','tidak','na'})
SINGLE_LETTERS = frozenset({'y','n'})
GIBBERISH = frozenset({'jh','kjg'})  # 键盘乱敲的已识别 pattern

def decide(row):
    b, t = row['b'], row['t']
    combined_clean = (b + t).replace(' ', '')
    
    # 空
    if not combined_clean:
        return 'invalid', '两题都为空'
    
    # 非语言: 2字以内且无字母（如单符号）
    if len(combined_clean) <= 2 and not any(c.isalpha() for c in combined_clean):
        return 'invalid', '非语言符号'
    
    # 单字母
    if len(combined_clean) == 1 and combined_clean.lower() in SINGLE_LETTERS:
        return 'invalid', '单字母'
    
    # 键盘乱敲
    tokens = set(combined_clean.lower())
    if tokens & GIBBERISH or (len(combined_clean) <= 5 and not any(c in 'aeiou' for c in combined_clean)):
        return 'invalid', '非语言/键盘乱敲'
    
    # 泛词
    for field, label in [(b, 'BENEFIT'), (t, 'TRUST')]:
        if not field:
            continue
        words = [w.strip('.,!?;:').lower() for w in field.split() if w.strip()]
        if len(words) == 1 and words[0] in VAGUE_WORDS:
            return 'invalid', f'{label}: 泛词 "{field}"'
    
    return 'valid', ''

v['_dec'] = v.apply(decide, axis=1)
v['decision'] = v['_dec'].apply(lambda x: x[0])
v['reason'] = v['_dec'].apply(lambda x: x[1])

queue.loc[mask, 'decision'] = v['decision'].values
queue.loc[mask, 'reason'] = v['reason'].values

queue.to_csv(Q_PATH, index=False)
v[['row_id','COUNTRY_CODE','BENEFIT_OPEN','TRUST_OPEN','decision','reason']]\
    .to_csv(OUT_DIR / 'verify_review_results.csv', index=False)

DELIV = BASE / '论文提交关键东西' / 'data'
for f in ['tisp_v3_review_queue.csv', 'verify_review_results.csv']:
    shutil.copy2(OUT_DIR / f, DELIV / f)

n = len(v)
nv = (v['decision'] == 'valid').sum()
ni = (v['decision'] == 'invalid').sum()
print(f"VERIFY: {n} -> valid={nv} invalid={ni}")
for _, r in v[v['decision']=='invalid'].iterrows():
    print("  id=%s | %s | %s | B='%s' | T='%s'" % (
        r['row_id'], r['COUNTRY_CODE'], r['reason'],
        str(r['BENEFIT_OPEN']), str(r['TRUST_OPEN'])))
print("done")
