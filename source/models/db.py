import os
import sqlite3
from werkzeug.security import generate_password_hash as _hash


DB_PATH = os.getenv("DB_PATH", "artifacts/data/flood_data.db")
USERS_DB_PATH = os.getenv("USERS_DB_PATH", "artifacts/data/users.db")


def get_users_conn():
    conn = sqlite3.connect(USERS_DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_users_db():
    conn = get_users_conn()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            email          TEXT PRIMARY KEY,
            name           TEXT NOT NULL,
            password_hash  TEXT NOT NULL,
            phone          TEXT DEFAULT "",
            receive_alerts INTEGER DEFAULT 1
        )
        """
    )
    conn.commit()
    conn.close()


def get_user(email: str):
    conn = get_users_conn()
    row = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    conn.close()
    return dict(row) if row else None


def create_user(email, name, password, phone="", receive_alerts=True):
    conn = get_users_conn()
    try:
        conn.execute(
            "INSERT INTO users VALUES (?,?,?,?,?)",
            (email, name, _hash(password), phone, int(receive_alerts)),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def get_alert_recipients():
    conn = get_users_conn()
    rows = conn.execute(
        "SELECT name, email, phone FROM users WHERE receive_alerts=1"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
