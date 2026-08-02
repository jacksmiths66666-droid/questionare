import pandas as pd

df = pd.read_csv("tisp_v3_final_all_data.csv", low_memory=False)
inv = df[df.final_decision == "invalid"].copy()

benefit = inv["BENEFIT_OPEN"].fillna("").astype(str)
trust = inv["TRUST_OPEN"].fillna("").astype(str)
benefit_empty = benefit.isin(["", "nan", "-99", "None"])
trust_empty = trust.isin(["", "nan", "-99", "None"])

benefit_len = benefit.str.len()
trust_len = trust.str.len()
benefit_len[benefit_empty] = 0
trust_len[trust_empty] = 0
max_len = pd.concat([benefit_len, trust_len], axis=1).max(axis=1)

# Assign review tier
def assign_tier(row):
    ml = max_len.loc[row.name]
    reason = str(row["trigger_reason"])
    tier = row["screening_tier"]

    if ml > 50:
        return "A"
    elif ml >= 16:
        return "B"
    elif ml >= 6:
        return "C"
    else:
        return "D"

inv["review_tier"] = inv.apply(assign_tier, axis=1)
inv["review_status"] = ""
inv["review_note"] = ""

# Flatten multi-line open-ended for xlsx display
inv["BENEFIT_OPEN"] = inv["BENEFIT_OPEN"].fillna("").astype(str).str.replace("\n", " ").str.replace("\r", " ")
inv["TRUST_OPEN"] = inv["TRUST_OPEN"].fillna("").astype(str).str.replace("\n", " ").str.replace("\r", " ")

# Build xlsx output columns
out_cols = [
    "review_tier", "row_id", "COUNTRY_CODE", "COUNTRY_NAME",
    "screening_tier", "trigger_reason",
    "BENEFIT_OPEN", "TRUST_OPEN", "BENEFIT_OPEN_ZH", "TRUST_OPEN_ZH",
    "signal_count", "ls_max_run", "md_score", "oe_r",
    "veto_any", "veto_all_missing", "veto_gibberish",
    "review_status", "review_note"
]

# Only include columns that exist
out_cols = [c for c in out_cols if c in inv.columns]
out = inv[out_cols].copy()
out.sort_values(["review_tier", "COUNTRY_CODE", "row_id"], inplace=True)

# Write xlsx with tier-colored sections
from openpyxl import Workbook
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
from openpyxl.utils import get_column_letter

wb = Workbook()
ws = wb.active
ws.title = "无效数据第三轮审查"

# Header style
header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
header_font = Font(color="FFFFFF", bold=True, size=11)
header_align = Alignment(horizontal="center", vertical="center", wrap_text=True)

tier_fills = {
    "A": PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid"),
    "B": PatternFill(start_color="FFEB9C", end_color="FFEB9C", fill_type="solid"),
    "C": PatternFill(start_color="FDE9D9", end_color="FDE9D9", fill_type="solid"),
    "D": PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid"),
}

# Write header
for c_idx, col_name in enumerate(out_cols, 1):
    cell = ws.cell(row=1, column=c_idx, value=col_name)
    cell.fill = header_fill
    cell.font = header_font
    cell.alignment = header_align

# Write data
for r_idx, (_, row) in enumerate(out.iterrows(), 2):
    tier = row["review_tier"]
    for c_idx, col_name in enumerate(out_cols, 1):
        val = row[col_name]
        if pd.isna(val):
            val = ""
        cell = ws.cell(row=r_idx, column=c_idx, value=val)
        cell.fill = tier_fills.get(tier, PatternFill())
        if col_name in ("BENEFIT_OPEN", "TRUST_OPEN", "BENEFIT_OPEN_ZH", "TRUST_OPEN_ZH"):
            cell.alignment = Alignment(wrap_text=True)

# Column widths
col_widths = {
    "review_tier": 8, "row_id": 10, "COUNTRY_CODE": 10, "COUNTRY_NAME": 16,
    "screening_tier": 10, "trigger_reason": 28,
    "BENEFIT_OPEN": 40, "TRUST_OPEN": 40, "BENEFIT_OPEN_ZH": 30, "TRUST_OPEN_ZH": 30,
    "signal_count": 8, "ls_max_run": 8, "md_score": 10, "oe_r": 10,
    "veto_any": 8, "veto_all_missing": 8, "veto_gibberish": 8,
    "review_status": 10, "review_note": 20,
}
for c_idx, col_name in enumerate(out_cols, 1):
    ws.column_dimensions[get_column_letter(c_idx)].width = col_widths.get(col_name, 12)

# Add tier summary sheet
ws2 = wb.create_sheet("审查说明")
ws2["A1"] = "无效数据第三轮审查方案"
ws2["A1"].font = Font(bold=True, size=14)
ws2["A3"] = "层级"
ws2["B3"] = "标准"
ws2["C3"] = "数量"
ws2["D3"] = "审查策略"
for c in ["A","B","C","D"]:
    ws2[f"{c}3"].font = Font(bold=True)
    ws2[f"{c}3"].fill = header_fill
    ws2[f"{c}3"].font = header_font

tier_info = [
    ("A", "开放题 >50 字且有实质内容", (out["review_tier"]=="A").sum(), "逐条精读，最有希望改判为 valid1"),
    ("B", "16-50 字且内容貌似切题", (out["review_tier"]=="B").sum(), "快速筛查，明显假阳性改判"),
    ("C", "6-15 字表达真实观点而非敷衍", (out["review_tier"]=="C").sum(), "区分'我不知道'类敷衍 vs 简短但切题"),
    ("D", "5 字以下或为空", (out["review_tier"]=="D").sum(), "维持无效，抽查确认无遗漏"),
]
for i, (tier, std, n, strategy) in enumerate(tier_info, 4):
    ws2[f"A{i}"] = tier
    ws2[f"B{i}"] = std
    ws2[f"C{i}"] = n
    ws2[f"D{i}"] = strategy
    for c in ["A","B","C","D"]:
        ws2[f"{c}{i}"].fill = tier_fills.get(tier, PatternFill())

# Freeze panes
ws.freeze_panes = "A2"
ws.auto_filter.ref = ws.dimensions

output_path = "tisp_v3_invalid_review_3rd.xlsx"
wb.save(output_path)
print(f"Saved: {output_path}")
print()
print(f"Tier breakdown:")
print(out["review_tier"].value_counts().sort_index().to_string())
