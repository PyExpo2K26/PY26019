import unittest

from app import app


class ChatbotRouteTests(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()

    def login_session(self):
        with self.client.session_transaction() as session:
            session["user_email"] = "chatbot@example.com"
            session["user_name"] = "Chatbot User"

    def test_chatbot_page_requires_login(self):
        response = self.client.get("/chatbot")
        self.assertEqual(response.status_code, 302)

    def test_chatbot_api_returns_weather_reply(self):
        self.login_session()
        response = self.client.post(
            "/api/chatbot",
            json={"message": "weather in Chennai"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["intent"], "weather")
        self.assertIn("reply", payload)

    def test_chatbot_api_returns_route_reply(self):
        self.login_session()
        response = self.client.post(
            "/api/chatbot",
            json={"message": "safe route in Erode"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["intent"], "route")
        self.assertIn("reply", payload)
