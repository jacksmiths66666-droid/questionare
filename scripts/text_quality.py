# -*- coding: utf-8 -*-
"""
================================================================================
开放式文本回答质量分析模块
================================================================================

【用途】
  对问卷中 4 道开放文本题（Q07C/Q10/Q12B/Q16B）进行低质量回答筛查。

【指标定义】
  - is_code_only:  回答仅由数字和逗号组成（访员只录入编码，受访者无实质回答）
  - is_dkna_only: 回答就是 "88" 或 "99"（明确表示不知道/拒答）
  - is_too_short:  回答长度 <= 3 个字符，过于简短，可能是敷衍或乱敲

【判断逻辑】
  任一指标命中 → 该题作答质量标记为 0（低质量）
  该题作答质量标记为 0 的样本 → 计入每人缺失次数

================================================================================
"""

import pandas as pd
import numpy as np
import re
import os, sys

# ---- 自动定位仓库根目录 ----
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT  = os.path.dirname(SCRIPT_DIR)

# ============================================================================
#  模块 A: Config —— 开放文本题定义
# ============================================================================
class TextConfig:
    """集中管理开放文本题字段名、题目描述和阈值。"""

    # 4 道开放文本题
    # (列名, 题目简短描述)
    TEXT_FIELDS = [
        ("P07Ctx",  "Q07C: 通过哪些媒体获知动员"),
        ("P10tx",   "Q10: 最重要的妇女诉求"),
        ("P12Btx",  "Q12B: 开展了哪些相关活动"),
        ("P16Btx",  "Q16B: 其他示威的主题"),
    ]

    # 阈值
    SHORT_THRESHOLD = 3          # 长度 ≤ 此值 视为过短
    CODE_ONLY_PATTERN = r"^[\d,\s]+$"   # 纯数字+逗号+空格 → 编码
    DKNA_PATTERN = r"^\s*(88|99)\s*$"    # 纯 DK/NA 编码

# ============================================================================
#  模块 B: QualityAnalyzer —— 文本质量分析核心
# ============================================================================
class QualityAnalyzer:
    """对每条开放文本做三项检查：编码、DK/NA、过短。"""

    def __init__(self, cfg: TextConfig = None):
        self.cfg = cfg or TextConfig()
        self.code_re   = re.compile(self.cfg.CODE_ONLY_PATTERN)
        self.dkna_re  = re.compile(self.cfg.DKNA_PATTERN)

    # ------------------------------------------------------------------
    # 单项检查
    # ------------------------------------------------------------------
    def is_code_only(self, text: str) -> bool:
        """文本是否仅由数字和逗号组成（访员只录编码）。"""
        if pd.isna(text) or str(text).strip() == "":
            return False   # 空值不算编码（空=跳题/没被问）
        return bool(self.code_re.match(str(text).strip()))

    def is_dkna_only(self, text: str) -> bool:
        """文本是否就是 '88' 或 '99'（访员标记为不知道/拒答）。"""
        if pd.isna(text) or str(text).strip() == "":
            return False
        return bool(self.dkna_re.match(str(text).strip()))

    def is_too_short(self, text: str) -> bool:
        """文本长度是否 <= SHORT_THRESHOLD（过于敷衍）。"""
        if pd.isna(text) or str(text).strip() == "":
            return False
        return len(str(text).strip()) <= self.cfg.SHORT_THRESHOLD

    # ------------------------------------------------------------------
    # 单字段全量检查
    # ------------------------------------------------------------------
    def check_field(self, series: pd.Series) -> pd.DataFrame:
        """对某一列的每个值执行三项检查，返回三项 bool 的 DataFrame。
        返回列: {col}_code, {col}_dkna, {col}_short
        """
        col_name = series.name
        result = pd.DataFrame(index=series.index)
        result[f"{col_name}_code"]  = series.apply(self.is_code_only)
        result[f"{col_name}_dkna"]  = series.apply(self.is_dkna_only)
        result[f"{col_name}_short"] = series.apply(self.is_too_short)
        return result

    # ------------------------------------------------------------------
    # 全部字段批量检查
    # ------------------------------------------------------------------
    def check_all(self, df: pd.DataFrame) -> pd.DataFrame:
        """对配置中所有 TEXT_FIELDS 执行检查，返回全部标记的 DataFrame。
        同时在 df 上原地添加 per-row 汇总列。
        """
        all_flags = pd.DataFrame(index=df.index)

        for col, desc in self.cfg.TEXT_FIELDS:
            if col not in df.columns:
                print(f"  [警告] 列 {col} 不存在于数据中，跳过")
                continue
            flags = self.check_field(df[col])
            all_flags = pd.concat([all_flags, flags], axis=1)

        # ---- 每人汇总 ----
        # 统计每人有多少道文本题「是编码/是 DK/过短」的总命中次数
        df["text_code_count"] = 0
        df["text_dkna_count"] = 0
        df["text_short_count"] = 0
        df["text_low_quality_count"] = 0  # 该题质量标记为 0 的次数

        for col, desc in self.cfg.TEXT_FIELDS:
            c_col = f"{col}_code"
            d_col = f"{col}_dkna"
            s_col = f"{col}_short"

            if c_col not in all_flags.columns:
                continue

            # 逐个累加
            df["text_code_count"] += all_flags[c_col].astype(int)
            df["text_dkna_count"] += all_flags[d_col].astype(int)
            df["text_short_count"] += all_flags[s_col].astype(int)

            # 该题是否为低质量（任一命中）
            df["text_low_quality_count"] += (
                all_flags[c_col] | all_flags[d_col] | all_flags[s_col]
            ).astype(int)

        return all_flags

