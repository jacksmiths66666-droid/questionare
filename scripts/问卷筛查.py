# -*- coding: utf-8 -*-
"""
================================================================================
PROTEiCA 问卷数据清洗筛查脚本 v2.0（模块化版）
================================================================================

【脚本用途】
  从 2,159 人的问卷数据中筛查"不认真作答"的样本。

【流程概览】
  Step 1: 跳题违规 -> 直接删除（数据逻辑错误，不可修复）
  Step 2: 四个核心指标 -> OR 逻辑（任一命中标记为不认真）
  Step 3: 八个辅助指标 -> 仅供参考（>=3 个命中建议人工复核）

【模块结构】
  config     - 所有可调参数和路径
  encoding   - 文本 -> 数字编码映射
  step1_skip - 跳题违规检查
  step2_dur  - 作答时间检查
  step2_maha - 马氏距离检查
  step2_long - 长串连续作答检查
  step2_dkna - DK/NA 泛滥检查
  step3_aux  - 辅助矛盾指标
  reporter   - 输出文件 + 统计汇总

【怎么改参数？】
  改 config 区的数值即可，不用动业务逻辑。

================================================================================
"""

# ============================================================================
#  模块 0: 导入
# ============================================================================
import pandas as pd
import numpy as np
from scipy.spatial.distance import mahalanobis
from numpy.linalg import inv
from collections import Counter


# ====== 自动定位仓库根目录 ======
import os, sys
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))          # scripts/ 目录
REPO_ROOT = os.path.dirname(SCRIPT_DIR)                          # 仓库根目录



# ============================================================================
#  模块 1: config —— 所有参数与路径
# ============================================================================
class Config:
    """集中管理所有文件路径、阈值和题目组定义。"""

    # ---- 文件路径 ----
    CSV_IN      = os.path.join(REPO_ROOT, "data", "raw", "02_PROTEiCA_survey_EN.csv")
    CSV_CLEAN   = os.path.join(REPO_ROOT, "output", "有效问卷.csv")
    CSV_INVALID = os.path.join(REPO_ROOT, "output", "无效问卷_待复核.csv")
    CSV_DETAIL  = os.path.join(REPO_ROOT, "output", "筛查明细.csv")

    # ---- 原始数据总人数（用于最终统计口径） ----
    N_ORIGINAL = 2159

    # ============================================================
    # 可调阈值区（改这里的数字就能调整严苛程度）
    # ============================================================

    # 作答时间（分钟） P1 / P99
    DUR_MIN  = 5.5
    DUR_MAX  = 34.5

    # 马氏距离 D^2 分界点  P95
    MAHA_TH  = 11.0

    # 长串连续相同答案数  P97
    LONG_TH  = 7

    # 显式 DK/NA 次数  P95
    DKNA_TH  = 5

    # ============================================================
    # 题目分组（供筛查逻辑引用）
    # ============================================================

    # P11A-E：性别平等态度 5 题（用于马氏距离）
    P11_COLS = ["P11A", "P11B", "P11C", "P11D", "P11E"]

    # P02A-E：政治信息获取渠道 5 题（用于辅助指标 5）
    P02_COLS = ["P02A", "P02B", "P02C", "P02D", "P02E"]

    # 55 道核心选择题（用于 DK/NA 统计）
    # 排除：开放文本题、辅助过程字段、纯跳题子题
    CORE_VARS = [
        "P01","P02A","P02B","P02C","P02D","P02E",
        "P03","P04","P05","P06",
        "P07","P07B","P07D1","P07D2","P07D3","P07D4","P07D5","P07D6",
        "P08","P09","P09B","P10B",
        "P11A","P11B","P11C","P11D","P11E",
        "P12","P13","P13B","P13C",
        "P14","P15","P16","P17","P17B","P17C",
        "P18","P19","P19B","P20","P20B",
        "P21A","P21B","P21C","P21D",
        "P22","P23","P24","P25",
        "P27","P27B","P27C","P28","P28B",
    ]

    # 21 道参与 longstring 的选择题定义
    # 每个元组: (列名, 编码字典, 是否反向, 尺度最大值)
    @staticmethod
    def build_longstring_items():
        """返回 21 道用于 longstring 的题目定义。
        注意：此函数放在类方法里是因为用到了 encoding 里定义的字典。
        实际调用时由 encoding 模块组装好后传入，不会在 config 里硬编码。
        """
        return []  # 占位，由 encoding 模块填充

