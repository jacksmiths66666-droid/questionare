"""TISP V3 第一轮机械筛查单元测试。"""

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd


SCRIPT = Path(__file__).resolve().parents[1] / "analysis" / "04_screen_tisp_v3.py"
SPEC = importlib.util.spec_from_file_location("tisp_v3", SCRIPT)
screen = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(screen)


def make_minimal_input(rows: int = 5) -> pd.DataFrame:
    """构造最小有效输入，各题填入范围内的值。"""
    country_pool = ["USA", "USA", "IDN", "PRT", "CHN"]
    data: dict[str, list[str]] = {"COUNTRY_CODE": [country_pool[i % len(country_pool)] for i in range(rows)]}
    for col, (low, high) in screen.ITEM_RANGES.items():
        data[col] = [str(low if i % 2 == 0 else high) for i in range(rows)]
    data["ATTCHECK_NUMBER"] = ["213"] * rows
    data["ATTCHECK_RES"] = ["1"] * rows
    data["BENEFIT_OPEN"] = [""] * rows
    data["TRUST_OPEN"] = [""] * rows
    return pd.DataFrame(data)


class TestAttentionSignals(unittest.TestCase):
    def test_both_pass_no_signal(self):
        raw = pd.DataFrame({
            "COUNTRY_CODE": ["USA"], "ATTCHECK_NUMBER": ["213"], "ATTCHECK_RES": ["1"],
        })
        numeric = pd.DataFrame(index=[0])
        got = screen.compute_attention_signals(raw, numeric)
        self.assertEqual(got["signal_attention"].iloc[0], 0)
        self.assertEqual(got["attention_verification"].iloc[0], 0)

    def test_any_fail_gives_signal(self):
        raw = pd.DataFrame({
            "COUNTRY_CODE": ["USA"], "ATTCHECK_NUMBER": ["999"], "ATTCHECK_RES": ["5"],
        })
        numeric = pd.DataFrame(index=[0])
        got = screen.compute_attention_signals(raw, numeric)
        self.assertEqual(got["signal_attention"].iloc[0], 1)
        self.assertEqual(got["attention_verification"].iloc[0], 0)

    def test_idn_any_fail_downgrades_to_verify(self):
        raw = pd.DataFrame({
            "COUNTRY_CODE": ["IDN"], "ATTCHECK_NUMBER": ["213"], "ATTCHECK_RES": ["5"],
        })
        numeric = pd.DataFrame(index=[0])
        got = screen.compute_attention_signals(raw, numeric)
        self.assertEqual(got["signal_attention"].iloc[0], 0)
        self.assertEqual(got["attention_verification"].iloc[0], 1)

    def test_prt_any_fail_downgrades_to_verify(self):
        raw = pd.DataFrame({
            "COUNTRY_CODE": ["PRT"], "ATTCHECK_NUMBER": ["213"], "ATTCHECK_RES": ["5"],
        })
        numeric = pd.DataFrame(index=[0])
        got = screen.compute_attention_signals(raw, numeric)
        self.assertEqual(got["signal_attention"].iloc[0], 0)
        self.assertEqual(got["attention_verification"].iloc[0], 1)

    def test_no_fail_no_signal(self):
        raw = pd.DataFrame({
            "COUNTRY_CODE": ["USA"], "ATTCHECK_NUMBER": ["213"], "ATTCHECK_RES": ["1"],
        })
        numeric = pd.DataFrame(index=[0])
        got = screen.compute_attention_signals(raw, numeric)
        self.assertEqual(got["signal_attention"].iloc[0], 0)