# ============================================================================
#  模块 C: Reporter —— 统计输出
# ============================================================================
class TextReporter:
    """输出文本质量分析的统计摘要。"""

    @staticmethod
    def report(df: pd.DataFrame, cfg: TextConfig):
        print("\n" + "=" * 60)
        print("开放文本质量分析报告")
        print("=" * 60)

        n = len(df)

        # ---- 逐题统计 ----
        for col, desc in cfg.TEXT_FIELDS:
            c_col = f"{col}_code"
            d_col = f"{col}_dkna"
            s_col = f"{col}_short"

            if c_col not in df.columns:
                continue

            # 非空回答数
            non_empty = df[col].notna() & (df[col].astype(str).str.strip() != "")
            n_answered = non_empty.sum()

            code = int(df[c_col].sum())
            dkna = int(df[d_col].sum())
            short_ = int(df[s_col].sum())

            # 任一命中 = 该题低质量
            low_quality = (df[c_col] | df[d_col] | df[s_col]).sum()

            print(f"\n  [{col}] {desc}")
            print(f"    非空回答: {n_answered} 人")
            print(f"    ├─ 纯编码(访员录入): {code} ({code/n*100:.1f}%)")
            print(f"    ├─ 纯DK/NA(88/99):  {dkna} ({dkna/n*100:.1f}%)")
            print(f"    ├─ 过短(<=3字符):   {short_} ({short_/n*100:.1f}%)")
            print(f"    └─ 该题标记为低质量: {low_quality} ({low_quality/n*100:.1f}%)")

        # ---- 每人汇总 ----
        lq_total = int(df["text_low_quality_count"].sum())
        print(f"\n  每人低质量命中数分布:")
        for k, v in sorted(df["text_low_quality_count"].value_counts().items()):
            print(f"    命中 {k} 道: {v} 人 ({v/n*100:.1f}%)")

        print(f"\n  合计: {lq_total} 次低质量标记分布在 {len(df)} 人中")
        print("=" * 60)

# ============================================================================
#  模块 D: 独立运行入口（用于单独测试文本分析）
# ============================================================================
def main():
    """单独运行此脚本时，对原始数据执行文本质量分析并打印报告。"""
    csv_path = os.path.join(REPO_ROOT, "data", "raw", "02_PROTEiCA_survey_EN.csv")

    if not os.path.exists(csv_path):
        print(f"[错误] 找不到数据文件: {csv_path}")
        sys.exit(1)

    print(f"读取: {csv_path}")
    df = pd.read_csv(csv_path)
    print(f"原始样本: {len(df)} 人\n")

    cfg = TextConfig()
    analyzer = QualityAnalyzer(cfg)
    _ = analyzer.check_all(df)
    TextReporter.report(df, cfg)

    print("\n提示: 此模块也可作为 library 被主筛查脚本 import 调用。")


if __name__ == "__main__":
    main()