# ============================================================================
#  模块 2: encoding —— 文本映射 & 编码表
# ============================================================================
class Encoding:
    """所有文本标签 -> 数字的映射，以及显式 DK/NA 集合。"""

    # 5 点 Likert（同意度）
    LIKERT = {
        "Strongly disagree":             1,
        "Disagree":                      2,
        "Neither agree nor disagree":    3,
        "Agree":                         4,
        "Strongly agree":                5,
    }

    # 5 点频率（P02A–E：媒体使用频率）
    FREQ_5 = {
        "Never":                             1,
        "Less (almost never)":               2,
        "1 or 2 days/weekends":              3,
        "3 or 4 days (quite a lot)":         4,
        "Everyday or almost everyday (5-7)":  5,
    }

    # 5 点频率（P21A：社媒政治活动频率）
    FREQ_SM = {
        "Never":                        1,
        "Less frequently":              2,
        "1-2 days a week/weekends":     3,
        "3-4 days a week":              4,
        "Every or almost every day":    5,
    }

    # 4 点定序（合并了 P01/P04/P06/P08/P10B/P07B/P07D1–4 的选项）
    # 由于各题选项文本不同但同属 4 级，统一用这一个字典兜底
    ORD4 = {
        # P01 / P04: 政治兴趣 / 政治效能感
        "Not at all": 1, "Hardly": 2, "Quite": 3, "Very": 4,
        # P06: 政治参与能力感
        "Not capable": 1, "Little": 2, "Quite": 3, "Very capable": 4,
        # P08: 三八动员必要性
        "Not at all necessary": 1, "Not very necessary": 2,
        "Quite necessary": 3, "Very necessary": 4,
        # P10B: 捍卫意见能力
        "No capable": 1, "Not very capable": 2,
        "Quite capable": 3, "Very capable": 4,
        # P07B / P07D1–4: 三八动员关注 / 行为频率
        "No interest": 1, "Hardly": 2, "Quite": 3, "A lot": 4,
        "Little": 2, "Very often": 4,
    }

    # 哪些文本算“不知道 / 拒答”
    DKNA_SET = {"DK", "NA", "Can't say", "No memories", "NC"}

    # ---------------------------------------------------------------
    # 21 道选择题定义（用于 longstring）
    # 字段说明:
    #   - name:   列名
    #   - dmap:   编码字典
    #   - reverse:是否反向（True 时 max_val+1 - val）
    #   - max_val:原始最大值（用于归一化）
    # ---------------------------------------------------------------
    @staticmethod
    def longstring_items():
        """构建 21 道用于 longstring 的选择题列表。"""
        L = Encoding.LIKERT
        F = Encoding.FREQ_5
        O = Encoding.ORD4
        S = Encoding.FREQ_SM

        return [
            # ---- 5 点 Likert ----
            ("P11A", L, True,  5),
            ("P11B", L, False, 5),
            ("P11C", L, False, 5),
            ("P11D", L, False, 5),
            ("P11E", L, False, 5),
            # ---- 5 点频率 ----
            ("P02A", F, False, 5),
            ("P02B", F, False, 5),
            ("P02C", F, False, 5),
            ("P02D", F, False, 5),
            ("P02E", F, False, 5),
            ("P21A", S, False, 5),
            # ---- 4 点定序 ----
            ("P01",  O, False, 4),
            ("P04",  O, False, 4),
            ("P06",  O, False, 4),
            ("P08",  O, False, 4),
            ("P10B", O, False, 4),
            # ---- 4 点频率（含跳题） ----
            ("P07B",  O, False, 4),
            ("P07D1", O, False, 4),
            ("P07D2", O, False, 4),
            ("P07D3", O, False, 4),
            ("P07D4", O, False, 4),
        ]

