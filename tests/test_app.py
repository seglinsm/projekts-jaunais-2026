import os
import sqlite3
import tempfile
import unittest

from app import create_app


class GoalBloomTests(unittest.TestCase):
    def setUp(self):
        file_descriptor, self.database_path = tempfile.mkstemp(suffix=".db")
        os.close(file_descriptor)
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE": self.database_path,
                "SECRET_KEY": "test-secret",
            }
        )
        self.client = self.app.test_client()

    def tearDown(self):
        if os.path.exists(self.database_path):
            os.remove(self.database_path)

    def test_dashboard_redirects_to_login_for_guests(self):
        response = self.client.get("/dashboard")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers["Location"])

    def test_user_can_register_login_and_logout(self):
        register_response = self.client.post(
            "/register",
            data={
                "username": "demo_user",
                "password": "secret123",
                "confirm_password": "secret123",
            },
        )
        self.assertEqual(register_response.status_code, 302)
        self.assertIn("/login?", register_response.headers["Location"])

        login_response = self.client.post(
            "/login",
            data={
                "username": "demo_user",
                "password": "secret123",
            },
        )
        self.assertEqual(login_response.status_code, 302)
        self.assertIn("/dashboard?", login_response.headers["Location"])

        dashboard_response = self.client.get("/dashboard")
        dashboard_html = dashboard_response.get_data(as_text=True)
        self.assertEqual(dashboard_response.status_code, 200)
        self.assertIn("Krājumu panelis", dashboard_html)
        self.assertIn("../static/dashboard.js", dashboard_html)

        logout_response = self.client.post("/logout")
        self.assertEqual(logout_response.status_code, 302)
        self.assertIn("/login?", logout_response.headers["Location"])

    def test_user_can_save_plan_and_use_quick_add(self):
        self._register_and_login()

        save_response = self.client.post(
            "/dashboard",
            data={
                "goal_name": "Drošības spilvens",
                "goal_amount": "1000",
                "current_balance": "400",
                "monthly_contribution": "125",
                "target_date": "",
                "note": "Trīs mēnešu izdevumiem.",
            },
        )
        self.assertEqual(save_response.status_code, 302)
        self.assertIn("/dashboard?", save_response.headers["Location"])

        data_response = self.client.get("/api/dashboard-data")
        payload = data_response.get_json()
        self.assertEqual(data_response.status_code, 200)
        self.assertEqual(payload["goalName"], "Drošības spilvens")
        self.assertEqual(payload["progressPercentage"], 40.0)
        self.assertEqual(payload["note"], "Trīs mēnešu izdevumiem.")
        self.assertEqual(payload["statusLabel"], "Brīvāks temps")

        quick_add_response = self.client.post("/dashboard/quick-add", data={"amount": "25"})
        self.assertEqual(quick_add_response.status_code, 302)
        self.assertIn("/dashboard?", quick_add_response.headers["Location"])

        updated_data_response = self.client.get("/api/dashboard-data")
        updated_payload = updated_data_response.get_json()
        self.assertEqual(updated_payload["currentBalance"], 425.0)
        self.assertEqual(updated_payload["progressPercentage"], 42.5)

        connection = sqlite3.connect(self.database_path)
        row = connection.execute(
            """
            SELECT goal_name, current_balance, monthly_contribution
            FROM savings_profiles
            """
        ).fetchone()
        connection.close()

        self.assertEqual(row[0], "Drošības spilvens")
        self.assertEqual(row[1], 425.0)
        self.assertEqual(row[2], 125.0)

    def test_rendered_dashboard_contains_no_raw_jinja_tokens(self):
        self._register_and_login()

        response = self.client.get("/dashboard")
        html = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("{{", html)
        self.assertNotIn("{%", html)
        self.assertIn("../static/style.css", html)
        self.assertIn("../static/dashboard.js", html)

    def _register_and_login(self):
        self.client.post(
            "/register",
            data={
                "username": "demo_user",
                "password": "secret123",
                "confirm_password": "secret123",
            },
        )
        self.client.post(
            "/login",
            data={
                "username": "demo_user",
                "password": "secret123",
            },
        )


if __name__ == "__main__":
    unittest.main()
