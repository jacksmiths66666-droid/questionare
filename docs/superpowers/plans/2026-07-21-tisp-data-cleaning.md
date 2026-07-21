# TISP 数据清洗实施计划

> **第一轮机械筛查的最终执行口径以 `docs/TISP第一轮机械筛查优化实施计划.md` 为准。** 本文件保留完整项目（含后续人工复核、分析样本和报告）时间线；其中早期的题块式马氏距离描述已由优化计划中的“每国核心 27 题单一马氏距离”取代。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把学长给出的“自动初筛 → 人工复核 → 输出高质量样本”的思路，按 TISP 新问卷的题目、跳题与可用字段重新实现，并产出可复现、可审计的筛查结果。

**Architecture:** 将处理分成五层：先走读新问卷并记录题目顺序、量尺和跳题；再对 CSV 做不删人的基础审计；随后按 TISP 题块计算注意力题、马氏距离、奇偶一致性和 Longstring 等初筛信号；接着人工复核被标记记录；最后输出高质量、待复核和无效样本，并完整保留触发理由。官方数据的既有处理作为背景信息，但不代替本次任务要求的筛查。

**Tech Stack:** Python 3、pandas、numpy、pyarrow（可选）、CSV、JSON、Markdown。

---

### Task 1: 走读 TISP 新问卷并固定筛查边界

**Files:**
- Read-only: `D:\开山\收集数据\D081_TISP\D081_TISP\dataset.csv`
- Read-only: `D:\开山\收集数据\D081_TISP\D081_TISP\codebook.pdf`
- Read-only: `D:\开山\收集数据\D081_TISP\D081_TISP\questionnaire\D081_Questionnaire.pdf`
- Create: `docs/data-cleaning-scope.md`

- [ ] **Step 1: Confirm the input snapshot**

运行：

```powershell
Get-FileHash .\D081_TISP\dataset.csv -Algorithm SHA256
```

把文件哈希、文件大小、行数、列数写入 `docs/data-cleaning-scope.md`。原始 CSV 后续只读，不在原文件上覆盖保存。

- [ ] **Step 2: Build a question-map before screening**

从 `D081_Questionnaire.pdf` 和 `.qsf` 记录：每个题块的题目顺序、题型、分值范围、是否是量表题、是否有随机分流/跳题；特别标记两道注意力题、两道开放题和每个可用于 Longstring 的同量尺题块。

- [ ] **Step 3: Record completion time if an interactive questionnaire link is available**

由研究者完整填写若干次实际在线问卷，记录每次从开始到提交的秒数与路径。若当前只有 PDF/QSF 和最终 CSV、没有在线链接或原始时长字段，则明确记录“无法对每名受访者做时间筛查”，而不是编造时间阈值。

- [ ] **Step 4: Write the boundary in plain language**

在 `docs/data-cleaning-scope.md` 写明：当前 CSV 是 TISP 官方已发布样本，但本项目仍按任务要求开展独立的质量信号筛查；没有个体时长字段时不执行时间筛查；开放题空白因随机分流不直接判无效；所有自动指标只先标记、随后复核。

- [ ] **Step 5: Checkpoint with the user**

在继续任何删行操作前，向用户展示样本数、国家数和清洗边界，得到确认。

### Task 2: 生成第一份“不删人”的数据体检报告

**Files:**
- Create: `analysis/01_audit_tisp.py`
- Create: `outputs/audit/overview.json`
- Create: `outputs/audit/column_audit.csv`
- Create: `outputs/audit/country_counts.csv`
- Create: `outputs/audit/attention_audit.csv`

- [ ] **Step 1: Read the CSV and record basic structure**

脚本必须记录行数、列数、国家数量、每国样本量、列名和数据类型；读取失败时停止，不生成清洗数据。

- [ ] **Step 2: Count special missing codes without changing values**

对每列统计空值、`-99`、`-98`、`NA`、空字符串的数量；输出每列的非缺失比例。此步骤只统计，不替换。

