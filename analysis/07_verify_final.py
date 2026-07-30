import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import pandas as pd

final = pd.read_csv("outputs/screening_v3/tisp_v3_analysis_ready.csv", dtype=str, keep_default_na=False)
flags = pd.read_csv("outputs/screening_v3/tisp_v3_flags.csv", dtype=str, keep_default_na=False)
queue = pd.read_csv("outputs/screening_v3/tisp_v3_review_queue.csv", dtype=str, keep_default_na=False)

print("=" * 60)
print("FINAL VERIFICATION")
print("=" * 60)
print(f"  行数: {len(final)}")
print(f"  列数: {len(final.columns)}")
vc = final['final_decision'].value_counts()
for v in ['normal', 'valid1', 'valid2', 'invalid']:
    n = vc.get(v, 0)
    print(f"  {v}: {n} ({n/len(final)*100:.2f}%)")
total_inv = vc.get('invalid', 0)
print(f"  有效率: {(len(final)-total_inv)/len(final)*100:.2f}%")

src = final[final['final_decision']=='invalid']['invalid_source'].value_counts()
print(f"\n  invalid 来源:")
for s, n in src.items():
    print(f"    {s}: {n}")
assert src.sum() == total_inv, f"来源总计 {src.sum()} != invalid 总数 {total_inv}"

# 关键列检查
assert 'both_len' in final.columns, "缺少 both_len"
assert 'invalid_source' in final.columns, "缺少 invalid_source"
assert len(final) == len(flags), f"行数不一致: {len(final)} vs {len(flags)}"

# 对比 flags 中的 Rule A/B 一致性
bl_check = final['both_len'].astype(int)
fa_check = (bl_check <= 5).sum()
fb_check = (final['ls_max_run'].astype(float) >= 17).sum()
print(f"\n  规则 A (<=5字): {fa_check}")
print(f"  规则 B (>=17): {fb_check}")

# 各国有效率
country = final.groupby('COUNTRY_CODE').agg(
    total=('row_id', 'size'),
    invalid=('final_decision', lambda x: (x == 'invalid').sum())
)
country['rate'] = (1 - country['invalid'] / country['total']) * 100
print(f"\n  最低有效率国家:")
for cc, r in country.nsmallest(5, 'rate').iterrows():
    print(f"    {cc}: {r['rate']:.1f}% ({r['total']}总/{r['invalid']}无效)")

print(f"\n{'='*60}")
print("VERIFICATION PASSED")