# ============================================================================
#  模块 3: step1_skip —— 跳题违规直接删除
# ============================================================================
class Step1SkipViolation:
    """检查问卷设计中的跳题规则是否被违反。违规样本直接剔除。"""

    @staticmethod
    def run(df: pd.DataFrame) -> pd.DataFrame:
        """在 df 上打 flag_skip 标记并输出统计，随后返回清理后的 DataFrame。

        规则：
        -#2  Q12=No（没参加三八活动），但 Q12B 却有活动记录       -> 违规
        -#6  Q27/=Yes（非同住伴侣），但 Q27C 填了伴侣性别(Man/Woman) -> 违规
        """

        print("\n" + "=" * 40)
        print("STEP 1: 跳题逻辑违规（直接删除）")
        print("=" * 40)

        # 规则 #2
        violated_r2 = (
            (df["P12"] == "No")
            & df["P12Btx"].notna()
            & (df["P12Btx"].astype(str).str.strip() != "")
        )

        # 规则 #6
        violated_r6 = (
            (~df["P27"].isin(["Yes", ""]))
            & df["P27C"].isin(["Man", "Woman"])
        )

        combined = violated_r2 | violated_r6
        df["flag_skip"] = combined.astype(int)

        print(f"  规则#2 (Q12=No但Q12B有记录)     : {violated_r2.sum()} 人")
        print(f"  规则#6 (Q27/=Yes但Q27C填了性别) : {violated_r6.sum()} 人")
        print(f"  >>> 合计剔除: {combined.sum()} 人")

        df_clean = df[~combined].copy().reset_index(drop=True)
        print(f"  >>> 剔除后剩余: {len(df_clean)} 人")
        return df_clean

# ============================================================================
#  模块 4: step2_dur —— 作答时间
# ============================================================================
class Step2Dur:
    """作答时间过短或过长均视为异常。"""

    @staticmethod
    def run(df: pd.DataFrame, cfg: Config) -> pd.DataFrame:
        print("\n" + "=" * 40)
        print("STEP 2-A: DUR 作答时间检查")
        print("=" * 40)

        df["DUR_num"] = pd.to_numeric(df["DUR"], errors="coerce")
        flag = (df["DUR_num"] < cfg.DUR_MIN) | (df["DUR_num"] > cfg.DUR_MAX)
        df["flag_dur"] = flag.astype(int)

        print(f"  阈值: < {cfg.DUR_MIN} min 或 > {cfg.DUR_MAX} min")
        print(f"  >>> 命中: {flag.sum()} 人")
        return flag

# ============================================================================
#  模块 5: step2_maha —— 马氏距离
# ============================================================================
class Step2Mahalanobis:
    """P11A-E（P11A 翻转后）5 维向量马氏距离 D^2。
    需在调用前由 encoding 模块完成数字编码。
    """

    @staticmethod
    def run(df: pd.DataFrame, p11_mat: np.ndarray, cfg: Config) -> pd.DataFrame:
        print("\n" + "=" * 40)
        print("STEP 2-B: 马氏距离检查（P11A-E 5 题）")
        print("=" * 40)

        mask = ~np.isnan(p11_mat).any(axis=1)
        X = p11_mat[mask]

        mu = X.mean(axis=0)
        cov = np.cov(X, rowvar=False) + np.eye(5) * 1e-8
        inv_cov = inv(cov)

        d2 = np.full(len(df), np.nan)
        d2[mask] = [mahalanobis(x, mu, inv_cov) ** 2 for x in X]

        df["maha_d2"] = d2
        flag = pd.Series(d2 > cfg.MAHA_TH, index=df.index).fillna(False)
        df["flag_maha"] = flag.astype(int)

        print(f"  P11 完整作答: {mask.sum()} 人")
        print(f"  阈值: D^2 > {cfg.MAHA_TH}")
        print(f"  >>> 命中: {flag.sum()} 人")
        return flag

