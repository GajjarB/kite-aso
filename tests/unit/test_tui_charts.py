import unittest

from src.aso_platform.tui_charts import count_by, is_ascii, mini_bar, rank_bar, score_buckets, sparkline


class TuiChartTests(unittest.TestCase):
    def test_mini_bar_handles_empty_and_overflow_values(self):
        self.assertEqual(mini_bar(0, 0, 6), "------   0%")
        self.assertEqual(mini_bar(150, 100, 6), "###### 100%")

    def test_rank_bar_caps_scores_and_stays_ascii(self):
        rendered = rank_bar(125, 8)

        self.assertIn("100.0", rendered)
        self.assertTrue(is_ascii(rendered))

    def test_sparkline_handles_empty_zero_and_narrow_widths(self):
        self.assertEqual(sparkline([], 4), "    ")
        self.assertEqual(sparkline([0, 0, 0], 4), "....")
        self.assertEqual(len(sparkline([1, 3, 2], 1)), 1)
        self.assertTrue(is_ascii(sparkline([1, 4, 2, 8], 10)))

    def test_counts_and_score_buckets_are_stable(self):
        items = [
            {"source": "seed", "composite_score": 35},
            {"source": "seed", "composite_score": 55},
            {"source": "category", "composite_score": 75},
            {"source": "category", "composite_score": 95},
        ]

        self.assertEqual(count_by(items, "source"), {"category": 2, "seed": 2})
        self.assertEqual(score_buckets(items), {"0-39": 1, "40-59": 1, "60-79": 1, "80-100": 1})


if __name__ == "__main__":
    unittest.main()
