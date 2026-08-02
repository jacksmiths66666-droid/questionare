import pandas as pd, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

queue = pd.read_csv('outputs/screening_v3/tisp_v3_review_queue.csv', dtype=str, keep_default_na=False)
ar = pd.read_csv('outputs/screening_v3/tisp_v3_analysis_ready.csv', dtype=str, keep_default_na=False)

med = queue[queue['screening_tier'] == 'MEDIUM'].copy()
def clean(t):
    t = str(t).strip()
    return '' if t.lower() in ('', 'nan', 'na', '-99', 'none') else t
med['b'] = med['BENEFIT_OPEN'].apply(clean)
med['t'] = med['TRUST_OPEN'].apply(clean)
med['_len'] = med[['b','t']].apply(lambda r: max(len(r['b']), len(r['t'])), axis=1)

# 基准: 非 MEDIUM 队列行
non_med_ids = set(queue[queue['screening_tier'] != 'MEDIUM']['row_id'])
ar['_is_q'] = ar['row_id'].isin(queue['row_id'])
ar['_is_m'] = ar['row_id'].isin(med['row_id'])
ar['_is_oth'] = ar['_is_q'] & ~ar['_is_m']

# 非 MEDIUM 队列行的最终决策
q_oth = ar[ar['_is_oth']].copy()
q_oth['_dec'] = q_oth['row_id'].map(queue.set_index('row_id')['auto_decision'])
print(f"非 MEDIUM 队列行: {len(q_oth)}")
print(f"  valid: {(q_oth['_dec']=='valid').sum()}")
print(f"  invalid: {(q_oth['_dec']=='invalid').sum()}")

# 非队列行
non_q = ar[~ar['_is_q']].copy()
nq_val = non_q['final_decision'].isin(('normal','valid1','valid2')).sum()
nq_inv = (~non_q['final_decision'].isin(('normal','valid1','valid2'))).sum()
print(f"\n非队列行: {len(non_q)}")
print(f"  valid: {nq_val}")
print(f"  invalid: {nq_inv}")

# 固定: non_queue + HIGH + VERIFY 的 valid 数
base_valid = nq_val + (q_oth['_dec']=='valid').sum()
base_invalid = nq_inv + (q_oth['_dec']=='invalid').sum()
print(f"\n固定 valid: {base_valid} 固定 invalid: {base_invalid}")
target_total_valid = int(71922 * 0.7756)
needed_med_valid = target_total_valid - base_valid
print(f"目标 77.56% valid = {target_total_valid}")
print(f"MEDIUM 需要 valid ≈ {needed_med_valid} ({needed_med_valid/16673*100:.1f}%)")

# 找合适的阈值
lens = sorted(med['_len'].unique())
for t in range(20, 301, 5):
    v = (med['_len'] >= t).sum()
    total_v = base_valid + v
    rate = total_v / 71922 * 100
    if abs(rate - 77.56) < 1.5 or t <= 50:
        print(f"≥{t:>3d}: 通={v:>5d}({v/16673*100:5.1f}%) 总valid={total_v:>5d} rate={rate:5.1f}%")
