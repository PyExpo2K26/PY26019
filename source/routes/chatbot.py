from functools import wraps

from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for


chatbot_bp = Blueprint("chatbot", __name__)
_ctx = {}


def configure_chatbot(**kwargs):
    _ctx.update(kwargs)


def _cfg(name):
    value = _ctx.get(name)
    if value is None:
        raise RuntimeError(f"Chatbot routes not configured: missing '{name}'")
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


@chatbot_bp.route("/chatbot")
@login_required
def chatbot_page():
    return render_template("chatbot.html")


@chatbot_bp.route("/api/chatbot", methods=["POST"])
@login_required
def api_chatbot():
    chatbot_service = _cfg("chatbot_service")
    payload = request.get_json() or {}
    message = payload.get("message", "")
    context = payload.get("context") or {}
    result = chatbot_service.process_message(message, context=context)
    return jsonify({"success": True, **result})
