import tempfile
import unittest
from pathlib import Path

from src.aso_platform.services.saas_store import SaasStore


class SaasStoreTests(unittest.TestCase):
    def test_signup_project_and_analysis_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = SaasStore(Path(tmp) / "saas.sqlite3")
            account = store.signup("founder@example.com", "Founder Lab")
            project = store.create_project(
                account["organization"]["id"],
                {
                    "name": "Calc Lab",
                    "package_id": "com.example.calc",
                    "category": "tools",
                    "seed_text": "calculator",
                    "competitors": "com.comp.one, com.comp.two",
                },
            )
            analysis = store.record_analysis(
                account["organization"]["id"],
                project["id"],
                "keyword_score",
                {"scores": [{"keyword": "calculator"}]},
            )
            auth = store.create_auth_token("founder@example.com", "Founder Lab")
            verified = store.verify_auth_token(auth["token"])
            job = store.create_job(account["organization"]["id"], project["id"])
            running = store.start_job(account["organization"]["id"], job["id"])
            completed = store.complete_job(account["organization"]["id"], job["id"], analysis["id"])

            projects = store.list_projects(account["organization"]["id"])
            analyses = store.list_analyses(account["organization"]["id"])

        self.assertEqual(account["user"]["email"], "founder@example.com")
        self.assertEqual(project["competitors"], ["com.comp.one", "com.comp.two"])
        self.assertEqual(len(projects), 1)
        self.assertEqual(analysis["summary"], "1 keyword estimates")
        self.assertTrue(analysis["action_plan"])
        self.assertEqual(verified["user"]["email"], "founder@example.com")
        self.assertEqual(running["status"], "running")
        self.assertEqual(completed["status"], "succeeded")
        self.assertEqual(len(analyses), 1)

    def test_quota_helpers_count_projects_and_analyses_today(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = SaasStore(Path(tmp) / "saas.sqlite3")
            account = store.signup("quota@example.com", "Quota")
            project = store.create_project(account["organization"]["id"], {"name": "Calc", "package_id": "com.example.calc"})
            store.record_analysis(account["organization"]["id"], project["id"], "keyword_score", {"scores": []})

            self.assertEqual(store.count_projects(account["organization"]["id"]), 1)
            self.assertEqual(store.count_analyses_today(account["organization"]["id"]), 1)

    def test_get_job_not_found(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = SaasStore(Path(tmp) / "saas.sqlite3")
            with self.assertRaisesRegex(KeyError, "Job not found."):
                store.get_job(organization_id=1, job_id=1)


if __name__ == "__main__":
    unittest.main()
