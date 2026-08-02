# -*- coding: utf-8 -*-
"""D087 阶段 3｜最终数据集生成（论文提交包版）

判定逻辑（不依赖任何旧文件）：
  - 队列行（592）：用 analysis/复核明细.csv 的 决策 列（保留→valid / 剔除→invalid）
  - 非队列行（1,567）：NORMAL 直接 valid；VETO（跳题违规 40）直接 invalid
输出：data/final_all.csv（2,159 × 全列，final_decision + _source）

用法（在包内执行，路径相对本包）：python 脚本/02_build_final.py
"""

import sys
import io
from pathlib import Path

import pandas as pd

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "data"
QUEUE = BASE / "analysis" / "复核明细.csv"

flags = pd.read_csv(OUT / "signals.csv", dtype=str, keep_default_na=False)
queue = pd.read_csv(QUEUE, dtype=str, keep_default_na=False)
print(f"signals: {len(flags)} | queue: {len(queue)}")

q_map = queue[["ID", "决策"]].drop_duplicates("ID")
q_map = q_map.rename(columns={"ID": "row_id", "决策": "final_decision"})
q_map["final_decision"] = q_map["final_decision"].map({"保留": "valid", "剔除": "invalid"})
assert q_map["final_decision"].notna().all(), "复核明细存在未映射决策"
flags = flags.merge(q_map, on="row_id", how="left")

queue_ids = set(q_map["row_id"])
flags["_source"] = flags["screening_tier"].map(
    {"HIGH": "queue", "MEDIUM": "queue", "NORMAL": "nonsignal", "VETO": "veto"})
flags.loc[flags["row_id"].isin(queue_ids), "_source"] = "queue"
flags["final_decision"] = flags["final_decision"].fillna(
    flags["screening_tier"].map({"VETO": "invalid", "NORMAL": "valid"}))

vc = flags["final_decision"].value_counts()
valid = int(vc.get("valid", 0))
invalid = int(vc.get("invalid", 0))
total = len(flags)
print(f"valid: {valid} ({valid / total * 100:.2f}%) | invalid: {invalid} ({invalid / total * 100:.2f}%)")

assert valid == 1751 and invalid == 408, f"数字不一致: {valid}/{invalid}"
assert flags["final_decision"].notna().all(), "存在未判定行"

# 列重排：标记列前置
first_cols = ["row_id", "final_decision", "_source", "screening_tier", "signal_count",
              "trigger_reason", "veto_any", "CI", "flag_dur_low", "flag_dur_high",
              "flag_md", "flag_long", "flag_dkna", "DUR", "MD_d2", "LS_run", "DKNA_count"]
rest = [c for c in flags.columns if c not in first_cols]
flags = flags[first_cols + rest]

flags.to_csv(OUT / "final_all.csv", index=False, encoding="utf-8-sig")
print(f"Saved: {OUT / 'final_all.csv'}")
print(flags["_source"].value_counts().to_string())
print(f"✅ {valid} / {invalid} 一致")
