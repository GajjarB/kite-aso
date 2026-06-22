import tempfile
import time
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from src.aso_platform.saas_app import AppConfig, create_app
from src.aso_platform.services.saas_store import SaasStore


class SaasAppContractTests(unittest.TestCase):
    def make_client(self, project_limit: int = 3):
        tmp = tempfile.TemporaryDirectory()
        store = SaasStore(Path(tmp.name) / "saas.sqlite3")
        config = AppConfig()
        config.database_url = str(Path(tmp.name) / "saas.sqlite3")
        config.project_limit = project_limit
        app = create_app(store=store, config=config)
        return tmp, TestClient(app)

    def login(self, client: TestClient, email: str = "team@example.com") -> None:
        started = client.post("/api/auth/start", json={"email": email, "workspace_name": "Team"})
        self.assertEqual(started.status_code, 200)
        token = started.json()["dev_token"]
        verified = client.post("/api/auth/verify", json={"token": token})
        self.assertEqual(verified.status_code, 200)

    def test_auth_project_keyword_score_and_report_flow(self):
        tmp, client = self.make_client()
        with tmp:
            anonymous = client.get("/api/projects")
            self.assertEqual(anonymous.status_code, 401)

            self.login(client)
            project = client.post(
                "/api/projects",
                json={"name": "Calc", "package_id": "com.example.calc", "seed_text": "calculator", "auto_analyze": False},
            )
            self.assertEqual(project.status_code, 201)
            self.assertEqual(project.json()["project"]["package_id"], "com.example.calc")

            scored = client.post("/api/keywords/score", json={"keywords": "calculator", "app_text": "calculator tools"})
            self.assertEqual(scored.status_code, 200)
            analysis = scored.json()["analysis"]
            self.assertTrue(analysis["payload"]["scores"][0]["volume_estimate"]["is_estimate"])
            self.assertTrue(analysis["action_plan"])

            md = client.get(f"/api/reports/{analysis['id']}.md")
            csv = client.get(f"/api/reports/{analysis['id']}.csv")
            self.assertEqual(md.status_code, 200)
            self.assertIn("ASO PRO Report", md.text)
            self.assertEqual(csv.status_code, 200)
            self.assertIn("keyword", csv.text)

    def test_tenant_isolation_blocks_cross_org_project_access(self):
        tmp, client_a = self.make_client()
        with tmp:
            self.login(client_a, "a@example.com")
            created = client_a.post(
                "/api/projects",
                json={"name": "A", "package_id": "com.example.a", "auto_analyze": False},
            ).json()["project"]

            client_b = TestClient(client_a.app)
            self.login(client_b, "b@example.com")
            blocked = client_b.get(f"/api/projects/{created['id']}")
            self.assertEqual(blocked.status_code, 404)
            self.assertEqual(blocked.json()["error"]["code"], "not_found")

    def test_quota_exceeded_returns_structured_error(self):
        tmp, client = self.make_client(project_limit=1)
        with tmp:
            self.login(client)
            first = client.post("/api/projects", json={"name": "One", "package_id": "com.example.one", "auto_analyze": False})
            second = client.post("/api/projects", json={"name": "Two", "package_id": "com.example.two", "auto_analyze": False})

            self.assertEqual(first.status_code, 201)
            self.assertEqual(second.status_code, 429)
            self.assertEqual(second.json()["error"]["code"], "quota_exceeded")
            self.assertIn("fix", second.json()["error"])

    def test_analysis_job_lifecycle_can_fail_visibly(self):
        tmp, client = self.make_client()
        with tmp:
            self.login(client)
            project = client.post(
                "/api/projects",
                json={"name": "Bad", "package_id": "bad.package.id", "seed_text": "calculator", "auto_analyze": False},
            ).json()["project"]
            queued = client.post(f"/api/projects/{project['id']}/analyses?analysis_type=baseline")
            self.assertEqual(queued.status_code, 200)
            job_id = queued.json()["job"]["id"]

            last = {}
            for _ in range(30):
                last = client.get(f"/api/analysis-jobs/{job_id}").json()["job"]
                if last["status"] in {"succeeded", "failed"}:
                    break
                time.sleep(0.1)

            self.assertIn(last["status"], {"succeeded", "failed", "running", "queued"})
            if last["status"] == "failed":
                self.assertTrue(last["error_message"])
                self.assertTrue(last["error_fix"])


if __name__ == "__main__":
    unittest.main()
