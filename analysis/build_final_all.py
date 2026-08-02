"""构建最终版全量数据：按 valid1/valid2/invalid/normal 分类输出。

输出：
  - tisp_v3_final_all.csv       全量数据（按类别排序，含 final_decision）
  - tisp_v3_final_all.xlsx      按类别分 sheet 的 Excel（含汇总表）
"""
import pandas as pd, numpy as np
from pathlib import Path

flags = pd.read_csv('outputs/screening_v3/tisp_v3_flags.csv', dtype=str, keep_default_na=False)
queue = pd.read_csv('outputs/screening_v3/tisp_v3_review_queue.csv', dtype=str, keep_default_na=False)
flags['row_id'] = flags['row_id'].astype(np.int64)
queue['row_id'] = queue['row_id'].astype(np.int64)

merged = flags.merge(queue[['row_id','final_decision']], on='row_id', how='left')
merged['final_decision'] = merged['final_decision'].fillna('normal')

OUT_DIR = Path('outputs/screening_v3')
OUT_DIR.mkdir(parents=True, exist_ok=True)

# === 1. CSV: 全量数据按 final_decision 排序 ===
order = {'invalid': 0, 'valid2': 1, 'valid1': 2, 'normal': 3}
merged['_sort'] = merged['final_decision'].map(order)
merged = merged.sort_values(['_sort', 'row_id']).drop(columns=['_sort'])

csv_path = OUT_DIR / 'tisp_v3_final_all.csv'
merged.to_csv(csv_path, index=False, encoding='utf-8-sig')
print(f'CSV: {csv_path} ({len(merged)} 行 x {len(merged.columns)} 列)')

# === 2. XLSX: 分 sheet ===
import xlsxwriter
xlsx_path = OUT_DIR / 'tisp_v3_final_all.xlsx'
wb = xlsxwriter.Workbook(str(xlsx_path))

hdr_fmt = wb.add_format({'bold': True, 'bg_color': '#4472C4', 'font_color': 'white',
                         'align': 'center', 'valign': 'vcenter', 'text_wrap': True})
fills = {
    '有效-valid1': wb.add_format({'bg_color': '#E8F5E9'}),
    '有效-valid2': wb.add_format({'bg_color': '#FFF8E1'}),
    '无效-invalid': wb.add_format({'bg_color': '#FFEBEE'}),
}

cats = [
    ('有效-valid1', merged['final_decision']=='valid1', '#E8F5E9'),
    ('有效-valid2', merged['final_decision']=='valid2', '#FFF8E1'),
    ('无效-invalid', merged['final_decision']=='invalid', '#FFEBEE'),
    ('正常-normal', merged['final_decision']=='normal', None),
]

cols = list(merged.columns)
for name, mask, bg in cats:
    ws = wb.add_worksheet(name)
    ws.freeze_panes(1, 0)
    ws.set_column(0, len(cols)-1, 10)  # default column width
    # header
    for c, col_name in enumerate(cols):
        ws.write(0, c, col_name, hdr_fmt)
    # data rows
    data = merged[mask]
    fmt = wb.add_format({'bg_color': bg}) if bg else None
    for r_idx, (_, row) in enumerate(data.iterrows(), start=1):
        for c_idx, val in enumerate(row):
            ws.write(r_idx, c_idx, val, fmt)

# summary sheet
ws = wb.add_worksheet('汇总')
ws.write(0, 0, 'final_decision', hdr_fmt)
ws.write(0, 1, 'n', hdr_fmt)
ws.write(0, 2, 'pct', hdr_fmt)
vc = merged['final_decision'].value_counts()
for i, (k, v) in enumerate(vc.items(), start=1):
    ws.write(i, 0, k)
    ws.write(i, 1, int(v))
    ws.write(i, 2, round(v / len(merged) * 100, 2))

wb.close()
print(f'XLSX: {xlsx_path}')

print(f'\n=== 最终版全量数据已生成 ===')
for k in ['invalid', 'valid2', 'valid1', 'normal']:
    print(f'  {k}: {int(vc.get(k, 0))}')
