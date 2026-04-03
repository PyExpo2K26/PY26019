import time
import unittest

from app import app
from models.db import create_user


class AuthRouteTests(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()
        self.email = f"test_{int(time.time() * 1000)}@example.com"
        self.password = "StrongPass123!"
        create_user(self.email, "Test User", self.password, "9999999999")

    def test_login_page_loads(self):
        response = self.client.get("/login")
        self.assertEqual(response.status_code, 200)

    def test_login_succeeds_with_valid_credentials(self):
        response = self.client.post(
            "/login",
            json={"email": self.email, "password": self.password},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["redirect"], "/dashboard")

    def test_login_fails_with_invalid_password(self):
        response = self.client.post(
            "/login",
            json={"email": self.email, "password": "wrong-password"},
        )

        self.assertEqual(response.status_code, 401)
        payload = response.get_json()
        self.assertFalse(payload["success"])

    def test_register_rejects_duplicate_email(self):
        response = self.client.post(
            "/register",
            json={
                "name": "Another User",
                "email": self.email,
                "password": "AnotherPass123!",
                "phone": "8888888888",
            },
        )

        self.assertEqual(response.status_code, 409)
        payload = response.get_json()
        self.assertFalse(payload["success"])


if __name__ == "__main__":
    unittest.main()
