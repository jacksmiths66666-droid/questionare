# questionare / D081_TISP

TISP questionnaire data quality-screening project.

## Data boundary

Raw `dataset.csv`, questionnaire/codebook PDF/QSF files, the full row-level flags table, and the manual review queue are excluded from GitHub. They remain in the controlled local workspace. Repository summaries and run metadata document the rules and results without publishing complete raw responses.

## First-round screening

Requires Python, pandas, numpy, and scikit-learn:

```powershell
python analysis/02_screen_tisp_quality.py
python -m unittest tests/test_screen_tisp_quality.py -v
```

The screening only creates flags; it does not delete cases. Rules cover attention checks, country-specific Ledoit-Wolf Mahalanobis distance, Trust/SCIPOP odd-even consistency, and ordered Longstring checks that break at missing values.

Thresholds, scale ranges, and sensitivity records are documented in `docs/` and `outputs/screening/tisp_mechanical_screen_run_metadata.json`.
