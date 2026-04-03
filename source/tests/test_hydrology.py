import unittest

from app import app


class HydrologyRouteTests(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()

    def login_session(self):
        with self.client.session_transaction() as session:
            session["user_email"] = "hydrology@example.com"
            session["user_name"] = "Hydrology User"

    def test_hydrology_endpoint_requires_login(self):
        response = self.client.get("/api/hydrology")
        self.assertEqual(response.status_code, 401)

    def test_scenario_simulate_returns_projection_bundle(self):
        self.login_session()

        response = self.client.post(
            "/api/scenario-simulate",
            json={
                "location": "Chennai, Tamil Nadu",
                "rainfall_intensity": 18,
                "duration_hours": 8,
                "initial_water_level": 2.7,
                "flow_rate": 145,
                "curve_number": 78,
                "amc": "II",
                "terrain_sensitivity": 1.2,
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["success"])
        self.assertIn("simulation", payload)
        self.assertIn("prediction", payload)
        self.assertIn("forecast", payload)


if __name__ == "__main__":
    unittest.main()
