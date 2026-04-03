import os
from utils.alert_service import AlertService


def build_alert_service():
    return AlertService(
        gmail_address=os.getenv("GMAIL_ADDRESS"),
        gmail_password=os.getenv("GMAIL_APP_PASSWORD"),
        twilio_sid=os.getenv("TWILIO_ACCOUNT_SID"),
        twilio_token=os.getenv("TWILIO_AUTH_TOKEN"),
        twilio_from=os.getenv("TWILIO_FROM_NUMBER"),
        twilio_to=os.getenv("TWILIO_TO_NUMBER"),
    )
