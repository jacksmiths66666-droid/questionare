# -*- coding: utf-8 -*-
"""D087 阶段 4｜彩色核查版（论文提交包版）

输入：data/final_all.csv → 输出：data/final_all.xlsx
条件着色：final_decision 绿/红、_source 蓝/灰/黄、screening_tier 橙/黄/紫/灰、signal_count
用法（在包内执行）：python 脚本/03_build_xlsx.py
"""

import sys
import io
import os
from pathlib import Path

import pandas as pd

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BASE = Path(__file__).resolve().parent.parent
SRC = BASE / "data" / "final_all.csv"
OUT = BASE / "data" / "final_all.xlsx"

df = pd.read_csv(SRC, dtype=str, keep_default_na=False)
print(f"载入 {len(df)} 行 × {len(df.columns)} 列")

import xlsxwriter
wb = xlsxwriter.Workbook(OUT, {"constant_memory": True, "strings_to_numbers": False})
ws = wb.add_worksheet("final_all")

hdr = wb.add_format({"bold": True, "font_color": "white", "bg_color": "#1F4E79",
                     "border": 1, "align": "center", "valign": "vcenter"})
for c, col in enumerate(df.columns):
    ws.write(0, c, col, hdr)

rows = df.values.tolist()
for r, row in enumerate(rows, 1):
    ws.write_row(r, 0, row)
print("数据写入完成")

def ci(name):
    return df.columns.get_loc(name)

rng = lambda c: f"{xlsxwriter.utility.xl_col_to_name(c)}2:{xlsxwriter.utility.xl_col_to_name(c)}{len(df) + 1}"

fd, src, tier, sig = ci("final_decision"), ci("_source"), ci("screening_tier"), ci("signal_count")

green = wb.add_format({"bg_color": "#E2EFDA"})
red = wb.add_format({"bg_color": "#FCE4EC"})
blue = wb.add_format({"bg_color": "#DDEBF7"})
gray = wb.add_format({"bg_color": "#F2F2F2"})
orange = wb.add_format({"bg_color": "#F8CBAD"})
yellow = wb.add_format({"bg_color": "#FFE699"})
purple = wb.add_format({"bg_color": "#E4DFEC"})

ws.conditional_format(rng(fd), {"type": "cell", "criteria": "==", "value": '"valid"', "format": green})
ws.conditional_format(rng(fd), {"type": "cell", "criteria": "==", "value": '"invalid"', "format": red})
ws.conditional_format(rng(src), {"type": "cell", "criteria": "==", "value": '"queue"', "format": blue})
ws.conditional_format(rng(src), {"type": "cell", "criteria": "==", "value": '"nonsignal"', "format": gray})
ws.conditional_format(rng(src), {"type": "cell", "criteria": "==", "value": '"veto"', "format": yellow})
ws.conditional_format(rng(tier), {"type": "cell", "criteria": "==", "value": '"HIGH"', "format": orange})
ws.conditional_format(rng(tier), {"type": "cell", "criteria": "==", "value": '"MEDIUM"', "format": yellow})
ws.conditional_format(rng(tier), {"type": "cell", "criteria": "==", "value": '"NORMAL"', "format": gray})
ws.conditional_format(rng(tier), {"type": "cell", "criteria": "==", "value": '"VETO"', "format": purple})
ws.conditional_format(rng(sig), {"type": "cell", "criteria": "==", "value": '"2"', "format": orange})
ws.conditional_format(rng(sig), {"type": "cell", "criteria": "==", "value": '"1"', "format": yellow})
ws.conditional_format(rng(sig), {"type": "cell", "criteria": "==", "value": '"0"', "format": gray})

ws.freeze_panes(1, 0)
ws.autofilter(0, 0, len(df), len(df.columns) - 1)
widths = {0: 10, 1: 14, 2: 12, 3: 14, 4: 12, 5: 22}
for c, w in widths.items():
    ws.set_column(c, c, w)
ws.set_column(6, len(df.columns) - 1, 10)

wb.close()
print(f"Saved: {OUT} | {os.path.getsize(OUT) / 1024 / 1024:.1f} MB")