# ============================================================================
#  模块 6: step2_long —— 长串连续相同作答
# ============================================================================
class Step2Longstring:
    """21 道选择题归一化后排成一串，计算最长连续相同长度。

    归一化方式：每道题 (编码值 / 最大值) -> 0~1
    四舍五入到一位小数后比较连续相同长度。
    """

    @staticmethod
    def run(df: pd.DataFrame, cfg: Config, enc: Encoding) -> pd.DataFrame:
        print("\n" + "=" * 40)
        print("STEP 2-C: Longstring 检查（21 道选择题）")
        print("=" * 40)

        items = enc.longstring_items()
        encoded = np.full((len(df), len(items)), np.nan)

        for j, (col, dmap, reverse, max_val) in enumerate(items):
            vals = df[col].map(dmap)
            if reverse:
                vals = max_val + 1 - vals
            encoded[:, j] = vals.values / max_val

        longs = []
        for row in encoded:
            arr = row[~np.isnan(row)]
            if len(arr) < 2:
                longs.append(1)
                continue
            arr_r = np.round(arr, 1)
            mx = cur = 1
            for k in range(1, len(arr_r)):
                if arr_r[k] == arr_r[k - 1]:
                    cur += 1
                    if cur > mx:
                        mx = cur
                else:
                    cur = 1
            longs.append(mx)

        df["longstring"] = longs
        flag = df["longstring"] >= cfg.LONG_TH
        df["flag_long"] = flag.astype(int)

        n_answered = (~np.isnan(encoded)).sum(axis=1).mean()

        print(f"  纳入题数: {len(items)}")
        print(f"  平均每人作答: {n_answered:.1f} 题")
        print(f"  阈值: 连续相同 >= {cfg.LONG_TH} 题")
        print(f"  >>> 命中: {flag.sum()} 人")

        return flag

# ============================================================================
#  模块 7: step2_dkna —— DK/NA 泛滥
# ============================================================================
class Step2DKNA:
    """统计 55 道核心题中显式 'DK' / 'NA' 的次数。"""

    @staticmethod
    def _count(row, cfg, enc):
        return sum(
            1 for col in cfg.CORE_VARS
            if str(row.get(col, "")).strip() in enc.DKNA_SET
        )

    @staticmethod
    def run(df: pd.DataFrame, cfg: Config, enc: Encoding) -> pd.DataFrame:
        print("\n" + "=" * 40)
        print("STEP 2-D: DK/NA 泛滥检查")
        print("=" * 40)

        counts = df.apply(lambda r: Step2DKNA._count(r, cfg, enc), axis=1)
        df["dkna_count"] = counts
        flag = counts >= cfg.DKNA_TH
        df["flag_dkna"] = flag.astype(int)

        print(f"  纳入题数: {len(cfg.CORE_VARS)}")
        print(f"  阈值: DK/NA >= {cfg.DKNA_TH} 个")
        print(f"  >>> 命中: {flag.sum()} 人")
        return flag

