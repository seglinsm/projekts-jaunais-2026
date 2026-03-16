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
            json={"title": "Vacation", "targetAmount": 500},
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
            json={"amount": 20, "date": "2026-03-08", "note": "Saved cash"},
        )
        second_manual = self.client.post(
            f"/api/goals/{goal_id}/contributions",
            json={"amount": 30, "date": "2026-03-15", "note": "Weekend bonus"},
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
        self.assertTrue(payload["estimateText"].startswith("At your current pace"))
        self.assertEqual(len(payload["contributions"]), 3)

    def test_goal_can_be_updated_and_deleted(self):
        create_response = self.client.post(
            "/api/goals",
            json={"title": "Laptop", "targetAmount": 1200},
        )
        goal_id = create_response.get_json()["id"]

        update_response = self.client.put(
            f"/api/goals/{goal_id}",
            json={
                "title": "Laptop Upgrade",
                "targetAmount": 1400,
                "description": "School and coding work",
            },
        )
        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(update_response.get_json()["title"], "Laptop Upgrade")

        delete_response = self.client.delete(f"/api/goals/{goal_id}")
        self.assertEqual(delete_response.status_code, 204)

        missing_response = self.client.get(f"/api/goals/{goal_id}")
        self.assertEqual(missing_response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
