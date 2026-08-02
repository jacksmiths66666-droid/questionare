import pandas as pd, sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from pathlib import Path

BASE = Path('outputs/screening_v3')

# 1. 原始数据量
raw = pd.read_csv(r'D:\开山\收集数据\081\D081_TISP\dataset.csv', dtype=str, keep_default_na=False)
print(f"原始数据: {len(raw)}")

# 2. metadata
with open(BASE / 'tisp_v3_metadata.json', 'r', encoding='utf-8') as f:
    meta = json.load(f)
print(f"\n=== metadata ===")
print(json.dumps(meta.get('stage_counts', {}), indent=1, ensure_ascii=False))

# 3. signal summary
sig = pd.read_csv(BASE / 'tisp_v3_signal_summary.csv', dtype=str)
print(f"\n=== signal summary ===")
print(sig.to_string())

# 4. analysis_ready 分布
ar = pd.read_csv(BASE / 'tisp_v3_analysis_ready.csv', dtype=str, keep_default_na=False)
print(f"\n=== analysis_ready ({len(ar)}) ===")
print(f"final_decision: {ar['final_decision'].value_counts().to_dict()}")
print(f"signal_count: {ar['signal_count'].value_counts().sort_index().to_dict()}")
print(f"tier: {ar['screening_tier'].value_counts().to_dict()}")
