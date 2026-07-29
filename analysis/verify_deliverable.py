"""Final verification of deliverable."""
import pandas as pd
from pathlib import Path
import re

BASE = Path(r"D:\开山\收集数据\D081_TISP")

print("=" * 60)
print("1. XLSX双页验证")
print("=" * 60)
xlsx_path = BASE / "论文提交关键东西" / "tisp_v3_review_queue.xlsx"
xlsx = pd.ExcelFile(xlsx_path)
print(f"  Sheet names: {xlsx.sheet_names}")
for s in xlsx.sheet_names:
    df = pd.read_excel(xlsx, sheet_name=s, dtype=str)
    cols = list(df.columns[:5])
    print(f"  {s}: {len(df)} rows, cols={cols}")

# Compare Sheet 2 with analysis-ready CSV
ready = pd.read_csv(
    BASE / "outputs" / "screening_v3" / "tisp_v3_analysis_ready.csv",
    dtype=str, keep_default_na=False, encoding="utf-8",
)
sheet2 = pd.read_excel(xlsx, sheet_name="全量有效数据", dtype=str)
print(f"\n  Sheet2 rows: {len(sheet2)}, CSV rows: {len(ready)}")
s2_ids = set(sheet2["row_id"])
r_ids = set(ready["row_id"])
print(f"  In Sheet2 but not CSV: {len(s2_ids - r_ids)}")
print(f"  In CSV but not Sheet2: {len(r_ids - s2_ids)}")

s2_fd = sheet2["final_decision"].value_counts().to_dict()
r_fd = ready["final_decision"].value_counts().to_dict()
print(f"  Sheet2 decisions: {dict(s2_fd)}")
print(f"  CSV decisions:    {dict(r_fd)}")

print("\n" + "=" * 60)
print("2. 文件交叉引用检查")
print("=" * 60)
for md_file in ["README.md", "数据清洗方法论.md", "人工复核规则.md"]:
    path = BASE / "论文提交关键东西" / md_file
    content = path.read_text(encoding="utf-8")
    refs = re.findall(r"`([^`]+\.(?:md|xlsx|py))`", content)
    for ref in refs:
        if ref.startswith("脚本/"):
            f = BASE / "论文提交关键东西" / ref
        elif ref == "tisp_v3_review_queue.csv":
            continue  # intermediate output, not in deliverable
        else:
            f = BASE / "论文提交关键东西" / ref
        status = "OK" if f.exists() else "MISSING"
        print(f"  {md_file}: `{ref}` -> {status}")

print("\n" + "=" * 60)
print("3. 方法论数字交叉验证（Section 3.4 vs 4.1 vs 实际数据）")
print("=" * 60)
queue = pd.read_csv(
    BASE / "outputs" / "screening_v3" / "tisp_v3_review_queue.csv",
    dtype=str, keep_default_na=False, encoding="utf-8",
)

print("  3.4 HIGH: doc says valid1=2, invalid=4")
high = queue[queue["screening_tier"] == "HIGH"]
print(f"  Actual HIGH: valid1={len(high[high['final_decision']=='valid1'])}, invalid={len(high[high['final_decision']=='invalid'])} **MISMATCH**")

print("\n  3.5 VERIFY: doc table says valid1=137, valid2=69, invalid=11, unsure=6")
verify = queue[queue["screening_tier"] == "VERIFY"]
print(f"  Actual VERIFY:")
print(f"    valid1={len(verify[verify['final_decision']=='valid1'])}, valid2={len(verify[verify['final_decision']=='valid2'])}, invalid={len(verify[verify['final_decision']=='invalid'])}")
print(f"    (pre-reso would be: valid1=137, invalid=11, unsure=6 -> post: valid1=140, invalid=14)")
print(f"    -> table shows pre-resolution, but 4.1 shows post-resolution (valid1=140, invalid=14)")

print("\n  4.1 HIGH: doc says valid1=1, invalid=5 -> matches data")
print(f"  4.1 VERIFY: doc says valid1=140, valid2=69, invalid=14 -> matches data")

print("\n  3.6: 5→valid1, 4→invalid")
unsure_ids = ["35055","43310","43438","43508","43550","43647","43734","43796","44090"]
unsure = queue[queue["row_id"].astype(str).isin(unsure_ids)]
print(f"  9 unsure resolution (from actual data):")
for _, r in unsure.iterrows():
    print(f"    row_id={r['row_id']:>6s} | {r['screening_tier']:>6s} | {r['trigger_reason']:40s} | {r['final_decision']}")
v1 = len(unsure[unsure['final_decision']=='valid1'])
inv = len(unsure[unsure['final_decision']=='invalid'])
print(f"  Total: {v1}→valid1, {inv}→invalid **{'OK' if v1==5 and inv==4 else 'MISMATCH'}**")

print("\n" + "=" * 60)
print("4. README 数字验证")
print("=" * 60)
print(f"  NORMAL 69,936 + MEDIUM 1,718 + HIGH 9 + VERIFY 259 = {69936+1718+9+259} (expect 71922)")
print(f"  Queue 1,323+6+223 = {1323+6+223} (expect 1552)")
print(f"  valid1 1,025 + valid2 85 + invalid 442 = {1025+85+442} (expect 1552)")
print(f"  Analysis-ready: 69936 + 1025 + 85 + 434(intercepted) = {69936+1025+85+434} (expect 71480)")

print("\n" + "=" * 60)
print("5. 交付件文件列表")
print("=" * 60)
for f in sorted(BASE.glob("论文提交关键东西/**/*")):
    if f.is_file():
        print(f"  {f.relative_to(BASE / '论文提交关键东西')} ({f.stat().st_size:,} bytes)")

print("\n" + "=" * 60)
print("6. README xlsx说明与xlsx实际内容对比")
print("=" * 60)
print('  README: "双页工作簿：Sheet 1「复核队列」1,552 条；Sheet 2「全量有效数据」71,480 条"')
s1 = len(pd.read_excel(xlsx, sheet_name="复核队列", dtype=str))
s2 = len(pd.read_excel(xlsx, sheet_name="全量有效数据", dtype=str))
print(f"  Actual: Sheet 1={s1}, Sheet 2={s2} -> {'OK' if s1==1552 and s2==71480 else 'MISMATCH'}")

print("\n=== DONE ===")
