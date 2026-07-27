# questionare / D081_TISP

TISP 问卷数据质量筛查项目。

## 数据边界

原始数据 `dataset.csv`、问卷/码表 PDF/QSF 文件不进入 GitHub。摘要与运行元数据记录规则和结果，不发布完整原始作答。

## V3 两轮筛查方案

两轮架构：**第一轮自动化** → **第二轮人工复核**

### 第一轮：4 个并行信号

| 信号 | 方法 | 阈值 |
|------|------|------|
| 注意力题异常 | ATTCHECK_NUMBER≠213 或 ATTCHECK_RES≠1 | 任一失败 |
| Global Longstring | 全部封闭题的最长连续同选 | 99% 分位数（数据驱动） |
| 马氏距离 | 27 核心题，corrcoef + solve，按国家分组 | 99.5% 分位数 |
| 奇偶一致性 | TRUST_SCI 6 对配对 Pearson r | 1% 分位数 |

### 信号叠加

- **0 个信号** → NORMAL（不进复核）
- **1 个信号** → MEDIUM（入复核）
- **≥2 个信号** → HIGH（入复核）
- **一票无效**：全量表缺失 或 开放题纯乱码 → 直接标记，不进复核

### 乱码检测（4 通用统计指标）

替代枚举规则，用熵/符号比/数字比/编码字符 4 个指标覆盖所有乱码类型。

### 运行

```powershell
python analysis/04_screen_tisp_v3.py
python -m pytest tests/test_screen_tisp_v3.py -v
```

输出在 `outputs/screening_v3/`：
- `tisp_v3_flags.csv` — 全量 71,922 行 × 153 列
- `tisp_v3_review_queue.csv` — 复核队列 1,553 行 × 30 列
- `tisp_v3_signal_summary.csv` — 68 国汇总
- `tisp_v3_metadata.json` — 完整参数记录

### 依赖

Python, pandas, numpy。无需 sklearn。

## 项目结构

```
analysis/       分析脚本
tests/          单元测试
docs/           方案文档
outputs/        运行结果
D081_TISP/      原始数据
```
