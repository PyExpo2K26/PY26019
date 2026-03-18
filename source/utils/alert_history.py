

from datetime import datetime

# In-memory list of all alerts sent this session
# Each entry is a dict with full alert details
_alert_log = []


def log_alert(location, risk_level, probability, rainfall, water_level, channels_sent):
    """
    Save a triggered alert to the log.
    Called by trigger_flood_alerts() after sending.

    channels_sent: list of channel names that were attempted e.g. ['email', 'sms']
    """
    entry = {
        "id":           len(_alert_log) + 1,
        "timestamp":    datetime.now(),
        "location":     location,
        "risk_level":   risk_level,
        "probability":  round(probability * 100, 1),
        "rainfall":     rainfall,
        "water_level":  water_level,
        "channels":     channels_sent,
        "status":       "Sent"
    }
    _alert_log.append(entry)
    return entry


def get_all_alerts():
    """Return all alerts, most recent first."""
    return list(reversed(_alert_log))


def get_recent_alerts(n=10):
    """Return the last n alerts."""
    return list(reversed(_alert_log))[:n]


def get_alert_count():
    """Return total number of alerts sent."""
    return len(_alert_log)


def get_high_priority_count():
    """Return number of High or Very High alerts."""
    return sum(1 for a in _alert_log if a["risk_level"] in ["High", "Very High"])


def clear_alert_log():
    """Clear all stored alerts."""
    global _alert_log
    _alert_log = []


def get_alert_summary():
    """Return a summary dict for the analytics section."""
    total = len(_alert_log)
    if total == 0:
        return {
            "total": 0,
            "high": 0,
            "medium": 0,
            "locations": [],
            "last_alert": None
        }

    by_risk = {}
    locations = set()
    for a in _alert_log:
        by_risk[a["risk_level"]] = by_risk.get(a["risk_level"], 0) + 1
        locations.add(a["location"])

    return {
        "total":       total,
        "high":        by_risk.get("High", 0) + by_risk.get("Very High", 0),
        "medium":      by_risk.get("Medium", 0),
        "locations":   list(locations),
        "last_alert":  _alert_log[-1]["timestamp"].strftime("%d %b %Y, %I:%M %p")
    }
