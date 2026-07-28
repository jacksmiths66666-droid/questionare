"""重排复核 Excel：HIGH → VERIFY → MEDIUM（按触发原因分组，longstring + mahalanobis 再分子类）"""
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
    "screening_tier", "row_id", "COUNTRY_CODE", "trigger_reason",
    "ls_max_run", "md_score", "oe_r",
    "BENEFIT_OPEN", "BENEFIT_OPEN_ZH",
    "TRUST_OPEN", "TRUST_OPEN_ZH",
    "final_decision",
]
df = q[cols].copy()

# ── longstring 分类逻辑 ──
def classify_ls(r):
    ls = r["ls_max_run"] if pd.notna(r["ls_max_run"]) else 0
    b = str(r["BENEFIT_OPEN_ZH"]) if pd.notna(r["BENEFIT_OPEN_ZH"]) else ""
    t = str(r["TRUST_OPEN_ZH"]) if pd.notna(r["TRUST_OPEN_ZH"]) else ""
    has_content = len(b.strip()) >= 6 or len(t.strip()) >= 6
    both_empty = not has_content and (
        (pd.isna(r["BENEFIT_OPEN_ZH"]) or len(b.strip()) == 0)
        and (pd.isna(r["TRUST_OPEN_ZH"]) or len(t.strip()) == 0)
    )
    if both_empty: return "D-无效倾向"
    if ls <= 34 and has_content: return "A-有效倾向"
    if ls >= 60 and not has_content: return "D-无效倾向"
    if ls >= 60 and has_content: return "C-需判断(极端)"
    return "B-需判断(中等)"

# ── mahalanobis 分类逻辑 ──
def classify_md(r):
    def olen(x):
        if pd.isna(x): return 0
        return len(str(x).strip())
    def gib_code(x):
        if pd.isna(x): return False
        x = str(x).strip()
        if x in ('-99','-99.','99','.','..','...','/'): return True
        if len(x) <= 2 and not any(c.isalpha() for c in x): return True
        return False
    b_gib = gib_code(r["BENEFIT_OPEN"])
    t_gib = gib_code(r["TRUST_OPEN"])
    if b_gib or t_gib:
        return "D-无效倾向"
    ml = max(olen(r["BENEFIT_OPEN"]), olen(r["TRUST_OPEN"]))
    if ml >= 50:
        return "A-有效倾向"
    elif ml >= 20:
        return "B-需判断(中长)"
    else:
        return "C-需判断(短回答)"

# ── 插入分类列 ──
df["分类"] = ""
ls_mask = (df["screening_tier"] == "MEDIUM") & (df["trigger_reason"] == "longstring_exceed")
df.loc[ls_mask, "分类"] = df[ls_mask].apply(classify_ls, axis=1)
md_mask = (df["screening_tier"] == "MEDIUM") & (df["trigger_reason"] == "mahalanobis_outlier")
df.loc[md_mask, "分类"] = df[md_mask].apply(classify_md, axis=1)

# ── 排序 ──
TIER_ORDER = {"HIGH": 0, "VERIFY": 1, "MEDIUM": 2}
TR_REASON_ORDER = {"longstring_exceed": 0, "mahalanobis_outlier": 1, "odd_even_low": 2, "attention_fail": 3}
LS_CAT_ORDER = {"A-有效倾向": 0, "B-需判断(中等)": 1, "C-需判断(极端)": 2, "D-无效倾向": 3}
MD_CAT_ORDER = {"A-有效倾向": 0, "B-需判断(中长)": 1, "C-需判断(短回答)": 2, "D-无效倾向": 3}

def sort_key(row):
    t = TIER_ORDER.get(str(row["screening_tier"]), 99)
    tr = str(row["trigger_reason"]) if pd.notna(row["trigger_reason"]) else ""
    cat = str(row["分类"])
    if t == 2 and tr == "longstring_exceed":
        return (2, 0, LS_CAT_ORDER.get(cat, 99), row["row_id"])
    if t == 2 and tr == "mahalanobis_outlier":
        return (2, 1, MD_CAT_ORDER.get(cat, 99), row["row_id"])
    if t == 2:
        return (2, TR_REASON_ORDER.get(tr, 99), 99, row["row_id"])
    return (t, 0, 0, row["row_id"])

