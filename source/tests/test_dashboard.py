import unittest

from app import app


class DashboardRouteTests(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()

    def test_dashboard_redirects_when_logged_out(self):
        response = self.client.get("/dashboard", follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers["Location"])

    def test_dashboard_loads_when_logged_in(self):
        with self.client.session_transaction() as session:
            session["user_email"] = "dashboard@example.com"
            session["user_name"] = "Dashboard User"

        response = self.client.get("/dashboard")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Dashboard", response.data)

    def test_realtime_api_requires_login(self):
        response = self.client.get("/api/realtime-data")
        self.assertEqual(response.status_code, 401)

    def test_realtime_api_returns_json_when_logged_in(self):
        with self.client.session_transaction() as session:
            session["user_email"] = "dashboard@example.com"
            session["user_name"] = "Dashboard User"

        response = self.client.get("/api/realtime-data")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIn("prediction", payload)
        self.assertIn("rainfall", payload)
        self.assertIn("timestamp", payload)


if __name__ == "__main__":
    unittest.main()
