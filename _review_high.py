import pandas as pd
import sys, io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

pd.set_option('display.max_colwidth', 200)
pd.set_option('display.width', 300)

queue = pd.read_csv('outputs/screening_v3/tisp_v3_review_queue.csv', dtype=str, keep_default_na=False)
high = queue[queue['screening_tier'] == 'HIGH'].copy()
high['row_id_int'] = high['row_id'].astype(int)

lines = []

for reason in high['trigger_reason'].unique():
    sub = high[high['trigger_reason'] == reason].sort_values('row_id')
    lines.append(f"\n{'='*80}")
    lines.append(f"  {reason}  ({len(sub)} 行)")
    lines.append(f"{'='*80}")
    for _, row in sub.iterrows():
        ben = str(row.get('BENEFIT_OPEN', ''))
        tru = str(row.get('TRUST_OPEN', ''))
        md_val = row.get('md_score', '?')
        try: md_val = f"{float(md_val):.2f}"
        except: pass
        lines.append(f"\n  row_id={row['row_id']} | {row['COUNTRY_CODE']} | "
                     f"ls={row.get('ls_max_run','?')} | md={md_val} | "
                     f"oe={row.get('oe_r','?')}")
        lines.append(f"  BENEFIT: {ben[:150]}")
        lines.append(f"  TRUST:   {tru[:150]}")

with open('outputs/screening_v3/high_review.txt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))

print(f"已输出 {len(high)} 行到 outputs/screening_v3/high_review.txt")
