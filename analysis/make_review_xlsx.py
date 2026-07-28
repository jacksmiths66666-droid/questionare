"""生成人工复核专用 Excel（精简列、换行、颜色分级）"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter

SRC = "outputs/screening_v3/tisp_v3_review_queue.csv"
OUT = "outputs/screening_v3/tisp_v3_review_queue.xlsx"

q = pd.read_csv(SRC)

# ── 精选列 ──
cols = [
    "screening_tier",
    "row_id",
    "COUNTRY_CODE",
    "trigger_reason",
    "ls_max_run",
    "md_score",
    "oe_r",
    "BENEFIT_OPEN",
    "BENEFIT_OPEN_ZH",
    "TRUST_OPEN",
    "TRUST_OPEN_ZH",
    "final_decision",
]
df = q[cols].copy()

# ── 颜色 ──
TIER_COLORS = {
    "HIGH":   PatternFill(start_color="FFE0E0", end_color="FFE0E0", fill_type="solid"),  # 红
    "VERIFY": PatternFill(start_color="FFE8CC", end_color="FFE8CC", fill_type="solid"),  # 橙
    "MEDIUM": PatternFill(start_color="FFFDE0", end_color="FFFDE0", fill_type="solid"),  # 黄
}
TIER_FONTS = {
    "HIGH":   Font(bold=True, color="CC0000"),
    "VERIFY": Font(bold=True, color="CC6600"),
    "MEDIUM": Font(bold=True, color="999900"),
}

wb = Workbook()
ws = wb.active
ws.title = "复核队列"

# ── 列宽 ──
COL_WIDTHS = {
    1: 12,   # screening_tier
    2: 8,    # row_id
    3: 10,   # COUNTRY_CODE
    4: 30,   # trigger_reason
    5: 10,   # ls_max_run
    6: 10,   # md_score
    7: 8,    # oe_r
    8: 45,   # BENEFIT_OPEN
    9: 45,   # BENEFIT_OPEN_ZH
    10: 45,  # TRUST_OPEN
    11: 45,  # TRUST_OPEN_ZH
    12: 12,  # final_decision
}

# ── 表头 ──
HEADER = [
    "等级", "编号", "国家", "触发原因",
    "连续同选", "马氏距离", "奇偶r",
    "开放题原文(BENEFIT)", "开放题翻译(BENEFIT)",
    "开放题原文(TRUST)", "开放题翻译(TRUST)",
    "复核结果",
]
HEADER_FILL = PatternFill(start_color="D0D0D0", end_color="D0D0D0", fill_type="solid")
HEADER_FONT = Font(bold=True, size=11)
WRAP = Alignment(wrap_text=True, vertical="top")

for c, h in enumerate(HEADER, 1):
    cell = ws.cell(row=1, column=c, value=h)
    cell.font = HEADER_FONT
    cell.fill = HEADER_FILL
    cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    cell.border = Border(
        bottom=Side(style="thin"), right=Side(style="thin")
    )
    ws.column_dimensions[get_column_letter(c)].width = COL_WIDTHS[c]

ws.row_dimensions[1].height = 30

# ── 数据行 ──
for r, row in df.iterrows():
    excel_row = r + 2
    tier = str(row["screening_tier"])
    fill = TIER_COLORS.get(tier, PatternFill())

    for c, col in enumerate(cols, 1):
        val = row[col]
        if pd.isna(val):
            val = ""
        elif col in ("ls_max_run", "oe_r"):
            val = round(float(val), 3)
        elif col == "md_score":
            val = round(float(val), 2)
        elif col == "row_id":
            val = int(val)
        cell = ws.cell(row=excel_row, column=c, value=val)

        # 换行 + 顶部对齐
        if col in ("trigger_reason", "BENEFIT_OPEN", "BENEFIT_OPEN_ZH", "TRUST_OPEN", "TRUST_OPEN_ZH"):
            cell.alignment = WRAP
        else:
            cell.alignment = Alignment(vertical="top")

        # 分级颜色
        if c == 1:
            cell.fill = fill
            cell.font = TIER_FONTS.get(tier, Font())
        elif c == 4:  # trigger_reason 也上色
            cell.fill = fill

        cell.border = Border(bottom=Side(style="hair"), right=Side(style="hair"))

# ── 冻结首行 + 前4列 ──
ws.freeze_panes = "E2"

# ── 筛选器 ──
ws.auto_filter.ref = f"A1:L{len(df)+1}"

# ── 复核指引 sheet ──
ws2 = wb.create_sheet("复核指引")
GUIDE = [
    ("列", "说明"),
    ("等级", "HIGH=≥2信号(红) / VERIFY=IDN/PRT注意力异常(橙) / MEDIUM=1信号(黄)"),
    ("编号", "原始数据行号，用于追溯"),
    ("国家", "ISO 国家代码"),
    ("触发原因", "触发了哪些信号，如 mahalanobis_outlier;odd_even_low"),
    ("连续同选", "最长连续同选题数，≥32触发"),
    ("马氏距离", "多变量异常值指标，越大越异常"),
    ("奇偶r", "反向题配对相关系数，<-0.88触发"),
    ("开放题原文", "受访者原始回答"),
    ("开放题翻译", "中文翻译，对照阅读"),
    ("复核结果", "填 valid / invalid / unsure"),
    ("", ""),
    ("判断标准", ""),
    ("valid", "开放题认真回答，信号偶然触发"),
    ("invalid", "开放题乱答/答非所问/明显随意"),
    ("unsure", "拿不准，标记后讨论"),
    ("", ""),
    ("操作建议", ""),
    ("1", "先筛选等级=HIGH，6条优先处理"),
    ("2", "再筛选等级=VERIFY，223条快速过（只看开放题）"),
    ("3", "最后处理MEDIUM，按触发原因分类批量处理"),
    ("4", "每处理完一批 Ctrl+S 保存"),
    ("5", "最终复核结果列填在 M 列(final_decision)"),
]
for r, (a, b) in enumerate(GUIDE, 1):
    ws2.cell(row=r, column=1, value=a).font = Font(bold=True)
    ws2.cell(row=r, column=2, value=b)
ws2.column_dimensions["A"].width = 18
ws2.column_dimensions["B"].width = 70

wb.save(OUT)
print(f"已生成: {OUT}")
print(f"共 {len(df)} 行，12 列 + 复核指引")