df["_sort"] = df.apply(sort_key, axis=1)
df = df.sort_values("_sort").drop(columns="_sort").reset_index(drop=True)

# ── 分组标记 ──
groups = []
prev = None
for i, row in df.iterrows():
    tier = str(row["screening_tier"])
    tr = str(row["trigger_reason"]) if pd.notna(row["trigger_reason"]) else ""
    cat = str(row["分类"])
    if tier == "MEDIUM" and tr == "longstring_exceed" and cat:
        key = ("MEDIUM", tr, cat)
    elif tier == "MEDIUM" and tr == "mahalanobis_outlier" and cat:
        key = ("MEDIUM", tr, cat)
    elif tier == "MEDIUM":
        key = ("MEDIUM", tr, "")
    else:
        key = (tier, "", "")
    if key != prev:
        groups.append((i, tier, tr, cat))
        prev = key

# ── 颜色 ──
TIER_COLORS = {
    "HIGH":   PatternFill(start_color="FFE0E0", end_color="FFE0E0", fill_type="solid"),
    "VERIFY": PatternFill(start_color="FFE8CC", end_color="FFE8CC", fill_type="solid"),
    "MEDIUM": PatternFill(start_color="FFFDE0", end_color="FFFDE0", fill_type="solid"),
}
TIER_FONTS = {
    "HIGH":   Font(bold=True, color="CC0000"),
    "VERIFY": Font(bold=True, color="CC6600"),
    "MEDIUM": Font(bold=True, color="999900"),
}
SECTION_FILL = PatternFill(start_color="E0E0E0", end_color="E0E0E0", fill_type="solid")
SECTION_FONT = Font(bold=True, size=11, color="333333")
LABEL_FILLS = {
    "longstring_exceed":   PatternFill(start_color="E8F0FE", end_color="E8F0FE", fill_type="solid"),
    "mahalanobis_outlier": PatternFill(start_color="E8F8E8", end_color="E8F8E8", fill_type="solid"),
    "odd_even_low":        PatternFill(start_color="FEE8F0", end_color="FEE8F0", fill_type="solid"),
    "attention_fail":      PatternFill(start_color="F0F0FF", end_color="F0F0FF", fill_type="solid"),
}
REASON_LABELS = {
    "longstring_exceed":   "连续同选 ≥32",
    "mahalanobis_outlier": "马氏距离离群",
    "odd_even_low":        "奇偶一致性低",
    "attention_fail":      "注意力题答错",
}
# longstring 子类
LS_CAT_FILLS = {
    "A-有效倾向":   PatternFill(start_color="D0F0D0", end_color="D0F0D0", fill_type="solid"),
    "B-需判断(中等)": PatternFill(start_color="FFF0D0", end_color="FFF0D0", fill_type="solid"),
    "C-需判断(极端)": PatternFill(start_color="FFD8D0", end_color="FFD8D0", fill_type="solid"),
    "D-无效倾向":   PatternFill(start_color="FFB0B0", end_color="FFB0B0", fill_type="solid"),
}
LS_CAT_LABELS = {
    "A-有效倾向":   "有效倾向 — 仅刚过阈值且写有开放题，标 valid1",
    "B-需判断(中等)": "需判断(中等) — 开放题内容与连续同选值均适中，需看开放题质量",
    "C-需判断(极端)": "需判断(极端) — 几乎全选同一选项但有开放题，需看是否救得回来",
    "D-无效倾向":   "无效倾向 — 开放题空白或极短且连续同选严重，标 invalid",
}
# mahalanobis 子类
MD_CAT_FILLS = {
    "A-有效倾向":    PatternFill(start_color="D0F0D0", end_color="D0F0D0", fill_type="solid"),
    "B-需判断(中长)":  PatternFill(start_color="FFF0D0", end_color="FFF0D0", fill_type="solid"),
    "C-需判断(短回答)": PatternFill(start_color="FFD8D0", end_color="FFD8D0", fill_type="solid"),
    "D-无效倾向":    PatternFill(start_color="FFB0B0", end_color="FFB0B0", fill_type="solid"),
}
MD_CAT_LABELS = {
    "A-有效倾向":    "有效倾向 — 开放题 >50字，内容明确切题，标 valid1",
    "B-需判断(中长)":  "需判断(中长) — 开放题 20-50字，需看内容是否切题",
    "C-需判断(短回答)": "需判断(短回答) — 开放题 <20字，需判断是否敷衍",
    "D-无效倾向":    "无效倾向 — 含-99/乱码/符号，标 invalid",
}