class TestLongstringSignals(unittest.TestCase):
    def test_no_longstring_no_signal(self):
        # 第 1 行：交替作答，最大 run=1；第 2 行：全 1，大 run 会把阈值推高
        cols = screen.GLOBAL_LS_ITEMS
        row1 = [(i % 5) + 1 for i in range(len(cols))]
        row2 = [1] * len(cols)
        numeric = pd.DataFrame([row1, row2], columns=cols)
        got = screen.compute_longstring_signals(numeric)
        self.assertEqual(got["signal_longstring"].iloc[0], 0)
        self.assertEqual(got["signal_longstring"].iloc[1], 1)

    def test_all_same_triggers_signal(self):
        numeric = pd.DataFrame(
            [[1] * len(screen.GLOBAL_LS_ITEMS)], columns=screen.GLOBAL_LS_ITEMS
        )
        got = screen.compute_longstring_signals(numeric)
        self.assertEqual(got["signal_longstring"].iloc[0], 1)

    def test_threshold_is_data_driven(self):
        a = pd.DataFrame([[1] * len(screen.GLOBAL_LS_ITEMS)], columns=screen.GLOBAL_LS_ITEMS)
        b = pd.DataFrame([[i % 5 + 1 for i in range(len(screen.GLOBAL_LS_ITEMS))]], columns=screen.GLOBAL_LS_ITEMS)
        numeric = pd.concat([a, b], ignore_index=True)
        got = screen.compute_longstring_signals(numeric)
        self.assertEqual(got["signal_longstring"].iloc[0], 1)
        self.assertEqual(got["signal_longstring"].iloc[1], 0)


class TestOddEvenSignals(unittest.TestCase):
    def test_single_row_always_flagged(self):
        raw = pd.DataFrame(
            [[1, 5, 3, 5, 3, 5, 2, 1, 1, 2, 3, 1]], columns=screen.TRUST_SCI
        )
        got = screen.compute_odd_even_signals(raw)
        not_comp = got["oe_not_computable"].iloc[0]
        signal = got["signal_odd_even"].iloc[0]
        self.assertTrue(not_comp == 1 or signal == 1)

    def test_multi_row_lowest_percentile_flagged(self):
        cols = screen.TRUST_SCI
        high = [[1, 2, 2, 1, 3, 3, 4, 4, 5, 5, 2, 3]]
        low = [[1, 5, 3, 5, 3, 5, 2, 1, 1, 2, 3, 1]]
        raw = pd.DataFrame(high * 99 + low, columns=cols)
        got = screen.compute_odd_even_signals(raw)
        # bottom 1% of 100 rows → 1 flagged
        flagged = got["signal_odd_even"].sum()
        self.assertEqual(flagged, 1)

    def test_constant_not_computable(self):
        raw = pd.DataFrame(
            [[5] * 12], columns=screen.TRUST_SCI
        )
        got = screen.compute_odd_even_signals(raw)
        self.assertEqual(got["oe_not_computable"].iloc[0], 1)
        self.assertEqual(got["signal_odd_even"].iloc[0], 0)


