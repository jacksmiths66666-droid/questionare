# TISP 第一轮机械筛查优化实施计划（执行版）

## 1. 目标、边界与固定原则

### 1.1 本轮目标

基于 TISP `dataset.csv` 的正式封闭式题目，为每条记录生成可审计的机械筛查信号，识别需要进入第二轮人工复核的潜在粗心、随机或连续同选作答。

本轮**不生成最终“有效/无效”结论，不删除任何记录，不修改任何原始答案**。

### 1.2 固定边界

- 输入文件：`D081_TISP/dataset.csv`；当前为 71,922 行、126 列、68 个国家。
- 原始 CSV 只读；输出必须另存。
- `COUNTRY_CODE` 只用于分组比较，不作为作答题目进入任何分数。
- 年龄、性别、教育、收入、宗教、政治倾向、开放题、国家信息和派生变量全部保留，但不进入作答模式计算。
- 当前文件没有个体作答时间、访谈意愿和联系方式；本轮不构造时间筛查，不纳入访谈确认。
- 开放题为空不作为异常，因为问卷随机展示其中一道开放题。

### 1.3 两层结果

```text
第一轮：自动计算信号、标记原因、排定复核优先级
第二轮：人工查看完整模式和开放题，再作保留/待定/无效判断
```

第一轮的 `mechanical_flag` 仅表示“需要关注”，绝不表示“最终无效”。

---

## 2. 输入审计与运行前门槛

每次运行前，脚本必须完成以下检查；任一关键检查失败则停止，不输出筛查结果。

| 检查项 | 规则 |
|---|---|
| 输入快照 | 记录 SHA-256、文件大小、行数、列数和运行时间 |
| 必需列 | `COUNTRY_CODE`、两道注意力题、27 道核心量表题和 8 个 Longstring 题块的所有列均必须存在 |
| 国家样本量 | 每个国家的有效可用于马氏距离样本数必须至少为 135（即 27 个维度的 5 倍）；不足时该国 `md_not_computable=1` |
| 特殊编码 | 空字符串、`NA`、`N/A`、`-98`、`-99` 都视为缺失，仅在计算副本中转换；输出总表仍保留原始值 |
| 题目取值 | 对参与计算的题目核对合法范围；超范围值视为缺失并写入 `range_issue_flag` |
| 输出保护 | 输出行数必须等于输入行数；各国样本量必须完全一致；原始列名和原始列值不得被覆盖 |

输出中必须带有从 1 开始的 `row_id`，用于人工复核时稳定定位原始记录。该编号只表示输入文件中的原始行顺序，不声称是受访者真实 ID。

---

## 3. 题目配置：固定列表，不使用模糊前缀猜测

所有配置写入代码顶部的常量或单独的 JSON/YAML 配置文件。Longstring 的顺序必须与问卷原始展示顺序一致，不依赖 CSV 列的偶然排列。

### 3.1 马氏距离：核心 27 题

```text
TRUST_SCI_expert, TRUST_SCI_honest, TRUST_SCI_concerned,
TRUST_SCI_open, TRUST_SCI_intellig, TRUST_SCI_ethical,
TRUST_SCI_improve, TRUST_SCI_trans, TRUST_SCI_qualified,
TRUST_SCI_sincere, TRUST_SCI_otherint, TRUST_SCI_otherviews,

SCIPOP_common, SCIPOP_good, SCIPOP_advantage, SCIPOP_cahoots,
SCIPOP_influence, SCIPOP_involved, SCIPOP_lifeexp, SCIPOP_rely,

OUTSPOKEN_othersthink, OUTSPOKEN_isolate, OUTSPOKEN_against,

SDO_allgroupsconsider, SDO_notpushequality,
SDO_equalityideal, SDO_superiordominate
```

这 27 题构成每个人的核心作答画像。四个量表不在本轮做研究得分或反向计分；马氏距离使用的是同国回答模式及其协方差，因此允许题目间存在正相关或负相关。

### 3.2 奇偶一致性：两个辅助题组

| 题组 | 题目数 | 最低有效配对数 |
|---|---:|---:|
| `TRUST_SCI_*` | 12 | 4 对 |
| `SCIPOP_*` | 8 | 3 对 |