- [ ] **Step 3: Check known quality fields**

分别统计：`ATTCHECK_NUMBER` 是否等于 213、`ATTCHECK_RES` 是否等于 1、`CONSENT` 是否等于 1，以及年龄是否在 18–100 之间。所有异常只写入审计表，不删除。

- [ ] **Step 4: Check item ranges using the questionnaire**

按题目量尺检查 1–5、1–7 和人口学分类变量的合法取值。`BENEFIT_OPEN` 与 `TRUST_OPEN` 的空白单独标记为“结构性缺失候选”，因为问卷随机只展示其中一道开放题。

- [ ] **Step 5: Run the audit and inspect the outputs**

运行：

```powershell
python .\analysis\01_audit_tisp.py
```

预期：生成审计文件；没有 `cleaned.csv`，没有删除任何行。

### Task 3: 实施 TISP 专属的自动机械初筛

**Files:**
- Create: `analysis/02_screen_tisp_quality.py`
- Create: `outputs/screening/tisp_quality_flags.csv`
- Create: `outputs/screening/tisp_screening_summary.csv`
- Create: `docs/decisions/tisp-screening-rules.md`

- [ ] **Step 1: Apply the two attention-check rules**

标记 `ATTCHECK_NUMBER != 213` 和 `ATTCHECK_RES != 1`。标记不等于立刻删除；先按国家列出异常数量，保留原始答案和触发原因。

- [ ] **Step 2: Calculate Mahalanobis distance within country**

不把 68 国、126 题混在一起算。第一轮主指标在同一国家内用 `TRUST_SCI_*`、`SCIPOP_*`、`OUTSPOKEN_*`、`SDO_*` 的固定 27 题计算一个核心马氏距离；缺失、标准化、收缩协方差与 99.5% 阈值均以 `TISP第一轮机械筛查优化实施计划.md` 为准。

- [ ] **Step 3: Calculate odd-even consistency within suitable item blocks**

只在题目内容与量尺足够一致的题块计算，先不把跨构念题目强行奇偶拆分；输出相关系数和“无法计算”的原因（题目太少、全选同一值、缺失过多）。

- [ ] **Step 4: Calculate Longstring by original question block**

按问卷原顺序，在同一组同量尺矩阵题中计算最长连续相同答案；不跨开放题、人口学题或不同量尺题块连续计数。

- [ ] **Step 5: Apply predeclared thresholds and record sensitivity counts**

不照抄旧代码的 `8.5` 和全局连续 12 题。主规则固定为：国别马氏距离第 99.5 百分位、两个奇偶题组都低于 0.10、Longstring 为题块长度的 80%；同时输出 99%、99.5%、99.75% 马氏距离阈值的敏感性计数，不在看过个体结果后修改主阈值。

- [ ] **Step 6: Create a review queue, not a deletion list**

将每条记录的触发指标组合成 `review_priority`；任何单一指标触发的记录都进入“待复核”，不直接输出为无效。

### Task 4: 人工复核自动标记的样本

**Files:**
- Create: `outputs/review/manual_review_template.csv`
- Create: `docs/manual-review-guide.md`

- [ ] **Step 1: Review open-ended answers when the answer was shown**

开放题为空不视为异常；若有回答，标记为“有实质内容”“无意义/乱填”“无法判断”。TISP 有多国语言回答，无法判断时保留为“无法判断”，不凭语言陌生直接判无效。

- [ ] **Step 2: Review the full response pattern and indicator combination**

逐条查看注意力题、马氏距离、奇偶一致性、Longstring 以及关键量表回答。只有多项指标共同支持粗心作答时，才建议判为无效；否则保留或列为待定。

- [ ] **Step 3: Record a human-readable decision**

每条复核记录必须填写 `final_decision`（保留/无效/待定）和 `decision_reason`；当前数据没有访谈意愿与联系方式，因此人工复核不含该项目。

