import unittest

from core.keywords import (
    build_keyword_candidates,
    build_public_search_enrichment,
    get_category_seed_keywords,
    normalize_keyword_category,
    normalize_keyword_seed_input,
    score_keywords,
)


class KeywordInputTests(unittest.TestCase):
    def test_messy_comma_input_becomes_separate_clean_seeds(self):
        review = normalize_keyword_seed_input(
            "Calculator app, scientific calc, converter, BMI, Age, GPA, Paece, Loan, Savings rtc."
        )

        self.assertIn("calculator", review["seeds"])
        self.assertIn("scientific calculator", review["seeds"])
        self.assertIn("unit converter", review["seeds"])
        self.assertIn("bmi calculator", review["seeds"])
        self.assertIn("percentage calculator", review["seeds"])
        self.assertIn("savings calculator", review["seeds"])
        self.assertNotIn("calculator app, scientific calc", review["seeds"])
        self.assertTrue(review["corrections"])
        self.assertIn("rtc", review["ignored_terms"])

    def test_keyword_candidates_are_traceable_and_scored_with_confidence(self):
        review = normalize_keyword_seed_input("BMI, loan")
        candidates = build_keyword_candidates(review["seeds"], max_keywords=12)
        scored = score_keywords(candidates, {"data": {}})

        self.assertTrue(scored)
        self.assertIn("source", scored[0])
        self.assertIn("confidence", scored[0])
        self.assertIn(scored[0]["priority"], {"HIGH", "MEDIUM", "LOW"})
        self.assertEqual(scored[0]["type"], "seed")

    def test_all_normalized_seeds_are_kept_before_variants(self):
        review = normalize_keyword_seed_input(
            "Calculator app, scientific calc, converter, BMI, Age, GPA, Paece, Loan, Savings rtc."
        )
        candidates = build_keyword_candidates(review["seeds"], max_keywords=len(review["seeds"]))
        keywords = {item["keyword"] for item in candidates}

        self.assertEqual(set(review["seeds"]), keywords)

    def test_seed_terms_outrank_local_variants_without_live_evidence(self):
        review = normalize_keyword_seed_input(
            "calculator, scientific calculator, unit converter, bmi calculator"
        )
        candidates = build_keyword_candidates(review["seeds"], max_keywords=24)
        scored = score_keywords(candidates, {"data": {}})
        top_four = {item["keyword"] for item in scored[:4]}

        self.assertEqual(top_four, set(review["seeds"]))

    def test_category_keyword_discovery_works_without_free_form_input(self):
        category = get_category_seed_keywords("tool")
        seed_sources = {seed: "category_seed" for seed in category["seeds"]}
        candidates = build_keyword_candidates(category["seeds"], max_keywords=24, seed_sources=seed_sources)
        scored = score_keywords(candidates, {"data": {}})
        top_types = {item["type"] for item in scored[:len(category["seeds"])]}

        self.assertEqual(category["category"], "tools")
        self.assertIn("calculator", category["seeds"])
        self.assertEqual(scored[0]["type"], "category")
        self.assertEqual(scored[0]["source"], "category_seed")
        self.assertEqual(top_types, {"category"})

    def test_unknown_category_falls_back_safely(self):
        category = normalize_keyword_category("strange unknown market")

        self.assertFalse(category["matched"])
        self.assertEqual(category["category"], "")
        self.assertTrue(category["warnings"])

    def test_public_search_enrichment_adds_live_support_and_suggestions(self):
        def stub_search(query: str, n_hits: int = 8, lang: str = "en", country: str = "us") -> list[dict]:
            return [
                {
                    "title": "BMI Calculator - Weight Tracker",
                    "summary": "Body mass index and weight tracker",
                    "category": "Health & Fitness",
                },
                {
                    "title": "Calorie Counter & BMI Calculator",
                    "summary": "Track calories and bmi results",
                    "category": "Health & Fitness",
                },
            ]

        enrichment = build_public_search_enrichment(["bmi calculator"], stub_search, query_limit=1, n_hits=4)
        candidates = build_keyword_candidates(
            ["bmi calculator"],
            suggestions=enrichment["suggestions"],
            live_support_map=enrichment["live_support_map"],
            max_keywords=12,
        )
        scored = score_keywords(candidates, {"data": {}})

        self.assertGreater(enrichment["live_support_map"]["bmi calculator"], 0)
        self.assertTrue(any(item["source"] == "approved_public_suggestion" for item in scored))
        self.assertEqual(scored[0]["keyword"], "bmi calculator")
        self.assertEqual(scored[0]["confidence"], "high")

    def test_live_suggestions_outrank_category_seeds_for_category_discovery(self):
        seed_sources = {"calculator": "category_seed"}
        candidates = build_keyword_candidates(
            ["calculator"],
            suggestions=[
                {
                    "keyword": "scientific calculator",
                    "count": 4,
                    "type": "suggestion",
                    "source": "approved_public_suggestion",
                    "seed_index": 0,
                    "live_support": 3,
                }
            ],
            seed_sources=seed_sources,
            live_support_map={"calculator": 4},
            max_keywords=10,
        )
        scored = score_keywords(candidates, {"data": {}})

        self.assertEqual(scored[0]["keyword"], "scientific calculator")
        self.assertEqual(scored[0]["source"], "approved_public_suggestion")


if __name__ == "__main__":
    unittest.main()