每个题组按已固定的原始顺序拆成奇数位和偶数位，相关只用同一位置的有效配对答案计算。

### 3.3 Longstring：八个连续题块

| 题块 | 长度 | 触发阈值 |
|---|---:|---:|
| `SCIINFO_*` | 10 | 连续相同 ≥8 |
| `NORMPERC_*` | 6 | 连续相同 ≥5 |
| `TRUST_SCI_*` | 12 | 连续相同 ≥10 |
| `SCIPOP_*` | 8 | 连续相同 ≥7 |
| `CLIM_EMO_*` | 9 | 连续相同 ≥8 |
| `CLIM_GOV_*` | 7 | 连续相同 ≥6 |
| `CLIM_WEATHERPAST_*` | 6 | 连续相同 ≥5 |
| `CLIM_WEATHERFUTU_*` | 6 | 连续相同 ≥5 |

阈值统一为 `ceil(题块长度 × 0.80)`；短于 6 题的题块不作为 Longstring 主判断。缺失值会中断连续序列，不能跨缺失连接前后答案。

`ATTCHECK_RES` 即使位于 SciPop 页面，也不并入 SciPop 的 Longstring 序列，因为它是带指令的注意力检查项，不是普通态度题。

固定顺序如下：

```text
SCIINFO = [SCIINFO_newspapersmags, SCIINFO_tvradio,
SCIINFO_newswebsitesapps, SCIINFO_videospodcasts, SCIINFO_filmsseries,
SCIINFO_books, SCIINFO_socialmedia, SCIINFO_messengers,
SCIINFO_museumszoos, SCIINFO_rlconversations]

NORMPERC = [NORMPERC_integrate, NORMPERC_advocate,
NORMPERC_communicate, NORMPERC_involved, NORMPERC_outreach,
NORMPERC_independent]

TRUST_SCI = [TRUST_SCI_expert, TRUST_SCI_honest, TRUST_SCI_concerned,
TRUST_SCI_open, TRUST_SCI_intellig, TRUST_SCI_ethical,
TRUST_SCI_improve, TRUST_SCI_trans, TRUST_SCI_qualified,
TRUST_SCI_sincere, TRUST_SCI_otherint, TRUST_SCI_otherviews]

SCIPOP = [SCIPOP_common, SCIPOP_good, SCIPOP_advantage, SCIPOP_cahoots,
SCIPOP_influence, SCIPOP_involved, SCIPOP_lifeexp, SCIPOP_rely]

CLIM_EMO = [CLIM_EMO_helpless, CLIM_EMO_anxious, CLIM_EMO_optimistic,
CLIM_EMO_angry, CLIM_EMO_guilty, CLIM_EMO_ashamed,
CLIM_EMO_depressed, CLIM_EMO_pessimistic, CLIM_EMO_indifferent]

CLIM_GOV = [CLIM_GOV_concerns, CLIM_GOV_doingenough,
CLIM_GOV_dismisspeople, CLIM_GOV_science, CLIM_GOV_futuregens,
CLIM_GOV_trustworthy, CLIM_GOV_lying]

CLIM_WEATHERPAST = [CLIM_WEATHERPAST_floods, CLIM_WEATHERPAST_heatwaves,
CLIM_WEATHERPAST_heavystorms, CLIM_WEATHERPAST_wildfires,
CLIM_WEATHERPAST_heavyrain, CLIM_WEATHERPAST_droughts]

CLIM_WEATHERFUTU = [CLIM_WEATHERFUTU_floods, CLIM_WEATHERFUTU_heatwaves,
CLIM_WEATHERFUTU_heavystorms, CLIM_WEATHERFUTU_wildfires,
CLIM_WEATHERFUTU_heavyrain, CLIM_WEATHERFUTU_droughts]
```

### 3.4 参与计算题目的合法数值范围

| 题组 | 合法值 |
|---|---|
| `SCIINFO_*` | 1–7 |
| `TRUST_SCI_*`、`SCIPOP_*`、`OUTSPOKEN_*`、`NORMPERC_*`、`CLIM_EMO_*`、`CLIM_GOV_*`、`CLIM_WEATHERPAST_*`、`CLIM_WEATHERFUTU_*` | 1–5 |
| `SDO_*` | 1–10 |
| `ATTCHECK_NUMBER` | 原始字符串；单独比较是否为 `213` |
| `ATTCHECK_RES` | 1–5；单独比较是否为 `1` |

