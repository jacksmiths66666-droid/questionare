"""Quick ref check."""
import re, pathlib
BASE = pathlib.Path("D:/开山/收集数据/D081_TISP/论文提交关键东西")
for md in ["README.md", "数据清洗方法论.md", "人工复核规则.md"]:
    txt = (BASE / md).read_text(encoding="utf-8")
    refs = re.findall(r"`([^`]+\.(?:md|xlsx|py))`", txt)
    for r in refs:
        p = BASE / r if not r.startswith("脚本/") else BASE / r
        if r == "tisp_v3_review_queue.csv":
            continue
        ok = "OK" if p.exists() else "MISSING"
        print(f"  {md:15s} -> {r:30s} {ok}")

print("\n--- All check ---")
files_in_dir = sorted([str(f.relative_to(BASE)) for f in BASE.rglob("*") if f.is_file()])
for f in files_in_dir:
    print(f"  deliverable: {f}")