# ── 全列列表（含分类列） ──
all_cols = cols[:4] + ["分类"] + cols[4:]

HEADER = [
    "等级", "编号", "国家", "触发原因", "分类",
    "连续同选", "马氏距离", "奇偶r",
    "开放题原文(BENEFIT)", "开放题翻译(BENEFIT)",
    "开放题原文(TRUST)", "开放题翻译(TRUST)",
    "复核结果",
]

HEADER_FILL = PatternFill(start_color="D0D0D0", end_color="D0D0D0", fill_type="solid")
HEADER_FONT = Font(bold=True, size=11)
WRAP = Alignment(wrap_text=True, vertical="top")

COL_WIDTHS = {1: 12, 2: 8, 3: 10, 4: 30, 5: 18, 6: 10, 7: 10, 8: 8, 9: 45, 10: 45, 11: 45, 12: 45, 13: 12}

wb = Workbook()
ws = wb.active
ws.title = "复核队列"

# ── 表头 ──
for c, h in enumerate(HEADER, 1):
    cell = ws.cell(row=1, column=c, value=h)
    cell.font = HEADER_FONT
    cell.fill = HEADER_FILL
    cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    cell.border = Border(bottom=Side(style="thin"), right=Side(style="thin"))
    ws.column_dimensions[get_column_letter(c)].width = COL_WIDTHS[c]

ws.row_dimensions[1].height = 30

# ── 写入数据 + 分隔行 ──
excel_row = 2
group_idx = 0
for i, row in df.iterrows():
    tier = str(row["screening_tier"])
    tr = str(row["trigger_reason"]) if pd.notna(row["trigger_reason"]) else ""
    cat = str(row["分类"])

    # 分隔行
    if group_idx < len(groups) and groups[group_idx][0] == i:
        _, g_tier, g_tr, g_cat = groups[group_idx]

        if g_tier == "MEDIUM" and g_tr == "longstring_exceed" and g_cat:
            label = f"▸ {LS_CAT_LABELS.get(g_cat, g_cat)}"
            section_fill = LS_CAT_FILLS.get(g_cat, SECTION_FILL)
        elif g_tier == "MEDIUM" and g_tr == "mahalanobis_outlier" and g_cat:
            label = f"▸ {MD_CAT_LABELS.get(g_cat, g_cat)}"
            section_fill = MD_CAT_FILLS.get(g_cat, SECTION_FILL)
        elif g_tier == "MEDIUM":
            label = f"▸ MEDIUM — {REASON_LABELS.get(g_tr, g_tr)}"
            section_fill = LABEL_FILLS.get(g_tr, SECTION_FILL)
        else:
            label = f"▸ {g_tier}"
            section_fill = SECTION_FILL

        ncols = len(HEADER)
        ws.merge_cells(start_row=excel_row, start_column=1, end_row=excel_row, end_column=ncols)
        cell = ws.cell(row=excel_row, column=1, value=label)
        cell.font = SECTION_FONT
        cell.fill = section_fill
        cell.alignment = Alignment(vertical="center")
        for cc in range(1, ncols + 1):
            ws.cell(row=excel_row, column=cc).fill = section_fill
            ws.cell(row=excel_row, column=cc).border = Border(bottom=Side(style="thin"))
        ws.row_dimensions[excel_row].height = 24
        excel_row += 1
        group_idx += 1

    # 数据行
    fill = TIER_COLORS.get(tier, PatternFill())
    for ci, col in enumerate(all_cols, 1):
        val = row[col]
        if pd.isna(val):
            val = ""
        elif col in ("ls_max_run", "oe_r"):
            val = round(float(val), 3)
        elif col == "md_score":
            val = round(float(val), 2)
        elif col == "row_id":
            val = int(val)
        elif col == "分类":
            if tr == "mahalanobis_outlier":
                val = MD_CAT_LABELS.get(str(val), val) if val else ""
            else:
                val = LS_CAT_LABELS.get(str(val), val) if val else ""
        cell = ws.cell(row=excel_row, column=ci, value=val)

        wrap_cols = {"分类", "trigger_reason", "BENEFIT_OPEN", "BENEFIT_OPEN_ZH", "TRUST_OPEN", "TRUST_OPEN_ZH"}
        if col in wrap_cols:
            cell.alignment = WRAP
        else:
            cell.alignment = Alignment(vertical="top")

        if ci == 1:
            cell.fill = fill
            cell.font = TIER_FONTS.get(tier, Font())
        elif col == "分类" and val:
            if tr == "mahalanobis_outlier":
                sc = MD_CAT_FILLS.get(str(row["分类"]))
            else:
                sc = LS_CAT_FILLS.get(str(row["分类"]))
            if sc:
                cell.fill = sc
        elif col == "trigger_reason":
            cell.fill = fill

        cell.border = Border(bottom=Side(style="hair"), right=Side(style="hair"))

    excel_row += 1

