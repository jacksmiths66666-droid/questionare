import pandas as pd, re
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

queue = pd.read_csv('outputs/screening_v3/tisp_v3_review_queue.csv', dtype=str, keep_default_na=False)
high = queue[queue['screening_tier'] == 'HIGH'].sort_values('row_id').copy()

def analyze_response(text):
    """分析单条开放题质量"""
    t = str(text).strip()
    if not t or t.lower() in ('nan', 'na', '-99', 'none', ''):
        return {'len': 0, 'empty': True, 'gibberish': False, 'text': ''}
    
    n = len(t)
    no_spaces = re.sub(r'\s', '', t)
    from collections import Counter
    char_counts = Counter(no_spaces.lower())
    import math
    entropy = -sum((c/len(no_spaces)) * math.log2(c/len(no_spaces)) for c in char_counts.values()) if no_spaces else 0
    adj_entropy = entropy / (math.log2(len(no_spaces)) if len(no_spaces) > 1 else 1)
    
    symbols = sum(1 for c in no_spaces if not c.isalnum() and not c.isspace())
    gibberish = (adj_entropy < 0.3 and entropy < 2.0) or (symbols / max(len(no_spaces),1) > 0.7)
    
    return {
        'len': n, 'empty': False, 'gibberish': gibberish,
        'text': t[:200]
    }

def judge_row(row):
    """逐行判断HIGH数据：有效/无效"""
    b = analyze_response(row['BENEFIT_OPEN'])
    t = analyze_response(row['TRUST_OPEN'])
    
    total_len = b['len'] + t['len']
    both_empty = b['empty'] and t['empty']
    both_gib = b['gibberish'] or t['gibberish']
    only_one = (b['empty'] and not t['empty']) or (not b['empty'] and t['empty'])
    
    # ── invalid ──
    if both_empty:
        return 'invalid', '两题都空'
    if both_gib:
        return 'invalid', '含乱码'
    
    b_text = b['text'].lower().strip().rstrip('.')
    t_text = t['text'].lower().strip().rstrip('.')
    auto_kw = {'yes', 'no', 'good'}
    
    if not b['empty'] and b['len'] <= 3 and b_text in auto_kw and t['empty']:
        return 'invalid', '一题敷衍(Yes/No)+另一题空'
    if not t['empty'] and t['len'] <= 3 and t_text in auto_kw and b['empty']:
        return 'invalid', '一题敷衍(Yes/No)+另一题空'
    if not b['empty'] and b['len'] <= 2 and t['empty']:
        return 'invalid', '一题几无内容+另一题空'
    if not t['empty'] and t['len'] <= 2 and b['empty']:
        return 'invalid', '一题几无内容+另一题空'
    
    # ── valid2: 两题都有实际内容，或有1-2句完整回答 ──
    if not b['empty'] and not t['empty']:
        if b['len'] >= 15 and t['len'] >= 15:
            return 'valid2', '两题都有实质内容(各≥15字)'
        if b['len'] >= 30 or t['len'] >= 30:
            return 'valid2', '至少一题回答充实'
    
    # ── valid1: 一题有内容，另一题短或空 ──
    if not b['empty'] and b['len'] >= 15:
        return 'valid1', f'BENEFIT有内容({b["len"]}字), TRUST{"空" if t["empty"] else "短"}'
    if not t['empty'] and t['len'] >= 15:
        return 'valid1', f'TRUST有内容({t["len"]}字), BENEFIT{"空" if b["empty"] else "短"}'
    
    if not b['empty'] and b['len'] >= 8:
        # 短文本质量检测：低元音比例→键盘乱敲/无意义字符堆叠
        b_clean = re.sub(r'\s', '', b_text)
        if b_clean:
            vowels_b = sum(1 for c in b_clean if c in 'aeiouaeiouàáâãäåèéêëìíîïòóôõöùúûü')
            unique_b = len(set(b_clean))
            vowel_ratio_b = vowels_b / len(b_clean)
            unique_ratio_b = unique_b / len(b_clean)
            if vowel_ratio_b < 0.15 and unique_ratio_b < 0.6 and len(b_clean) > 3:
                return 'invalid', f'BENEFIT低元音/低多样性可疑({b["len"]}字)'
        return 'valid1', f'BENEFIT有基本内容({b["len"]}字)'
    if not t['empty'] and t['len'] >= 8:
        t_clean = re.sub(r'\s', '', t_text)
        if t_clean:
            vowels_t = sum(1 for c in t_clean if c in 'aeiouaeiouàáâãäåèéêëìíîïòóôõöùúûü')
            unique_t = len(set(t_clean))
            vowel_ratio_t = vowels_t / len(t_clean)
            unique_ratio_t = unique_t / len(t_clean)
            if vowel_ratio_t < 0.15 and unique_ratio_t < 0.6 and len(t_clean) > 3:
                return 'invalid', f'TRUST低元音/低多样性可疑({t["len"]}字)'
        return 'valid1', f'TRUST有基本内容({t["len"]}字)'
    
    # ── 剩下：有内容但极短 → invalid ──
    return 'invalid', f'内容极短(B={b["len"]}, T={t["len"]})'

results = []
for _, row in high.iterrows():
    decision, reason = judge_row(row)
    b_analysis = analyze_response(row['BENEFIT_OPEN'])
    t_analysis = analyze_response(row['TRUST_OPEN'])
    results.append({
        'row_id': row['row_id'],
        'country': row['COUNTRY_CODE'],
        'trigger': row['trigger_reason'],
        'ls': row['ls_max_run'],
        'benefit': str(row['BENEFIT_OPEN'])[:200],
        'trust': str(row['TRUST_OPEN'])[:200],
        'b_len': b_analysis['len'],
        't_len': t_analysis['len'],
        'total_len': b_analysis['len'] + t_analysis['len'],
        'b_gib': b_analysis['gibberish'],
        't_gib': t_analysis['gibberish'],
        'decision': decision,
        'reason': reason
    })

df = pd.DataFrame(results)
df.to_csv('outputs/screening_v3/high_autoreview_results.csv', index=False, encoding='utf-8-sig')

# 输出详细到txt
with open('outputs/screening_v3/high_autoreview.txt', 'w', encoding='utf-8') as f:
    f.write(f"HIGH 层逐行审查结果（160行）\n")
    f.write(f"{'='*100}\n\n")
    for _, r in df.iterrows():
        f.write(f"row_id={r['row_id']:>5s} | {r['country']} | {r['trigger']:<35s} | "
                f"ls={r['ls']:<4s} | len=B{r['b_len']}+T{r['t_len']}={r['total_len']}\n")
        f.write(f"  判定: {r['decision']:<7s} | 理由: {r['reason']}\n")
        f.write(f"  BENEFIT: {r['benefit']}\n")
        f.write(f"  TRUST:   {r['trust']}\n\n")

print(f"已输出: outputs/screening_v3/high_autoreview.txt")
print(f"\n判定分布:")
print(df['decision'].value_counts().to_string())
print(f"\n各trigger判定:")
for trig in df['trigger'].unique():
    sub = df[df['trigger']==trig]
    print(f"\n{trig} ({len(sub)}行):")
    print(sub['decision'].value_counts().to_string())
