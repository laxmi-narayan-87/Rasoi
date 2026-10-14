"""Regression tests for Vercel database failures and health diagnostics."""
import json
import os
import unittest
from unittest.mock import patch

from fastapi import HTTPException

from app.main import health, load_catalog, startup
from app.recipes import connect, database_backend


class VercelRuntimeTests(unittest.TestCase):
    def test_vercel_startup_does_not_run_database_ddl(self):
        with patch.dict(os.environ, {"VERCEL": "1"}):
            with patch("app.main.init_db") as init_db:
                startup()
        init_db.assert_not_called()

    def test_vercel_without_database_url_does_not_fall_back_to_sqlite(self):
        with patch.dict(os.environ, {"VERCEL": "1"}):
            with patch("app.recipes.DATABASE_URL", ""):
                self.assertEqual(database_backend(), "unconfigured")
                with self.assertRaisesRegex(RuntimeError, "DATABASE_URL is required"):
                    with connect():
                        pass

    def test_health_returns_503_diagnostic_when_database_is_unavailable(self):
        with patch.dict(os.environ, {"VERCEL": "1"}):
            with patch("app.recipes.DATABASE_URL", ""):
                with patch("app.main.all_recipes", side_effect=RuntimeError("connection failed")):
                    with patch("app.main.logger.exception"):
                        response = health()

        self.assertEqual(response.status_code, 503)
        payload = json.loads(response.body)
        self.assertEqual(payload["status"], "degraded")
        self.assertEqual(payload["database"], "unconfigured")
        self.assertIn("Production DATABASE_URL", payload["message"])

    def test_recipe_catalog_errors_are_returned_as_http_503(self):
        with patch("app.main.all_recipes", side_effect=RuntimeError("connection failed")):
            with patch("app.main.logger.exception"):
                with self.assertRaises(HTTPException) as caught:
                    load_catalog()

        self.assertEqual(caught.exception.status_code, 503)
        self.assertIn("DATABASE_URL", caught.exception.detail)


if __name__ == "__main__":
    unittest.main()