# ============================================================================
#  模块 8: step3_aux —— 辅助矛盾指标
# ============================================================================
class Step3Auxiliary:
    """8 个辅助指标，仅标记不删除。

    建议：同一人被 >= 3 个辅助指标同时命中 -> 人工复核是否降级。
    """

    @staticmethod
    def run(df: pd.DataFrame, p11_mat: np.ndarray, enc: Encoding):
        print("\n" + "=" * 40)
        print("辅助指标（仅供参考，不直接剔除）")
        print("=" * 40)

        # [1] P11E > P11D：女权认属矛盾
        mask = ~np.isnan(p11_mat[:, 3:5]).any(axis=1)
        df["aux_p11_contra"] = ((p11_mat[:, 4] > p11_mat[:, 3]) & mask).astype(int)
        print(f"  [1] P11E>P11D: {df['aux_p11_contra'].sum()} 人")

        # [2] IRV = 0：P11 五题完全没波动
        irv = np.nanstd(p11_mat, axis=1)
        df["aux_irv_zero"] = ((irv == 0) & ~np.isnan(p11_mat).any(axis=1)).astype(int)
        print(f"  [2] IRV=0: {df['aux_irv_zero'].sum()} 人")

        # [3] P08=非常必要 + P09=负面感受
        cond = (df["P08"] == "Very necessary") & (df["P09"] == "Rather negative")
        df["aux_p8p9"] = cond.astype(int)
        print(f"  [3] P08+P09 矛盾: {cond.sum()} 人")

        # [4] 高兴趣 + 多 DK
        cond = (df["P01"].isin(["Very", "Quite"])) & (df["dkna_count"] >= 5)
        df["aux_p1_dk"] = cond.astype(int)
        print(f"  [4] 高兴趣+DK>=5: {cond.sum()} 人")

        # [5] P02 五渠道全一样
        p02 = df[["P02A","P02B","P02C","P02D","P02E"]].map(
            lambda x: enc.FREQ_5.get(x, np.nan)
        )
        df["aux_p2_same"] = (
            p02.notna().all(axis=1) & (p02.nunique(axis=1) == 1)
        ).astype(int)
        print(f"  [5] P02 五渠道全一样: {df['aux_p2_same'].sum()} 人")

        # [6] 参加过抗议但忘了主题
        cond = (
            df["P16"].isin(["Yes, in two or more", "Yes, once"])
            & (
                df["P16B_1"].isna()
                | (df["P16B_1"].astype(str).str.strip() == "DK")
                | (df["P16B_1"].astype(str).str.strip() == "")
            )
        )
        df["aux_protest_forget"] = cond.astype(int)
        print(f"  [6] 抗议忘主题: {cond.sum()} 人")

        # [7] 大学毕业 + 完全无法捍卫意见
        cond = (
            df["P25"].str.contains("University", na=False)
            & (df["P10B"] == "No capable")
        )
        df["aux_uni_nocap"] = cond.astype(int)
        print(f"  [7] 大学+无能力: {cond.sum()} 人")

        # [8] Very + P02 全 <= 2
        p02_max = p02.max(axis=1)
        cond = (df["P01"] == "Very") & (p02_max <= 2)
        df["aux_very_p2low"] = cond.astype(int)
        print(f"  [8] Very+P02全<=2: {cond.sum()} 人")

