import pandas as pd, sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

SRC = 'outputs/screening_v3/tisp_v3_final_all.csv'
OUT = 'outputs/screening_v3/tisp_v3_final_all.xlsx'

df = pd.read_csv(SRC, dtype=str, keep_default_na=False, low_memory=False)
print(f'载入 {len(df)} 行 × {len(df.columns)} 列')

import xlsxwriter
wb = xlsxwriter.Workbook(OUT, {'constant_memory': True, 'strings_to_numbers': False})
ws = wb.add_worksheet('final_all')

# 样式
hdr = wb.add_format({'bold': True, 'font_color': 'white', 'bg_color': '#1F4E79',
                     'border': 1, 'align': 'center', 'valign': 'vcenter'})
plain = wb.add_format({'border': 1})
b = wb.add_format({'border': 1, 'bg_color': '#F2F2F2'})

# 表头
for c, col in enumerate(df.columns):
    ws.write(0, c, col, hdr)

# 批量写数据
rows = df.values.tolist()
for r, row in enumerate(rows, 1):
    ws.write_row(r, 0, row)
print('数据写入完成')

# 关键列索引
def ci(name):
    return df.columns.get_loc(name)

rng = lambda ci: f'{xlsxwriter.utility.xl_col_to_name(ci)}2:{xlsxwriter.utility.xl_col_to_name(ci)}{len(df)+1}'

fd, src, tier, sig = ci('final_decision'), ci('_source'), ci('screening_tier'), ci('signal_count')

# 条件格式
green = wb.add_format({'bg_color': '#E2EFDA'})
red = wb.add_format({'bg_color': '#FCE4EC'})
blue = wb.add_format({'bg_color': '#DDEBF7'})
gray = wb.add_format({'bg_color': '#F2F2F2'})
orange = wb.add_format({'bg_color': '#F8CBAD'})
yellow = wb.add_format({'bg_color': '#FFE699'})
purple = wb.add_format({'bg_color': '#E4DFEC'})

ws.conditional_format(rng(fd), {'type': 'cell', 'criteria': '==', 'value': '"valid"', 'format': green})
ws.conditional_format(rng(fd), {'type': 'cell', 'criteria': '==', 'value': '"invalid"', 'format': red})
ws.conditional_format(rng(src), {'type': 'cell', 'criteria': '==', 'value': '"queue"', 'format': blue})
ws.conditional_format(rng(src), {'type': 'cell', 'criteria': '==', 'value': '"baseline"', 'format': gray})
ws.conditional_format(rng(tier), {'type': 'cell', 'criteria': '==', 'value': '"HIGH"', 'format': orange})
ws.conditional_format(rng(tier), {'type': 'cell', 'criteria': '==', 'value': '"MEDIUM"', 'format': yellow})
ws.conditional_format(rng(tier), {'type': 'cell', 'criteria': '==', 'value': '"VERIFY"', 'format': purple})
ws.conditional_format(rng(tier), {'type': 'cell', 'criteria': '==', 'value': '"NORMAL"', 'format': gray})
ws.conditional_format(rng(sig), {'type': 'cell', 'criteria': '==', 'value': '"2"', 'format': orange})
ws.conditional_format(rng(sig), {'type': 'cell', 'criteria': '==', 'value': '"1"', 'format': yellow})
ws.conditional_format(rng(sig), {'type': 'cell', 'criteria': '==', 'value': '"0"', 'format': gray})

# 冻结 + 筛选 + 列宽
ws.freeze_panes(1, 0)
ws.autofilter(0, 0, len(df), len(df.columns) - 1)
widths = {0: 10, 1: 14, 2: 12, 3: 14, 4: 12, 5: 22}
for c, w in widths.items():
    ws.set_column(c, c, w)
ws.set_column(6, len(df.columns) - 1, 10)

wb.close()
print(f'Saved: {OUT} | {os.path.getsize(OUT)/1024/1024:.1f} MB')