### Task 5: 生成最终数据和清洗记录

**Files:**
- Create: `analysis/03_build_clean_dataset.py`
- Create: `outputs/final/high_quality_data.csv`
- Create: `outputs/final/invalid_or_review_data.csv`
- Create: `outputs/final/screening_log.csv`

- [ ] **Step 1: Recode confirmed special missing values**

将 codebook 确认的特殊缺失编码转为标准缺失值，并在日志中记录修改数量；不覆盖输入 CSV。

- [ ] **Step 2: Split by reviewed decision**

`high_quality_data.csv` 保留人工复核为“保留”的记录；`invalid_or_review_data.csv` 保留“无效”和“待定”记录，并显示每个触发指标与人工理由。

- [ ] **Step 3: Verify counts and reproducibility**

校验高质量、无效、待定三者合计等于输入行数；重新运行脚本时应生成同样的样本数与日志。

### Task 6: 根据研究问题构造量表与分析样本

**Files:**
- Create: `docs/analysis-question.md`
- Create: `analysis/03_build_analysis_dataset.py`
- Create: `outputs/analysis/analysis_dataset.csv`
- Create: `outputs/analysis/sample_flow.csv`

- [ ] **Step 1: Write the research question in one sentence**

明确因变量、核心自变量、控制变量、国家范围和分析单位。没有这一步，不决定最终删哪些缺失记录。

- [ ] **Step 2: Map constructs to item columns**

例如将 `TRUST_SCI_*`、`SCIPOP_*`、`OUTSPOKEN_*` 和 `SDO_*` 分别映射到理论构念；按 codebook 和论文确定反向计分，不能靠列名猜。

- [ ] **Step 3: Compute scale scores with a predeclared missing rule**

对每个量表规定最低回答题数；未达到最低题数则该量表得分为缺失，达到则按已回答题目计算均值或总分。规则写入 `docs/analysis-question.md`。

- [ ] **Step 4: Apply analysis-specific complete-case filtering**

只因本次模型所需变量缺失而排除记录；输出每一步剩余样本数和排除原因到 `sample_flow.csv`。开放题不作为所有分析的必需变量。

- [ ] **Step 5: Decide whether weights are required**

如果研究要做跨国总体推断，取得官方带权重版本并记录权重变量；如果只做样本内部关联分析，明确说明使用未加权数据的理由。

### Task 7: 筛查阈值敏感性分析

**Files:**
- Create: `analysis/04_sensitivity_quality_flags.py`
- Create: `outputs/sensitivity/quality_flags.csv`
- Create: `docs/sensitivity-analysis.md`

- [ ] **Step 1: Compare reasonable threshold choices**

比较不同马氏距离、奇偶一致性和 Longstring 阈值下的标记人数；确认结论不依赖一个任意阈值。

- [ ] **Step 2: Keep the main result tied to review decisions**

自动指标只提供证据；最终高质量/无效划分必须来自已记录的人工复核规则。

- [ ] **Step 3: Report whether conclusions change**

若两套样本的主要结论一致，则说明结果对额外质量标记稳健；若不一致，回到研究设计讨论，而不是直接选择更“好看”的结果。

### Task 8: 最终交付与方法文字

**Files:**
- Create: `docs/data-cleaning-method.md`
- Create: `outputs/final/README.md`

- [ ] **Step 1: Produce the sample flow**

从官方输入样本开始，列出每次变量处理和分析筛选后的样本量；区分“官方已处理”与“本研究新增处理”。

- [ ] **Step 2: Write the reproducibility note**

写明作答时长字段缺失，因此未能对个体执行时间筛查；开放题空白按随机分流处理；说明自动初筛指标、阈值、人工复核和最终人数。

- [ ] **Step 3: Final verification**

检查脚本可从原始 CSV 重新生成所有输出；确认原始 CSV 未被改写；检查输出样本数、国家数、缺失比例和量表分数范围。
