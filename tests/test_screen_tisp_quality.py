import importlib.util
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

SCRIPT = Path(__file__).resolve().parents[1] / "analysis" / "02_screen_tisp_quality.py"
SPEC = importlib.util.spec_from_file_location("tisp_screen", SCRIPT)
screen = importlib.util.module_from_spec(SPEC)
sys.modules["tisp_screen"] = screen
assert SPEC.loader is not None
SPEC.loader.exec_module(screen)


class ScreeningLogicTests(unittest.TestCase):
    def test_attention_statuses_distinguishes_anomaly_from_number_failure(self):
        raw = pd.DataFrame({"ATTCHECK_NUMBER": ["213", "212", "", "213"], "ATTCHECK_RES": ["1", "1", "1", "2"]})
        got = screen.attention_statuses(raw)
        self.assertEqual(got["attention_number_status"].tolist(), ["pass", "fail", "missing", "pass"])
        self.assertEqual(got["attention_response_status"].tolist(), ["pass", "pass", "pass", "anomaly"])
        self.assertEqual(got["attention_flag"].tolist(), [0, 1, 1, 1])

    def test_longest_run_counts_missing_as_a_break(self):
        run, start, value = screen.longest_run([1, 1, np.nan, 1, 1, 1, 2])
        self.assertEqual((run, start, value), (3, 4, 1))
        self.assertEqual(screen.longest_run([np.nan, np.nan])[1], None)

    def test_longstring_threshold_is_inclusive(self):
        columns = screen.LONG_BLOCKS["sciinfo"][0]
        numeric = pd.DataFrame([[2] * 8 + [3, 4]], columns=columns)
        # 补齐函数所需的其他长串题块；本测试只检查 sciinfo 这一项
        for block, (cols, _) in screen.LONG_BLOCKS.items():
            for col in cols:
                if col not in numeric:
                    numeric[col] = 1
        got = screen.calculate_longstrings(numeric)
        self.assertEqual(int(got.loc[0, "long_sciinfo_flag"]), 1)
        self.assertEqual(int(got.loc[0, "long_sciinfo_max_run"]), 8)

    def test_sciinfo_uses_its_true_one_to_seven_scale(self):
        values, issue = screen.numeric_with_range(pd.Series(["1", "7", "8", "-99"]), 1, 7)
        self.assertEqual(values.tolist()[:2], [1.0, 7.0])
        self.assertEqual(int(issue.sum()), 1)

    def test_odd_even_family_requires_both_scales_low(self):
        cols = screen.TRUST + screen.SCIPOP
        numeric = pd.DataFrame([[np.nan] * len(cols), [np.nan] * len(cols)], columns=cols)
        # trust odd/even pairs are inversely patterned -> r=-1; scipop pairs positive -> r=1
        numeric.loc[0, screen.TRUST] = [1, 5, 2, 4, 3, 3, 4, 2, 5, 1, 2, 4]
        numeric.loc[0, screen.SCIPOP] = [1, 1, 2, 2, 3, 3, 4, 4]
        numeric.loc[1, screen.TRUST] = [1, 5, 2, 4, 3, 3, 4, 2, 5, 1, 2, 4]
        numeric.loc[1, screen.SCIPOP] = [1, 1, 2, 2, 3, 3, 4, 4]
        got = screen.calculate_odd_even(numeric)
        self.assertEqual(int(got.loc[0, "trust_eo_low_flag"]), 1)
        self.assertEqual(int(got.loc[0, "scipop_eo_low_flag"]), 0)
        self.assertEqual(int(got.loc[0, "odd_even_flag"]), 0)

    def test_md_is_calculated_within_country_not_across_countries(self):
        rng = np.random.default_rng(7)
        n = 140
        cols = screen.CORE_MD_COLS
        a = pd.DataFrame(rng.integers(1, 6, size=(n, len(cols))), columns=cols)
        b = pd.DataFrame(rng.integers(1, 6, size=(n, len(cols))), columns=cols)
        numeric_one = pd.concat([a, b], ignore_index=True)
        countries = pd.Series(["A"] * n + ["B"] * n)
        score_one, _ = screen.calculate_country_mahalanobis(numeric_one, countries)
        numeric_two = numeric_one.copy()
        numeric_two.loc[n:, cols] = rng.integers(1, 6, size=(n, len(cols)))
        score_two, _ = screen.calculate_country_mahalanobis(numeric_two, countries)
        np.testing.assert_allclose(score_one.loc[: n - 1, "md_score"], score_two.loc[: n - 1, "md_score"])
        self.assertTrue(score_one.loc[: n - 1, "md_score"].notna().all())


if __name__ == "__main__":
    unittest.main()
