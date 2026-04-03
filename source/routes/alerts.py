from functools import wraps

from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for


alerts_bp = Blueprint("alerts", __name__)
_ctx = {}


def configure_alerts(**kwargs):
    _ctx.update(kwargs)


def _cfg(name):
    value = _ctx.get(name)
    if value is None:
        raise RuntimeError(f"Alerts routes not configured: missing '{name}'")
    return value


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_email" not in session:
            if request.path.startswith("/api/"):
                return jsonify({"success": False, "error": "Authentication required"}), 401
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)

    return decorated_function


@alerts_bp.route("/alerts")
@login_required
def alerts_page():
    return render_template("alerts.html")


@alerts_bp.route("/api/send-alert", methods=["POST"])
@login_required
def api_send_alert():
    send_email_now = _cfg("send_email_now")
    alert_service = _cfg("alert_service")
    alerts_ok = _cfg("ALERTS_OK")
    db_ok = _cfg("DB_OK")
    db = _cfg("db")
    datetime = _cfg("datetime")

    data = request.get_json() or {}
    to_email = data.get("email") or data.get("to_email")
    location = data.get("location", "Unknown")
    risk_level = data.get("risk_level", "Moderate")
    probability = float(data.get("probability", 50))
    rainfall = float(data.get("rainfall", 0))
    water_level = float(data.get("water_level", 0))
    phone = data.get("phone")

    ok, err = send_email_now(to_email, location, risk_level, probability, rainfall, water_level)
    sms_ok = None
    if alerts_ok and phone:
        try:
            sms_ok = alert_service.trigger_flood_alerts(
                location=location,
                risk_level=risk_level,
                probability=probability / 100,
                rainfall=rainfall,
                water_level=water_level,
                recipient_email=None,
                send_sms=True,
                send_whatsapp=True,
                to_phone=phone,
            )
        except Exception:
            sms_ok = False

    if db_ok and db is not None:
        try:
            db.log_alert(
                location=location,
                risk_level=risk_level,
                alert_method="Email" if ok else "Email Failed",
                recipient=to_email or "unknown",
                status="Sent" if ok else "Failed",
                message=f"Manual alert at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            )
        except Exception:
            pass

    return jsonify({"success": ok, "sms_success": sms_ok, "error": err})


@alerts_bp.route("/api/broadcast-alert", methods=["POST"])
@login_required
def api_broadcast_alert():
    broadcast_alert = _cfg("broadcast_alert")
    data = request.get_json() or {}
    location = data.get("location", "Unknown")
    risk_level = data.get("risk_level", "High")
    probability = float(data.get("probability", 75))
    rainfall = float(data.get("rainfall", 0))
    water_level = float(data.get("water_level", 0))
    broadcast_alert(location, risk_level, probability, rainfall, water_level)
    return jsonify({"success": True})


@alerts_bp.route("/api/alert-recipients")
@login_required
def api_alert_recipients():
    get_alert_recipients = _cfg("get_alert_recipients")
    return jsonify({"success": True, "recipients": get_alert_recipients()})


@alerts_bp.route("/api/alert-history")
@login_required
def api_alert_history():
    alert_log = _cfg("alert_log")
    rows = []
    for item in list(alert_log)[::-1]:
        row = dict(item)
        timestamp = row.get("timestamp")
        if hasattr(timestamp, "strftime"):
            row["timestamp"] = timestamp.strftime("%Y-%m-%d %H:%M:%S")
        rows.append(row)
    return jsonify({"success": True, "history": rows})


@alerts_bp.route("/api/alert-summary")
@login_required
def api_alert_summary():
    alert_log = _cfg("alert_log")
    total = len(alert_log)
    high = sum(1 for item in alert_log if item.get("risk_level") in ("High", "Very High"))
    moderate = sum(1 for item in alert_log if item.get("risk_level") in ("Moderate", "Medium"))
    latest = None
    if total:
        latest = dict(list(alert_log)[-1])
        ts = latest.get("timestamp")
        if hasattr(ts, "strftime"):
            latest["timestamp"] = ts.strftime("%Y-%m-%d %H:%M:%S")
    return jsonify(
        {
            "success": True,
            "summary": {
                "total_alerts": total,
                "high_or_higher": high,
                "moderate": moderate,
                "latest": latest,
            },
        }
    )