ws.freeze_panes = "E2"
ws.auto_filter.ref = f"A1:{get_column_letter(len(HEADER))}{excel_row-1}"

# ── 复核指引 sheet ──
ws2 = wb.create_sheet("复核指引")
GUIDE = [
    ("列", "说明"),
    ("等级", "HIGH=≥2信号(红) / VERIFY=IDN/PRT注意力异常(橙) / MEDIUM=1信号(黄)"),
    ("编号", "原始数据行号，用于追溯"),
    ("国家", "ISO 国家代码"),
    ("触发原因", "触发了哪些信号"),
    ("分类", "子分类（longstring 4档 / mahalanobis 4档）"),
    ("连续同选", "最长连续同选题数，≥32触发"),
    ("马氏距离", "多变量异常值指标，越大越异常"),
    ("奇偶r", "反向题配对相关系数，<-0.88触发"),
    ("开放题原文", "受访者原始回答"),
    ("开放题翻译", "中文翻译，对照阅读"),
    ("复核结果", "valid1=基础有效 / valid2=严格有效 / invalid=无效 / unsure=不确定"),
    ("", ""),
    ("longstring 4类", ""),
    ("有效倾向", "连续同选32-34且开放题有内容 → 标 valid1"),
    ("需判断(中等)", "35-59+有开放题 → 看内容"),
    ("需判断(极端)", "60-71+有开放题 → 严格判定"),
    ("无效倾向", "开放题空/极短/极端同选 → 标 invalid"),
    ("", ""),
    ("mahalanobis 4类", ""),
    ("有效倾向", ">50字开放题，内容明确切题 → 标 valid1"),
    ("需判断(中长)", "20-50字开放题 → 看内容是否切题"),
    ("需判断(短回答)", "<20字开放题 → 判断是否敷衍"),
    ("无效倾向", "含-99/乱码 → 标 invalid"),
    ("", ""),
    ("操作建议", ""),
    ("1", "从分隔行开始，按子类顺序过"),
    ("2", "每处理完一个子类 Ctrl+S 保存"),
    ("3", "复核结果列：valid1=基础有效, valid2=严格有效, invalid=无效, unsure=不确定"),
]
for r, (a, b) in enumerate(GUIDE, 1):
    ws2.cell(row=r, column=1, value=a).font = Font(bold=True)
    ws2.cell(row=r, column=2, value=b)
ws2.column_dimensions["A"].width = 20
ws2.column_dimensions["B"].width = 75

wb.save(OUT)
print(f"已生成: {OUT}")
print()

# 统计
for t in ["HIGH", "VERIFY", "MEDIUM"]:
    sub = df[df["screening_tier"] == t]
    print(f"{t}: {len(sub)} 行")
    if t == "MEDIUM":
        for tr, cnt in sub["trigger_reason"].value_counts().items():
            print(f"  └ {tr}: {cnt}")
            if tr in ("longstring_exceed", "mahalanobis_outlier"):
                cat_labels = LS_CAT_LABELS if tr == "longstring_exceed" else MD_CAT_LABELS
                for cat, ccnt in sub[sub["trigger_reason"] == tr]["分类"].value_counts().items():
                    print(f"      └ {cat_labels.get(cat, cat)}: {ccnt}")