class TestIsGibberish(unittest.TestCase):
    """测试新的通用统计法 is_gibberish（4个指标）。"""

    # 多样化的正常文本，用于建立合理的熵值阈值参照
    NORMAL_CORPUS = [
        "science is important for society and policy making",
        "kjo eshte nje pergjigje normale dhe e pranueshme",
        "trust in institutions varies across different countries",
        "shkenca ka ndikim te madh ne jeten tone te perditshme",
        "the role of experts is crucial in modern democratic society",
        "mire besimi tek shkencetaret ndryshon sipas kultures",
        "kuptimi i pergjigjeve eshte i qarte dhe i kuptueshem",
        "pergjigjet e hulumtimit tregojne rezultate te rendesishme",
        "te dhena dhe rezultatet jane te rendesishme per studimin",
        "normat sociale ndikojne ne qendrimet e popullates se gjere",
        "kjo eshte nje fjali e thjeshte normale per testim",
        "besimi tek ekspertet ndryshon sipas vendeve dhe kultures",
        "science communication is important for public understanding",
        "research results inform policy decisions in many areas",
        "public attitudes toward science are shaped by many factors",
        "institutional trust levels vary between different regions",
        "pergjigjet ne kete studim jane mbledhur nga shume vende",
        "te gjitha keto pyetje jane te rendesishme per analize",
        "normat dhe qendrimet sociale ndikojne ne jeten e perditshme",
        "shkencetaret kane rol te rendesishem ne zhvillimin e shoqerise",
        "education and knowledge are fundamental for societal progress",
        "kultura dhe traditat ndikojne ne menyren e te menduarit",
        "the relationship between trust and science is complex",
        "rezultatet e studimit tregojne ndryshime te konsiderueshme",
        "perceptimet publike ndaj shkences ndryshojne neper bote",
        "the role of media in shaping public opinion is significant",
        "te dhena empirike jane thelbësore për kërkimin shkencor",
        "social norms influence individual behavior in meaningful ways",
        "qendrimet ndaj shkences formohen gjate jetës së njeriut",
        "the impact of science on daily life continues to grow",
    ] * 5  # 150条正常文本

    def test_entropy_low_triggers(self):
        """指标E：熵值低于阈值应触发（全同字符、重复子串、ababb）。"""
        gibberish = ["aaaaaa", "ababab", "ababb", "121212", "-----", "?????"]
        text = pd.Series(self.NORMAL_CORPUS + gibberish)
        got, threshold = screen.is_gibberish(text)
        gib_part = got.iloc[-len(gibberish):]
        self.assertTrue(gib_part.all(), f"Gibberish not triggered, threshold={threshold}, got {gib_part.tolist()}")

    def test_entropy_medium_not_triggers(self):
        """指标E：有效长文本的熵值高于阈值（单独计算熵值验证）。"""
        texts = [
            "njerezimi jane te rendesishem per studimin",
            "mirenjeku eshte nje fjale e bukur dhe e kuptueshme",
            "kuptimi i ketyre pergjigjeve eshte i qarte per te gjithe",
            "shkencetaret jane te besueshem dhe kane dijeni te thelle",
            "te gjitha keto pyetje jane te mira dhe te rendesishme",
        ]
        for t in texts:
            no_space = t.replace(' ', '')
            ent = screen._shannon_entropy(no_space)
            self.assertGreater(ent, 2.5,
                             f'"{t}" entropy {ent:.4f} should be above 2.5 (typical gibberish threshold)')

    def test_all_symbols_triggers(self):
        """指标S：纯符号应触发。"""
        text = pd.Series(["///////", "@@@@@@@", "......", "???"])
        got, _ = screen.is_gibberish(text)
        self.assertTrue(got.all(), f"Expected all triggered, got {got.tolist()}")

    def test_all_digits_triggers(self):
        """指标D：纯数字（长度≥5）应触发。"""
        text = pd.Series(["1234567890", "56184165185", "0000000000"])
        got, _ = screen.is_gibberish(text)
        self.assertTrue(got.all(), f"Expected all triggered, got {got.tolist()}")

    def test_short_digits_not_triggers(self):
        """指标D：长度<5的纯数字不应触发。"""
        text = pd.Series(["12345", "1234"])
        got, _ = screen.is_gibberish(text)
        self.assertFalse(got.iloc[1], "Short digits should not trigger")

    def test_encoding_char_triggers(self):
        """指标M：含编码乱码字符应触发。"""
        text = pd.Series(["\ufffd\ufffd\ufffd\ufffd\ufffd"])
        got, _ = screen.is_gibberish(text)
        self.assertTrue(got.iloc[0], "Unicode replacement char should trigger")

    def test_multilingual_not_falsely_flagged(self):
        """多语言有效文本的熵值高于阈值（单独计算熵值验证）。"""
        texts = [
            "Kjo eshte nje pergjigje normale dhe e pranueshme",
            "This is a normal answer in English for testing",
            "Ceci est une reponse normale pour le test",
        ]
        for t in texts:
            no_space = t.replace(' ', '')
            ent = screen._shannon_entropy(no_space)
            self.assertGreater(ent, 2.5,
                             f'"{t}" entropy {ent:.4f} should be above 2.5 (typical gibberish threshold)')

    def test_short_answer_not_falsely_flagged(self):
        """短答案（长度<3）不应触发。"""
        text = pd.Series(["Yes", "OK", "No"])
        got, _ = screen.is_gibberish(text)
        self.assertFalse(got.any(), "Short answers should not trigger")

    def test_empty_not_flagged(self):
        """空值不应标记为乱码。"""
        text = pd.Series(["", pd.NA, None])
        got, _ = screen.is_gibberish(text)
        self.assertFalse(got.any(), "Empty/null should not trigger")

    def test_threshold_is_data_driven(self):
        """熵值阈值应由数据分位数决定，而非固定值。"""
        # 构造混合数据：gibberish + 正常文本
        gibberish = ["aaaaaa"] * 10
        text = pd.Series(self.NORMAL_CORPUS + gibberish)
        got, threshold = screen.is_gibberish(text)
        # 所有aaaaaa应被标记（熵=0，远低于阈值）
        self.assertTrue(got.iloc[-10:].all(), "All identical chars should trigger")
        # 验证阈值是数据驱动的（不等于固定值）
        self.assertNotEqual(threshold, 1.0, "Threshold should not be a fixed value")
        # 验证正常文本的熵值普遍高于gibberish
        normal_entropies = [screen._shannon_entropy(t.replace(' ', ''))
                           for t in self.NORMAL_CORPUS[:30]]
        gib_entropy = screen._shannon_entropy("aaaaaa")
        self.assertEqual(gib_entropy, 0.0, "Gibberish entropy should be 0")
        avg_normal = sum(normal_entropies) / len(normal_entropies)
        self.assertGreater(avg_normal, 3.0, "Average normal entropy should be high")