# ============================================================================
#  模块 9: reporter —— 综合标记 & 输出
# ============================================================================
class Reporter:
    """完成 OR 逻辑合并、命中详情记录、文件输出及最终汇总。"""

    @staticmethod
    def finalize(df: pd.DataFrame, flags: dict, cfg: Config):
        """flags = { "dur": bool_series, "maha": ..., "long": ..., "dkna": ... }"""

        print("\n" + "=" * 40)
        print("STEP 2 汇总: OR 逻辑")
        print("=" * 40)

        dur_flag  = flags["dur"]
        maha_flag = flags["maha"]
        long_flag = flags["long"]
        dkna_flag = flags["dkna"]

        # is_careless = 1 表示不认真
        df["is_careless"] = (
            dur_flag | maha_flag | long_flag | dkna_flag
        ).astype(int)

        df["hit_count"] = (
            df["flag_dur"] + df["flag_maha"] + df["flag_long"] + df["flag_dkna"]
        )

        df["hit_detail"] = ""
        df.loc[dur_flag,  "hit_detail"] += "DUR;"
        df.loc[maha_flag, "hit_detail"] += "Mahalanobis;"
        df.loc[long_flag, "hit_detail"] += "Longstring;"
        df.loc[dkna_flag, "hit_detail"] += "DKNA;"
        df["hit_detail"] = df["hit_detail"].str.rstrip(";")

        n_careless = df["is_careless"].sum()
        print(f"  不认真: {n_careless} 人")
        print(f"  命中分布:")
        for k, v in sorted(df["hit_count"].value_counts().items()):
            print(f"    命中 {k} 个指标: {v} 人")

        # ---------- 拆分输出 ----------
        print("\n" + "=" * 40)
        print("输出文件")
        print("=" * 40)

        df_clean = df[df["is_careless"] == 0].copy()
        df_clean.to_csv(cfg.CSV_CLEAN, index=False, encoding="utf-8-sig")
        print(f"  有效问卷: {len(df_clean)} 人 -> {cfg.CSV_CLEAN}")

        df_invalid = df[df["is_careless"] == 1].copy()
        df_invalid.to_csv(cfg.CSV_INVALID, index=False, encoding="utf-8-sig")
        print(f"  无效问卷: {len(df_invalid)} 人 -> {cfg.CSV_INVALID}")

        df.to_csv(cfg.CSV_DETAIL, index=False, encoding="utf-8-sig")
        print(f"  筛查明细: {len(df)} 行 -> {cfg.CSV_DETAIL}")

        # ---------- 最终汇总 ----------
        skip_deleted = cfg.N_ORIGINAL - len(df)
        total_deleted = skip_deleted + n_careless
        kept = len(df_clean)

        print("\n" + "=" * 60)
        print("筛查完成")
        print("=" * 60)
        print(f"  原始: {cfg.N_ORIGINAL} 人")
        print(f"  |-- 跳题违规: {skip_deleted} 人")
        print(f"  |-- 不认真:   {n_careless} 人")
        print(f"  |-- 合计删除: {total_deleted} 人 ({total_deleted/cfg.N_ORIGINAL*100:.1f}%)")
        print(f"  |-- 最终保留: {kept} 人 ({kept/cfg.N_ORIGINAL*100:.1f}%)")
        print("=" * 60)
        print("如需调整阈值，修改 Config 类中的 DUR_MIN/MAHA_TH/LONG_TH/DKNA_TH 后重新运行。")


# ====== 自动定位仓库根目录 ======
import os, sys
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))          # scripts/ 目录
REPO_ROOT = os.path.dirname(SCRIPT_DIR)                          # 仓库根目录



# ============================================================================
#  模块 10: main —— 主流程
# ============================================================================
def main():
    cfg = Config()
    enc = Encoding()

    # ---- 0. 加载 ----
    print("=" * 60)
    print("PROTEiCA 问卷数据清洗筛查 v2.0")
    print("=" * 60)
    df_raw = pd.read_csv(cfg.CSV_IN)
    print(f"\n原始样本: {cfg.N_ORIGINAL} 人")

    # ---- 1. 跳题违规 ----
    df = Step1SkipViolation.run(df_raw.copy())

    # ---- 提前编码 P11（马氏距离 + 辅助指标共用） ----
    p11_mat = np.full((len(df), 5), np.nan)
    for j, col in enumerate(cfg.P11_COLS):
        vals = df[col].map(enc.LIKERT)
        if j == 0:
            vals = 6 - vals  # P11A 翻转
        p11_mat[:, j] = vals.values

    # ---- 2. 四个核心指标 ----
    dur_flag  = Step2Dur.run(df, cfg)
    maha_flag = Step2Mahalanobis.run(df, p11_mat, cfg)
    long_flag = Step2Longstring.run(df, cfg, enc)
    dkna_flag = Step2DKNA.run(df, cfg, enc)

    # ---- 3. 辅助指标 ----
    Step3Auxiliary.run(df, p11_mat, enc)

    # ---- 4. 综合输出 ----
    Reporter.finalize(df, {
        "dur": dur_flag, "maha": maha_flag,
        "long": long_flag, "dkna": dkna_flag,
    }, cfg)

# ============================================================================
if __name__ == "__main__":
    main()
