"""
MEDIUM non-longstring 行内容审核
规则:
1. 两题都空 → invalid
2. 内容为空 / 单字母 / 键盘乱敲 / 无意义符号 → invalid  
3. 写了真实语言且与问题相关 → valid

输出两份: 全量结果 + 边界行清单（供人工核验）
"""
import pandas as pd, sys, io, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from pathlib import Path
import unicodedata

def has_letter(s):
    """检查字符串是否包含任意书写系统的字母字符"""
    for c in s:
        if unicodedata.category(c).startswith('L'):
            return True
    return False

def has_vowel(s):
    """检查字符串是否包含元音（拉丁/西里尔/希腊等）"""
    # 常见书写系统的元音集
    latin_vowels = set('aeiouAEIOU')
    cyrillic_vowels = set('аеёиоуыэюяАЕЁИОУЫЭЮЯ')
    greek_vowels = set('αεηιουωΑΕΗΙΟΥΩ')
    korean_jungsung = set('ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ')
    for c in s:
        if c in latin_vowels or c in cyrillic_vowels or c in greek_vowels or c in korean_jungsung:
            return True
    # CJK 和阿拉伯/希伯来通常不标记"元音"（用符号表示），默认宽松处理
    for c in s:
        script = unicodedata.name(c, '')
        if any(kw in script for kw in ['CJK', 'ARABIC', 'HEBREW', 'HIRAGANA', 'KATAKANA', 'HANGUL']):
            return True
    return False

BASE = Path.cwd()
Q_PATH = BASE / 'outputs' / 'screening_v3' / 'tisp_v3_review_queue.csv'
OUT_DIR = BASE / 'outputs' / 'screening_v3'

queue = pd.read_csv(Q_PATH, dtype=str, keep_default_na=False)
med = queue[queue['screening_tier'] == 'MEDIUM'].copy()

for c in ['signal_attention','signal_longstring','signal_mahalanobis','signal_odd_even']:
    med[c] = pd.to_numeric(med[c], errors='coerce').fillna(0).astype(int)

med_nls = med[(med['signal_longstring'] == 0) & 
              ((med['signal_odd_even'] == 1) | (med['signal_mahalanobis'] == 1) | (med['signal_attention'] == 1))].copy()

def clean(t):
    t = str(t).strip()
    return '' if t.lower() in ('', 'nan', 'na', '-99', 'none') else t

med_nls['b'] = med_nls['BENEFIT_OPEN'].apply(clean)
med_nls['t'] = med_nls['TRUST_OPEN'].apply(clean)

# 无效模式
NON_WORDS = frozenset({'y','n','0','1','2','3','4','5'})
VAGUE_WORDS = frozenset({'ada','bisa','dapat','ok','okay','ya','tidak','na','ni','ne','има'})
GIBBERISH_PATTERNS = [
    (lambda s: len(s) <= 3 and has_letter(s) and not has_vowel(s), '无元音乱敲'),
    (lambda s: len(s) > 1 and re.match(r'^(.)\1+$', s), '重复单字符'),
    (lambda s: not has_letter(s), '纯非字母'),
]

def is_gibberish(text):
    for pattern, reason in GIBBERISH_PATTERNS:
        if pattern(text):
            return reason
    return None

results = []
for _, r in med_nls.iterrows():
    rid = r['row_id']
    cc = r['COUNTRY_CODE']
    b = r['b']
    t = r['t']
    
    signals = []
    if r['signal_odd_even'] == 1: signals.append('OE')
    if r['signal_mahalanobis'] == 1: signals.append('MD')
    if r['signal_attention'] == 1: signals.append('AT')
    sig_str = '+'.join(signals)
    
    combined_clean = (b + t).replace(' ', '')
    
    # 1. 两题都空
    if not combined_clean:
        results.append((rid, cc, sig_str, b, t, 'invalid', '两题都空'))
        continue
    
    # 2. 检查各字段
    field_results = []
    for field, label in [(b, 'B'), (t, 'T')]:
        if not field:
            field_results.append((label, '', '空'))
            continue
        f_clean = field.strip().lower()
        # 单字母/数字
        if len(f_clean) <= 1 and f_clean in NON_WORDS:
            field_results.append((label, field, '单字符'))
            continue
        # 键盘乱敲
        g_res = is_gibberish(f_clean)
        if g_res:
            field_results.append((label, field, g_res))
            continue
        # 泛词
        words = [w.strip('.,!?;:').lower() for w in field.split() if w.strip()]
        if len(words) == 1 and words[0] in VAGUE_WORDS:
            field_results.append((label, field, '泛词'))
            continue
        # 短且无意义模式: 3-5 字符, 无实义词
        if len(field.strip()) <= 5:
            # 检查是否像是个有意义的词（含字母+元音）
            if not has_vowel(f_clean):
                field_results.append((label, field, '短无元音'))
                continue
        
        field_results.append((label, field, ''))  # 空=通过
    
    # 如果所有非空字段都是无效 → invalid
    non_empty_fields = [(l, v, st) for l, v, st in field_results if v]
    if non_empty_fields and all(st != '' for _, _, st in non_empty_fields):
        reasons = [f"{l}:{st}" for l, v, st in non_empty_fields]
        results.append((rid, cc, sig_str, b, t, 'invalid', '; '.join(reasons)))
        continue
    
    # 有效: 至少一个字段通过了检查
    results.append((rid, cc, sig_str, b, t, 'valid', ''))

# 输出
df = pd.DataFrame(results, columns=['row_id','COUNTRY_CODE','signal','BENEFIT_OPEN','TRUST_OPEN','decision','reason'])
n = len(df)
nv = (df['decision'] == 'valid').sum()
ni = (df['decision'] == 'invalid').sum()
print(f"总计: {n}  valid={nv}  invalid={ni}")

# 写出全量结果
df.to_csv(OUT_DIR / 'med_nls_review_results.csv', index=False)
print(f"已写入: {OUT_DIR / 'med_nls_review_results.csv'}")

# 写出边界行（invalid 中需要人工核验的）
borderline = df[(df['decision'] == 'invalid') & (df['reason'] != '两题都空')].copy()
print(f"\n边界行（需核验）: {len(borderline)}")
for _, r in borderline.iterrows():
    print(f"  id={r['row_id']:>8s} | {r['COUNTRY_CODE']} | [{r['signal']}] | {r['reason']} | B='{r['BENEFIT_OPEN']}' | T='{r['TRUST_OPEN']}'")

borderline.to_csv(OUT_DIR / 'med_nls_borderline.csv', index=False)
