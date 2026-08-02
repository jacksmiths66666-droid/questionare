import pandas as pd

final = pd.read_csv("outputs/screening_v3/tisp_v3_analysis_ready_v2.csv", low_memory=False)

print("=== 最终数据分布 ===")
dist = final['final_decision'].value_counts()
for k, v in dist.items():
    print(f"  {k}: {v} ({v/len(final)*100:.2f}%)")
print(f"  总计: {len(final)}")

# 计算 valid 比例
valid = len(final[final['final_decision'].isin(['normal', 'valid1', 'valid2'])])
invalid = len(final[final['final_decision'] == 'invalid'])
print(f"\n有效率: {valid}/{len(final)} = {valid/len(final)*100:.2f}%")
print(f"无效率: {invalid}/{len(final)} = {invalid/len(final)*100:.2f}%")

# 对比学长的预期
print(f"\n=== 与学长预期对比 ===")
print(f"学长期望有效率: ~80%")
print(f"实际有效率: {valid/len(final)*100:.2f}%")
print(f"差异: +{(valid/len(final)*100 - 80):.2f}%")

# 检查 valid1 的内容质量
print(f"\n=== valid1 样本检查 ===")
valid1 = final[final['final_decision'] == 'valid1'].head(10)
for _, r in valid1.iterrows():
    ben = str(r.get('BENEFIT_OPEN', ''))[:50]
    trust = str(r.get('TRUST_OPEN', ''))[:50]
    print(f"  #{r['row_id']} ({r['COUNTRY_CODE']}): B={ben} | T={trust}")
