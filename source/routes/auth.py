from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from models.db import create_user, get_user


auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")

    data = request.get_json() or {}
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    user = get_user(email)

    if user and check_password_hash(user["password_hash"], password):
        session["user_email"] = email
        session["user_name"] = user["name"]
        return jsonify({"success": True, "name": user["name"], "redirect": "/dashboard"})

    return jsonify({"success": False, "error": "Invalid email or password."}), 401


@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json() or {}
    name = data.get("name", "").strip()
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    phone = data.get("phone", "").strip()
    receive_alerts = bool(data.get("receive_alerts", True))

    if not name or not email or not password:
        return jsonify({"success": False, "error": "All fields required."}), 400

    ok = create_user(email, name, password, phone, receive_alerts)
    if not ok:
        return jsonify({"success": False, "error": "Email already registered."}), 409

    return jsonify({"success": True})


@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("predictions.home"))