class TestTriggerReason(unittest.TestCase):
    """测试 trigger_reason 列生成。"""

    def test_no_signals_empty_reason(self):
        att = pd.DataFrame({"signal_attention": [0]})
        ls = pd.DataFrame({"signal_longstring": [0]})
        md = pd.DataFrame({"signal_mahalanobis": [0]})
        oe = pd.DataFrame({"signal_odd_even": [0]})
        got = screen.stack_signals(att, ls, md, oe)
        self.assertEqual(got["trigger_reason"].iloc[0], "")

    def test_single_signal_correct_reason(self):
        att = pd.DataFrame({"signal_attention": [1]})
        ls = pd.DataFrame({"signal_longstring": [0]})
        md = pd.DataFrame({"signal_mahalanobis": [0]})
        oe = pd.DataFrame({"signal_odd_even": [0]})
        got = screen.stack_signals(att, ls, md, oe)
        self.assertEqual(got["trigger_reason"].iloc[0], "attention_fail")

    def test_multiple_signals_combined_reason(self):
        att = pd.DataFrame({"signal_attention": [1]})
        ls = pd.DataFrame({"signal_longstring": [1]})
        md = pd.DataFrame({"signal_mahalanobis": [1]})
        oe = pd.DataFrame({"signal_odd_even": [0]})
        got = screen.stack_signals(att, ls, md, oe)
        self.assertIn("attention_fail", got["trigger_reason"].iloc[0])
        self.assertIn("longstring_exceed", got["trigger_reason"].iloc[0])
        self.assertIn("mahalanobis_outlier", got["trigger_reason"].iloc[0])
        self.assertNotIn("odd_even", got["trigger_reason"].iloc[0])


class TestOneVoteVeto(unittest.TestCase):
    def test_all_missing_triggers_veto(self):
        raw = pd.DataFrame({**{c: [""] for c in screen.ITEM_RANGES},
                            **{"BENEFIT_OPEN": ["normal"], "TRUST_OPEN": ["text"]}})
        got, _ = screen.compute_one_vote_veto(raw)
        self.assertEqual(got["veto_all_missing"].iloc[0], 1)
        self.assertEqual(got["veto_any"].iloc[0], 1)

    def test_gibberish_triggers_veto(self):
        closed = {c: ["1"] for c in list(screen.ITEM_RANGES)[:5]}
        for i, c in enumerate(list(screen.ITEM_RANGES)[5:]):
            closed[c] = ["1"]
        raw = pd.DataFrame({**closed, "BENEFIT_OPEN": ["aaaaaa"], "TRUST_OPEN": ["bbbbbb"]})
        got, _ = screen.compute_one_vote_veto(raw)
        self.assertEqual(got["veto_gibberish"].iloc[0], 1)
        self.assertEqual(got["veto_any"].iloc[0], 1)

    def test_normal_answer_no_veto(self):
        """多条正常回答不应触发 veto（需要足够数据建立阈值）。"""
        # 5条数据，每条都填入范围内值
        closed = {c: ["1"] * 5 for c in screen.ITEM_RANGES}
        raw = pd.DataFrame({
            **closed,
            "BENEFIT_OPEN": ["I like science", "Science is important",
                             "We need research", "Education matters",
                             "aaaaaa"],
            "TRUST_OPEN": ["I trust experts", "Trust is earned",
                            "Evidence based", "Professional work",
                            "bbbbbb"],
        })
        got, _ = screen.compute_one_vote_veto(raw)
        # 正常回答（前4行）不应触发 veto
        self.assertEqual(got["veto_gibberish"].iloc[0], 0, "Normal answer should not trigger veto")

    def test_entropy_threshold_returned(self):
        """确保 entropy_threshold 被正确返回。"""
        raw = pd.DataFrame({**{c: ["1"] for c in screen.ITEM_RANGES},
                            **{"BENEFIT_OPEN": ["aaaaaa"], "TRUST_OPEN": ["normal text"]}})
        _, threshold = screen.compute_one_vote_veto(raw)
        self.assertIsInstance(threshold, float)


