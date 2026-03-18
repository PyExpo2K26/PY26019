"""
alert_service.py
Place this file in:  D:/FloodPredictionApp/utils/alert_service.py
"""

import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta

# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────

GMAIL_ADDRESS      = "shalinib491@gmail.com"
GMAIL_APP_PASSWORD = "jtzitoukkevtlaqw"

TWILIO_ACCOUNT_SID = "ACc3c8f99582634fc631ccc095b4a7cf72"
TWILIO_AUTH_TOKEN  = "1bc67fb3b31e393543526301db0a1635"
TWILIO_FROM_NUMBER = "+19897873589"
TWILIO_TO_NUMBER   = "+919578621748"

HIGH_RISK_PROBABILITY   = 0.65
MEDIUM_RISK_PROBABILITY = 0.45
ALERT_COOLDOWN_MINUTES  = 30

# ─────────────────────────────────────────────

_last_alert_times = {}


def _is_on_cooldown(location: str) -> bool:
    if location not in _last_alert_times:
        return False
    return datetime.now() - _last_alert_times[location] < timedelta(minutes=ALERT_COOLDOWN_MINUTES)


def _record_alert(location: str):
    _last_alert_times[location] = datetime.now()


class AlertService:
    """
    AlertService wraps email, SMS, and WhatsApp sending
    for the Flood Prediction System.
    """

    def __init__(
        self,
        gmail_address: str      = GMAIL_ADDRESS,
        gmail_password: str     = GMAIL_APP_PASSWORD,
        twilio_sid: str         = TWILIO_ACCOUNT_SID,
        twilio_token: str       = TWILIO_AUTH_TOKEN,
        twilio_from: str        = TWILIO_FROM_NUMBER,
        twilio_to: str          = TWILIO_TO_NUMBER,
    ):
        self.gmail_address  = gmail_address
        self.gmail_password = gmail_password
        self.twilio_sid     = twilio_sid
        self.twilio_token   = twilio_token
        self.twilio_from    = twilio_from
        self.twilio_to      = twilio_to

    # ── EMAIL ──────────────────────────────────────────────────────────────

    def send_email(
        self,
        to_email: str,
        subject: str,
        body: str
    ) -> bool:
        """
        Send an email via Gmail SMTP SSL.
        Returns True on success, False on failure.
        """
        try:
            msg = MIMEMultipart()
            msg["From"]    = self.gmail_address
            msg["To"]      = to_email
            msg["Subject"] = subject
            msg.attach(MIMEText(body, "plain"))

            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(self.gmail_address, self.gmail_password)
                server.sendmail(self.gmail_address, to_email, msg.as_string())

            return True

        except smtplib.SMTPAuthenticationError:
            print("[AlertService] Gmail authentication failed. Check your App Password.")
            return False
        except Exception as e:
            print(f"[AlertService] Email error: {e}")
            return False

    # ── SMS ────────────────────────────────────────────────────────────────

    def send_sms(
        self,
        to_number: str,
        body: str
    ) -> bool:
        """
        Send an SMS via Twilio.
        Returns True on success, False on failure.
        """
        try:
            from twilio.rest import Client
        except ImportError:
            print("[AlertService] Twilio not installed. Run: pip install twilio")
            return False

        try:
            client  = Client(self.twilio_sid, self.twilio_token)
            message = client.messages.create(
                body  = body,
                from_ = self.twilio_from,
                to    = to_number
            )
            print(f"[AlertService] SMS sent. SID: {message.sid}")
            return True

        except Exception as e:
            print(f"[AlertService] SMS error: {e}")
            return False

    # ── WHATSAPP ───────────────────────────────────────────────────────────

    def send_whatsapp(
        self,
        to_number: str,
        body: str
    ) -> bool:
        """
        Send a WhatsApp message via Twilio WhatsApp sandbox.
        Returns True on success, False on failure.
        """
        try:
            from twilio.rest import Client
        except ImportError:
            print("[AlertService] Twilio not installed. Run: pip install twilio")
            return False

        try:
            # Strip any existing whatsapp: prefix before adding it
            clean_to   = to_number.replace("whatsapp:", "")
            clean_from = self.twilio_from.replace("whatsapp:", "")

            client  = Client(self.twilio_sid, self.twilio_token)
            message = client.messages.create(
                body  = body,
                from_ = f"whatsapp:{clean_from}",
                to    = f"whatsapp:{clean_to}"
            )
            print(f"[AlertService] WhatsApp sent. SID: {message.sid}")
            return True

        except Exception as e:
            print(f"[AlertService] WhatsApp error: {e}")
            return False

    # ── CONVENIENCE: trigger all configured channels ───────────────────────

    def trigger_flood_alerts(
        self,
        location: str,
        risk_level: str,
        probability: float,
        rainfall: float,
        water_level: float,
        recipient_email: str = None,
        send_sms: bool       = False,
        send_whatsapp: bool  = False,
        to_phone: str        = None
    ) -> list:
        """
        High-level helper: checks thresholds, respects cooldown,
        then sends alerts on every enabled channel.
        Returns a list of result dicts.
        """
        results = []

        alert_required = (
            risk_level in ["High", "Very High"] and probability >= HIGH_RISK_PROBABILITY
        ) or (
            risk_level == "Medium" and probability >= MEDIUM_RISK_PROBABILITY
        )

        if not alert_required:
            results.append({
                "channel": "check", "success": False,
                "message": f"Risk ({risk_level}, {round(probability*100,1)}%) below threshold."
            })
            return results

        if _is_on_cooldown(location):
            minutes_left = ALERT_COOLDOWN_MINUTES - int(
                (datetime.now() - _last_alert_times[location]).total_seconds() / 60
            )
            results.append({
                "channel": "cooldown", "success": False,
                "message": f"Cooldown active for {location}. {minutes_left} min remaining."
            })
            return results

        _record_alert(location)
        timestamp = datetime.now().strftime("%d %b %Y, %I:%M %p")
        prob_pct  = round(probability * 100, 1)

        body = (
            f"FLOOD ALERT [{risk_level.upper()}]\n"
            f"Location   : {location}\n"
            f"Time       : {timestamp}\n"
            f"Probability: {prob_pct}%\n"
            f"Rainfall   : {rainfall} mm\n"
            f"Water Level: {water_level} m\n"
            f"Action     : {'EVACUATE NOW. Move to higher ground.' if risk_level in ['High','Very High'] else 'Stay alert. Prepare emergency kit.'}\n"
            f"Helpline   : 1070"
        )

        if recipient_email:
            ok = self.send_email(
                to_email = recipient_email,
                subject  = f"[FLOOD ALERT] {risk_level} Risk - {location}",
                body     = body
            )
            results.append({"channel": "email", "success": ok,
                             "message": f"Email {'sent' if ok else 'failed'} to {recipient_email}"})

        if send_sms:
            ok = self.send_sms(to_phone or self.twilio_to, body)
            results.append({"channel": "sms", "success": ok,
                             "message": f"SMS {'sent' if ok else 'failed'}"})

        if send_whatsapp:
            ok = self.send_whatsapp(to_phone or self.twilio_to, body)
            results.append({"channel": "whatsapp", "success": ok,
                             "message": f"WhatsApp {'sent' if ok else 'failed'}"})

        if not results:
            results.append({"channel": "none", "success": False,
                             "message": "No alert channels configured."})

        return results