import json
import os
import subprocess
import sys
import time
import unittest
from pathlib import Path

os.environ.setdefault("LLM_MODE", "mock")
os.environ.setdefault("DB_READY_WAIT_SECONDS", "0")

from fastapi.testclient import TestClient

from app.main import app
from app.mock_llm import mock_answer
from app.settings import http_origin, public_api_base

API = Path(__file__).resolve().parents[1]


class SettingsTests(unittest.TestCase):
    def test_origin_rejects_secrets_and_scripts(self):
        self.assertIsNone(http_origin("javascript:alert(1)"))
        self.assertIsNone(http_origin("https://user:secret@example.com"))
        self.assertEqual(http_origin("https://example.com/path"), "https://example.com")
        self.assertEqual(
            http_origin("https://chat-with-me.fastapicloud.dev/v1/chat"),
            "https://chat-with-me.fastapicloud.dev",
        )

    def test_public_api_defaults_to_the_live_host(self):
        previous = os.environ.pop("PUBLIC_API_URL", None)
        alias = os.environ.pop("WIDGET_API_BASE", None)
        try:
            self.assertEqual(public_api_base(), "https://chat-with-me.fastapicloud.dev")
        finally:
            if previous is not None:
                os.environ["PUBLIC_API_URL"] = previous
            if alias is not None:
                os.environ["WIDGET_API_BASE"] = alias


class PageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.client.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.client.__exit__(None, None, None)

    def test_root_is_a_chat_page(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers["content-type"])
        self.assertIn("Ask about the work.", response.text)
        self.assertNotIn("Not Found", response.text)

    def test_health_is_fast_and_shaped(self):
        started = time.perf_counter()
        response = self.client.get("/health")
        elapsed = time.perf_counter() - started
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["api"], "ok")
        self.assertIn(body["db"], {"starting", "ok", "error", "unconfigured"})
        self.assertLess(elapsed, 1.0)

    def test_embed_escapes_markup_and_ignores_bad_urls(self):
        response = self.client.get(
            "/embed",
            params={"title": "<script>alert(1)</script>", "accent": "red", "api": "javascript:alert(1)"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("<script>alert", response.text)
        self.assertNotIn("javascript:", response.text)
        self.assertIn("https://chat-with-me.fastapicloud.dev", response.text)
        self.assertIn('frame-ancestors *', response.headers.get("content-security-policy", ""))

    def test_widget_points_at_the_live_api(self):
        response = self.client.get("/widget.js")
        self.assertEqual(response.status_code, 200)
        self.assertIn("application/javascript", response.headers["content-type"])
        self.assertIn('var PORTFOLIO_API_BASE = "https://chat-with-me.fastapicloud.dev";', response.text)
        self.assertIn("dataset.api", response.text)
        self.assertIn("data-api", response.text)

    def test_example_page_loads_the_widget(self):
        response = self.client.get("/examples/embed.html")
        self.assertEqual(response.status_code, 200)
        self.assertIn('src="/widget.js"', response.text)
        self.assertIn("Ask Hassan", response.text)

    def test_home_can_target_another_api(self):
        response = self.client.get("/", params={"api": "https://chat-with-me.fastapicloud.dev/v1/chat"})
        config = json.loads(response.text.split('id="chat-config">', 1)[1].split("</script>", 1)[0])
        self.assertEqual(config["apiBase"], "https://chat-with-me.fastapicloud.dev")


class MockAnswerTests(unittest.TestCase):
    def test_hiring_answer_stays_inside_the_record(self):
        row = {
            "title": "Why hire Hassan",
            "category": "about",
            "score": 3,
            "content": (
                "Category: about\n"
                "Title: Why hire Hassan\n"
                "Hire Hassan when you need someone who owns backends in production. "
                "At Digital Matters he owns the NestJS backend for ReadMaududi (50,000+ readers)."
            ),
        }
        answer = mock_answer("Why should we hire you?", [row])
        self.assertIn("ReadMaududi", answer)
        self.assertIn("Hire me", answer)
        self.assertNotIn("Hire Hassan", answer)


class StartupTests(unittest.TestCase):
    def test_health_does_not_wait_on_a_slow_database(self):
        code = r"""
import os, time
os.environ["DATABASE_URL"] = "postgresql://portfolio:portfolio@203.0.113.1:5432/portfolio"
os.environ["DB_CONNECT_TIMEOUT"] = "3"
os.environ["DB_READY_WAIT_SECONDS"] = "0"
os.environ["LLM_MODE"] = "mock"
from fastapi.testclient import TestClient
from app.main import app
with TestClient(app) as client:
    started = time.perf_counter()
    response = client.get("/health")
    elapsed = time.perf_counter() - started
assert response.status_code == 200, response.text
assert response.json()["api"] == "ok"
assert elapsed < 1.0, elapsed
print("ok", round(elapsed, 3))
"""
        completed = subprocess.run(
            [sys.executable, "-c", code],
            cwd=API,
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr + completed.stdout)
        self.assertIn("ok", completed.stdout)


if __name__ == "__main__":
    unittest.main()
