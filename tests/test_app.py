import os
import tempfile
import unittest

from app import create_app


class SavingsApiTests(unittest.TestCase):
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

    def test_goal_summary_updates_with_recurring_plan_and_manual_deposits(self):
        goal_response = self.client.post(
            "/api/goals",
            json={"title": "Atvaļinājums", "targetAmount": 500},
        )
        self.assertEqual(goal_response.status_code, 201)
        goal_id = goal_response.get_json()["id"]

        plan_response = self.client.put(
            f"/api/goals/{goal_id}/recurring-plan",
            json={
                "amount": 50,
                "frequency": "monthly",
                "startDate": "2026-03-01",
                "isActive": True,
            },
        )
        self.assertEqual(plan_response.status_code, 200)

        first_manual = self.client.post(
            f"/api/goals/{goal_id}/contributions",
            json={"amount": 20, "date": "2026-03-08", "note": "Iekrāta skaidra nauda"},
        )
        second_manual = self.client.post(
            f"/api/goals/{goal_id}/contributions",
            json={"amount": 30, "date": "2026-03-15", "note": "Nedēļas nogales piemaksa"},
        )
        self.assertEqual(first_manual.status_code, 201)
        self.assertEqual(second_manual.status_code, 201)

        summary_response = self.client.get(f"/api/goals/{goal_id}")
        self.assertEqual(summary_response.status_code, 200)
        payload = summary_response.get_json()

        self.assertEqual(payload["totalSaved"], 100.0)
        self.assertEqual(payload["remainingAmount"], 400.0)
        self.assertEqual(payload["progressPercentage"], 20.0)
        self.assertEqual(payload["visualProgressPercentage"], 20.0)
        self.assertEqual(payload["recurringContributionAmount"], 50.0)
        self.assertTrue(payload["estimateText"].startswith("Ar pašreizējo tempu"))
        self.assertEqual(len(payload["contributions"]), 3)

    def test_goal_can_be_updated_and_deleted(self):
        create_response = self.client.post(
            "/api/goals",
            json={"title": "Klēpjdators", "targetAmount": 1200},
        )
        goal_id = create_response.get_json()["id"]

        update_response = self.client.put(
            f"/api/goals/{goal_id}",
            json={
                "title": "Klēpjdatora uzlabojums",
                "targetAmount": 1400,
                "description": "Skolas un programmēšanas darbam",
            },
        )
        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(update_response.get_json()["title"], "Klēpjdatora uzlabojums")

        delete_response = self.client.delete(f"/api/goals/{goal_id}")
        self.assertEqual(delete_response.status_code, 204)

        missing_response = self.client.get(f"/api/goals/{goal_id}")
        self.assertEqual(missing_response.status_code, 404)

    def test_web_goal_flow_supports_editing_and_deleting(self):
        create_response = self.client.post(
            "/goals",
            data={
                "title": "Velosipēds",
                "targetAmount": "300",
                "description": "Pilsētas braucieniem",
                "targetDate": "2026-09-01",
            },
        )
        self.assertEqual(create_response.status_code, 302)

        goals_response = self.client.get("/api/goals")
        self.assertEqual(goals_response.status_code, 200)
        goal_id = goals_response.get_json()["items"][0]["id"]

        dashboard_response = self.client.get("/")
        dashboard_html = dashboard_response.get_data(as_text=True)
        self.assertEqual(dashboard_response.status_code, 200)
        self.assertIn("SaveSprint Uzkrājumu panelis", dashboard_html)
        self.assertIn('action="/goals"', dashboard_html)

        add_contribution_response = self.client.post(
            f"/goals/{goal_id}/contributions",
            data={
                "amount": "45",
                "date": "2026-03-10",
                "note": "Kabatas nauda",
                "type": "manual",
            },
        )
        self.assertEqual(add_contribution_response.status_code, 302)

        contributions_response = self.client.get(f"/api/goals/{goal_id}/contributions")
        self.assertEqual(contributions_response.status_code, 200)
        contribution_id = contributions_response.get_json()["items"][0]["id"]

        update_contribution_response = self.client.post(
            f"/contributions/{contribution_id}/edit",
            data={
                "goal_id": str(goal_id),
                "amount": "55",
                "date": "2026-03-11",
                "note": "Atjaunināta piezīme",
                "type": "manual",
            },
        )
        self.assertEqual(update_contribution_response.status_code, 302)

        detail_response = self.client.get(f"/goals/{goal_id}")
        detail_html = detail_response.get_data(as_text=True)
        self.assertEqual(detail_response.status_code, 200)
        self.assertIn("Dzēst mērķi", detail_html)
        self.assertIn("Rediģēt", detail_html)
        self.assertIn("Atjaunināta piezīme", detail_html)
        self.assertIn("Manuāla", detail_html)

        delete_goal_response = self.client.post(f"/goals/{goal_id}/delete")
        self.assertEqual(delete_goal_response.status_code, 302)

        missing_response = self.client.get(f"/api/goals/{goal_id}")
        self.assertEqual(missing_response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