任何不在表内范围的非缺失值先写入 `range_issue_flag`，再在计算副本中转为缺失；原始单元格不改写。

---

## 4. 四类机械指标与精确规则

### 4.1 注意力题：先标记，再核验编码

| 字段 | 预期答案 | 输出状态 |
|---|---|---|
| `ATTCHECK_NUMBER` | 字符串标准化后等于 `213` | `pass` / `fail` / `missing` |
| `ATTCHECK_RES` | 数值等于 `1` | `pass` / `anomaly` / `missing` |

当前基础审计发现：数字题异常 4 条；第二题非 1 有 302 条、缺失 2 条，且异常高度集中在印尼和葡萄牙。因此第一轮输出将第二题的非 1 标为 `attention_response_anomaly`，而不是直接写成最终失败。

在第二轮开始前，必须以 TISP 主问卷/QSF 和国家版本元数据核验该国编码；核验完成后才允许把该异常解释为 `attention_response_fail`。无论核验结果如何，本轮不删行。

### 4.2 马氏距离：每国一个核心画像距离

1. 以 `COUNTRY_CODE` 分组。
2. 对本国的 27 个核心题将特殊编码和超范围值视为缺失。
3. 若某条记录缺失 6 题及以上，则 `md_not_computable=1`；不填补、不标记 `md_flag`。
4. 对可计算记录：每一题以本国中位数临时填补缺失，再按本国均值和标准差做 z 标准化。
5. 本国中没有变化的题目从本国马氏距离计算中剔除，并记录 `md_dropped_constant_item_n`。
6. 使用 Ledoit-Wolf 收缩协方差估计量计算平方马氏距离，再开平方得到 `md_core_score`。该方法比直接求普通协方差逆矩阵更稳定。
7. 当本国有效样本数不少于 135 且实际参与维度至少为 10 时，计算该国 `md_core_threshold_p995`。
8. `md_core_score > md_core_threshold_p995` 时，`md_flag=1`。

主阈值固定为每个国家距离分布的第 99.5 百分位。它代表“本国最极端约 0.5% 的作答画像”，是进入复核队列的规则，不是无效判定。

同时输出预先指定的敏感性计数：第 99 百分位和第 99.75 百分位。敏感性结果只用于说明阈值对标记人数的影响，不改变主结果中的 `md_flag`。

### 4.3 奇偶一致性：低权重的随机作答辅助信号

1. 对 `TRUST_SCI_*` 与 `SCIPOP_*` 分别计算个体奇偶相关。
2. 有效配对数不足表 3.2 的最低要求时，填 `NaN` 并将相应 `*_eo_not_computable=1`。
3. 奇数或偶数向量标准差为 0 时，也填 `NaN` 并标为不可计算；该类整齐回答由 Longstring 判断，不用人为赋值为相关系数 1。
4. 每个可计算题组中，`r < 0.10` 生成该题组的低相关标记。
5. 只有在两个题组都可计算且都低于 0.10 时，才令 `odd_even_flag=1`。

这个“两个题组同时低相关”的合并规则故意保守，避免因为 TISP 量表含多个真实维度而把单一题组低相关误判为随机作答。单个题组的结果仍保留，供人工复核查看。

### 4.4 Longstring：题块内连续相同回答

对表 3.3 的每个题块、每条记录依题目顺序遍历：

- 连续相同值时累计；
- 不同值或缺失时重置；
- 输出每个题块的最大连续长度、触发值、起始题目和连续答案值；
- 任一题块达到对应阈值即 `longstring_flag=1`。

`longstring_flag` 是一个信号家族；同一个人在多个题块触发时，`flag_count` 仍只把 Longstring 计为 1，但详细题块字段完整保留。

---

## 5. 信号合并、优先级与第二轮交接

### 5.1 信号家族

`flag_count` 只统计四个家族，最大值为 4：

```text
attention_flag
md_flag
odd_even_flag
longstring_flag
```

`attention_flag` 在第一轮中包含数字题失败、第二题异常和注意力题缺失；第二题异常另有状态字段，防止被误说成已最终判定失败。

### 5.2 复核优先级