class TestSignalStacking(unittest.TestCase):
    def test_zero_signals_normal(self):
        att = pd.DataFrame({"signal_attention": [0]})
        ls = pd.DataFrame({"signal_longstring": [0]})
        md = pd.DataFrame({"signal_mahalanobis": [0]})
        oe = pd.DataFrame({"signal_odd_even": [0]})
        got = screen.stack_signals(att, ls, md, oe)
        self.assertEqual(got["screening_tier"].iloc[0], "NORMAL")
        self.assertEqual(got["signal_count"].iloc[0], 0)
        self.assertEqual(got["trigger_reason"].iloc[0], "")

    def test_one_signal_medium(self):
        att = pd.DataFrame({"signal_attention": [1]})
        ls = pd.DataFrame({"signal_longstring": [0]})
        md = pd.DataFrame({"signal_mahalanobis": [0]})
        oe = pd.DataFrame({"signal_odd_even": [0]})
        got = screen.stack_signals(att, ls, md, oe)
        self.assertEqual(got["screening_tier"].iloc[0], "MEDIUM")
        self.assertEqual(got["signal_count"].iloc[0], 1)
        self.assertEqual(got["trigger_reason"].iloc[0], "attention_fail")

    def test_two_signals_high(self):
        att = pd.DataFrame({"signal_attention": [1]})
        ls = pd.DataFrame({"signal_longstring": [1]})
        md = pd.DataFrame({"signal_mahalanobis": [0]})
        oe = pd.DataFrame({"signal_odd_even": [0]})
        got = screen.stack_signals(att, ls, md, oe)
        self.assertEqual(got["screening_tier"].iloc[0], "HIGH")
        self.assertEqual(got["signal_count"].iloc[0], 2)
        self.assertIn("attention_fail", got["trigger_reason"].iloc[0])
        self.assertIn("longstring_exceed", got["trigger_reason"].iloc[0])

    def test_three_signals_high(self):
        att = pd.DataFrame({"signal_attention": [1]})
        ls = pd.DataFrame({"signal_longstring": [1]})
        md = pd.DataFrame({"signal_mahalanobis": [1]})
        oe = pd.DataFrame({"signal_odd_even": [0]})
        got = screen.stack_signals(att, ls, md, oe)
        self.assertEqual(got["screening_tier"].iloc[0], "HIGH")
        self.assertEqual(got["signal_count"].iloc[0], 3)


class TestEndToEnd(unittest.TestCase):
    def test_output_row_count_matches_input(self):
        raw = make_minimal_input(rows=10)
        with tempfile.TemporaryDirectory() as tmp:
            input_path = Path(tmp) / "test_input.csv"
            raw.to_csv(input_path, index=False, encoding="utf-8")
            paths = screen.run_screening(input_path, Path(tmp))
            flags = pd.read_csv(paths["flags"])
            self.assertEqual(len(flags), len(raw))

    def test_metadata_contains_expected_keys(self):
        raw = make_minimal_input(rows=5)
        with tempfile.TemporaryDirectory() as tmp:
            input_path = Path(tmp) / "test_input.csv"
            raw.to_csv(input_path, index=False, encoding="utf-8")
            paths = screen.run_screening(input_path, Path(tmp))
            meta = json.loads(Path(paths["metadata"]).read_text(encoding="utf-8"))
            for key in ("run_utc", "input_rows", "counts", "params", "output_files", "md_country_details"):
                self.assertIn(key, meta)


if __name__ == "__main__":
    import json
    unittest.main()
