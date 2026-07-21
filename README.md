# D081_TISP

TISP 问卷数据的第一轮机械质量筛查项目。

## 数据边界

原始 `dataset.csv`、问卷/代码本 PDF/QSF、完整逐行标记表和人工复核队列均不进入 GitHub。它们只在本地受控目录中使用。仓库中的汇总和运行元数据用于复现规则、核对版本和记录结果，不包含完整原始作答。

## 第一轮筛查

运行环境需要 Python、pandas、numpy、scikit-learn：

```powershell
python analysis/02_screen_tisp_quality.py
python -m unittest tests/test_screen_tisp_quality.py -v
```

筛查仅生成标记，不自动删除样本。规则包括注意力题、按国家独立计算的 Ledoit–Wolf 马氏距离、Trust/SCIPOP 奇偶一致性、以及按题目顺序且遇缺失中断的 Longstring。

正式阈值、量表范围和敏感性记录见 `docs/` 与 `outputs/screening/tisp_mechanical_screen_run_metadata.json`。