| `review_priority` | 规则 |
|---|---|
| `HIGH` | 注意力题异常；或至少两类非注意力信号同时触发 |
| `MEDIUM` | 仅马氏距离异常；或仅 Longstring 异常 |
| `LOW` | 仅奇偶一致性异常 |
| `NONE` | 四类信号均未触发 |
| `NOT_COMPUTABLE` | 所有可用信号均无法计算，且未有注意力题异常 |

没有任何第一轮优先级等同于“无效样本”。第二轮人工复核才填写 `final_decision` 和 `decision_reason`。

### 5.3 必须交给第二轮的材料

对每个触发记录，人工复核表至少包含：

- `row_id`、`COUNTRY_CODE`；
- 两道注意力题原始答案和状态；
- 马氏距离、国别阈值和排名百分位；
- 两个奇偶相关系数及不可计算原因；
- 每个触发 Longstring 的题块、起点、长度和答案；
- 两道开放题原始文本；
- `trigger_reason`、`review_priority`；
- 预留的 `final_decision`、`decision_reason` 和 `reviewer` 字段。

---

## 6. 输出契约

第一轮固定输出四个文件：

| 文件 | 内容 |
|---|---|
| `outputs/screening/tisp_mechanical_screen_flags.csv` | 全部原始列 + 所有第一轮指标、标记和复核优先级；行数必须为 71,922 |
| `outputs/screening/tisp_mechanical_screen_country_summary.csv` | 每国样本数、注意力题状态、马氏距离阈值、各类标记人数/比例、不可计算人数 |
| `outputs/screening/tisp_mechanical_screen_review_queue.csv` | 仅 `review_priority != NONE` 的记录及第二轮所需字段；是副本，不代表已删除其他记录 |
| `outputs/screening/tisp_mechanical_screen_run_metadata.json` | 输入哈希、运行时间、代码版本、题目配置、缺失规则、阈值和敏感性结果 |

所有输出必须采用 UTF-8 with BOM，方便 Excel 直接打开中文文本。

---

## 7. 验证与测试清单

### 7.1 自动检查

- 输出总表行数、国家数和各国样本量与输入完全相同。
- 原始 126 列均存在且原始单元格内容未改变。
- 27 个马氏距离题目、2 个奇偶题组、8 个 Longstring 题块的配置都通过列存在检查。
- 每国 `md_core_threshold_p995` 非空，或有明确的 `md_not_computable` 原因。
- `flag_count` 始终在 0–4 之间。
- `trigger_reason` 与对应 flag 一致。
- `review_priority=NONE` 的记录不得出现在 review queue。

### 7.2 小型合成数据单元测试

- 两个国家具有不同平均水平时，马氏距离只在各自国内计算，不互相影响。
- 12 题块连续 10 题相同会触发，连续 9 题不会触发。
- 缺失值会中断 Longstring。
- 两道注意力题的通过、异常和缺失状态正确。
- 仅一组奇偶相关低时不触发 `odd_even_flag`；两组均低时触发。
- 同一输入重复运行，输出关键数值和标记完全一致。

### 7.3 阈值敏感性审查

运行后只比较预设的 99%、99.5%、99.75% 马氏距离阈值下的国别标记率；不根据“结果好不好看”临时修改主阈值。若某国 99.5% 阈值下的标记率明显与其他国家不一致，记录原因供第二轮解释，但不改写该国规则。

---

## 8. 实施顺序与完成标准

1. 创建固定题目配置和输入预检。
2. 编写注意力题、马氏距离、奇偶一致性和 Longstring 函数，并用合成数据测试。
3. 在完整 TISP CSV 上运行，先只生成四类输出文件。
4. 核对输出保护、国别汇总、不可计算记录和敏感性结果。
5. 先完成 `ATTCHECK_RES` 的国家编码核验，再把 review queue 交给第二轮人工复核。

第一轮机械筛查只有同时满足以下条件才算完成：

- 不删除、不覆盖、不改写任何原始记录；
- 所有指标按上述固定题组和固定规则计算；
- 每条记录都有可追溯的状态与异常原因；
- 每个国家的比较只发生在本国内部；
- 阈值、缺失处理、不可计算情况和敏感性结果均写入元数据；
- 第二轮人工复核可以仅凭 review queue 和总表复现每条标记的原因。
