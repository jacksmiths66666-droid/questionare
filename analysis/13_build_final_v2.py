"""
最终数据集生成（v5，2026-08-01）
数据源：flags.csv（04 终版 7-30 18:34）+ review_queue.csv（7-31 23:39 终版）
判定逻辑（不依赖任何旧文件）：
  - 队列行（17,009）：用 queue.decision
  - 非队列行（54,913）：乱码检测（45 veto 长乱码 + 32 短乱码）→ invalid；否则 valid
"""
import pandas as pd, math
import sys, io
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "outputs" / "screening_v3"


def _shannon_entropy(s):
    freq = {}
    for c in s:
        freq[c] = freq.get(c, 0) + 1
    n = len(s)
    return -sum((c / n) * math.log2(c / n) for c in freq.values() if c > 0)


def is_gibberish_text(s):
    """判定单条文本是否为乱码（修正版逻辑，内联）"""
    s = str(s).strip().lower()
    if s in ("", "nan", "-99", "none"):
        return False
    no_spaces = s.replace(" ", "").replace("\r", "").replace("\n", "").replace("\t", "")
    n = len(no_spaces)
    if n < 3:
        return False
    raw_entropy = _shannon_entropy(no_spaces)
    log_n = math.log2(n) if n > 0 else 0
    adj_entropy = raw_entropy / log_n if log_n > 0 else 0
    low_entropy = (adj_entropy < 0.3) and (raw_entropy < 2.0)
    repetitive = len(set(no_spaces.lower())) <= 2 and n >= 15
    sym_count = sum(1 for c in no_spaces if not c.isalnum() and not c.isspace())
    high_symbol = (sym_count / max(n, 1)) > 0.7 and n >= 5
    dig_count = sum(1 for c in no_spaces if c.isdigit())
    high_digit = (dig_count / max(n, 1)) > 0.8 and n >= 5
    has_ufffd = "\ufffd" in no_spaces
    control_ratio = sum(1 for c in no_spaces if ord(c) < 32 and ord(c) not in (9, 10, 13)) / max(n, 1)
    has_surrogate = any(0xD800 <= ord(c) <= 0xDFFF for c in no_spaces)
    return (low_entropy or repetitive or high_symbol or high_digit
            or has_ufffd or (control_ratio > 0.3) or has_surrogate)


flags = pd.read_csv(OUT / "tisp_v3_flags.csv", dtype=str, keep_default_na=False, low_memory=False)
queue = pd.read_csv(OUT / "tisp_v3_review_queue.csv", dtype=str, keep_default_na=False)

print(f"flags: {len(flags)} | queue: {len(queue)}")

q_map = queue[["row_id", "decision"]].drop_duplicates("row_id")
q_map = q_map.rename(columns={"decision": "final_decision"})
flags["row_id"] = flags["row_id"].astype(str)
q_map["row_id"] = q_map["row_id"].astype(str)

queue_ids = set(q_map["row_id"])
flags["_in_queue"] = flags["row_id"].isin(queue_ids)
flags = flags.merge(q_map, on="row_id", how="left", suffixes=("", "_q"))
flags = flags.drop(columns=["final_decision_q"], errors="ignore")

# 非队列行乱码检测
nonq_mask = ~flags["_in_queue"]
gib = pd.Series(False, index=flags.index)
for col in ["BENEFIT_OPEN", "TRUST_OPEN"]:
    gib = gib | flags[col].apply(is_gibberish_text)
flags["_gib"] = gib & nonq_mask

def decide(row):
    if row["_in_queue"]:
        return row["final_decision"]
    if row["_gib"]:
        return "invalid"
    return "valid"

flags["final_decision"] = flags.apply(decide, axis=1)
flags["_source"] = flags["_in_queue"].map({True: "queue", False: "nonsignal"})
flags.loc[nonq_mask & flags["_gib"], "_source"] = "gibberish"

n_gib = gib[nonq_mask].sum()
print(f"非队列乱码: {n_gib} 行 (veto 长乱码 {((gib[nonq_mask]) & (flags.loc[nonq_mask,'veto_any']=='1')).sum()} + 短乱码 {((gib[nonq_mask]) & (flags.loc[nonq_mask,'veto_any']=='0')).sum()})")

# 排序 + 列重排
flags["_sort"] = flags["final_decision"].map({"valid": 0, "invalid": 1})
flags.sort_values(["_sort", "row_id"], inplace=True)
flags.drop(columns=["_sort", "_in_queue", "_gib"], inplace=True)

first_cols = ["row_id", "final_decision", "_source"] + [
    c for c in ["screening_tier", "signal_count", "trigger_reason", "veto_any"] if c in flags.columns
]
rest = [c for c in flags.columns if c not in first_cols]
flags = flags[first_cols + rest]

flags.to_csv(OUT / "tisp_v3_final_all.csv", index=False, encoding="utf-8-sig")
print(f"\nSaved: {OUT / 'tisp_v3_final_all.csv'}")

vc = flags["final_decision"].value_counts()
valid = vc.get("valid", 0)
invalid = vc.get("invalid", 0)
total = len(flags)
print(f"valid: {valid} ({valid/total*100:.2f}%) | invalid: {invalid} ({invalid/total*100:.2f}%) | total: {total}")
print(flags["_source"].value_counts().to_string())

assert valid == 55868 and invalid == 16054, "数字不一致!"
print("✅ 55,868 / 16,054 一致")

pd.DataFrame({
    "final_decision": ["valid", "invalid"],
    "n": [valid, invalid],
    "pct": [round(valid/total*100, 2), round(invalid/total*100, 2)],
}).to_csv(OUT / "tisp_v3_decision_summary.csv", index=False, encoding="utf-8-sig")
print(f"Saved: {OUT / 'tisp_v3_decision_summary.csv'}")
