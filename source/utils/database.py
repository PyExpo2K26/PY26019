import sqlite3
import os
import pandas as pd
from datetime import datetime

DB_PATH = "flood_data.db"


def init_db():
    """Initialize the database with all required tables"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Predictions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            rainfall REAL,
            water_level REAL,
            temperature REAL,
            humidity REAL,
            prediction INTEGER,
            probability REAL,
            risk_level TEXT,
            location TEXT
        )
    ''')

    # Alerts table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            location TEXT,
            risk_level TEXT,
            alert_method TEXT,
            recipient TEXT,
            phone TEXT,
            email TEXT,
            status TEXT,
            message TEXT,
            prediction_id INTEGER
        )
    ''')

    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            name TEXT,
            email TEXT,
            phone TEXT,
            location TEXT,
            alert_method TEXT
        )
    ''')

    conn.commit()
    conn.close()
    print("Database initialized successfully!")


def save_prediction(rainfall, water_level, temperature, humidity,
                    prediction, probability, risk_level, location="Unknown"):
    """Save a prediction to the database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO predictions
        (timestamp, rainfall, water_level, temperature, humidity,
         prediction, probability, risk_level, location)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        datetime.now().isoformat(),
        rainfall, water_level, temperature, humidity,
        prediction, probability, risk_level, location
    ))
    conn.commit()
    last_id = cursor.lastrowid
    conn.close()
    return last_id


def get_all_predictions(limit=10):
    """Get recent predictions from database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM predictions
        ORDER BY timestamp DESC
        LIMIT ?
    ''', (limit,))
    rows = cursor.fetchall()
    conn.close()

    predictions = []
    for row in rows:
        predictions.append({
            'id':          row[0],
            'timestamp':   row[1],
            'rainfall':    row[2],
            'water_level': row[3],
            'temperature': row[4],
            'humidity':    row[5],
            'prediction':  row[6],
            'probability': row[7],
            'risk_level':  row[8],
            'location':    row[9]
        })
    return predictions


def get_prediction_by_id(pred_id):
    """Get a specific prediction by ID"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM predictions WHERE id = ?', (pred_id,))
    row = cursor.fetchone()
    conn.close()

    if row:
        return {
            'id':          row[0],
            'timestamp':   row[1],
            'rainfall':    row[2],
            'water_level': row[3],
            'temperature': row[4],
            'humidity':    row[5],
            'prediction':  row[6],
            'probability': row[7],
            'risk_level':  row[8],
            'location':    row[9]
        }
    return None


class FloodDatabase:
    """Class-based interface for the flood database"""

    def __init__(self, db_path="flood_data.db"):
        global DB_PATH
        DB_PATH = db_path
        init_db()

    # ── Prediction methods ────────────────────────────────────────────────────

    def log_prediction(self, location, rainfall_mm, risk_level, probability, prediction_type):
        """Log a prediction to the database"""
        try:
            return save_prediction(
                rainfall=rainfall_mm,
                water_level=0,
                temperature=0,
                humidity=0,
                prediction=1 if risk_level in ["High", "Very High"] else 0,
                probability=probability,
                risk_level=risk_level,
                location=location
            )
        except Exception as e:
            print(f"DB log error: {e}")
            return False

    def get_recent(self, limit=10):
        """Get recent predictions as list"""
        return get_all_predictions(limit)

    def get_by_id(self, pred_id):
        """Get prediction by ID"""
        return get_prediction_by_id(pred_id)

    def get_predictions(self, limit=100, days=30, location=None):
        """Get predictions as DataFrame, optionally filtered by location and days"""
        conn = sqlite3.connect(DB_PATH)
        if location:
            query = '''
                SELECT * FROM predictions
                WHERE timestamp >= datetime('now', ?)
                AND location = ?
                ORDER BY timestamp DESC
                LIMIT ?
            '''
            df = pd.read_sql_query(query, conn, params=(f'-{days} days', location, limit))
        else:
            query = '''
                SELECT * FROM predictions
                WHERE timestamp >= datetime('now', ?)
                ORDER BY timestamp DESC
                LIMIT ?
            '''
            df = pd.read_sql_query(query, conn, params=(f'-{days} days', limit))
        conn.close()
        return df

    def get_prediction_stats(self, location=None):
        """Get prediction statistics, optionally filtered by location"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        where = "WHERE location = ?" if location else ""
        params = (location,) if location else ()

        cursor.execute(f"SELECT COUNT(*) FROM predictions {where}", params)
        total = cursor.fetchone()[0]

        cursor.execute(f"SELECT AVG(rainfall) FROM predictions {where}", params)
        avg_rainfall = cursor.fetchone()[0] or 0

        cursor.execute(f"SELECT COUNT(*) FROM predictions {where + (' AND' if location else 'WHERE')} risk_level = 'High'",
                       params)
        high_risk = cursor.fetchone()[0]

        cursor.execute(f"SELECT COUNT(*) FROM predictions {where + (' AND' if location else 'WHERE')} risk_level = 'Very High'",
                       params)
        very_high_risk = cursor.fetchone()[0]

        conn.close()
        return {
            'total_predictions':   total,
            'avg_rainfall':        round(avg_rainfall, 2),
            'high_risk_count':     high_risk,
            'very_high_risk_count': very_high_risk
        }

    # ── Alert methods ─────────────────────────────────────────────────────────

    def log_alert(self, location, risk_level, alert_method, recipient,
                  phone=None, email=None, status='Sent',
                  message='', prediction_id=None):
        """Log a sent alert to the database"""
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO alerts
                (timestamp, location, risk_level, alert_method, recipient,
                 phone, email, status, message, prediction_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                datetime.now().isoformat(),
                location, risk_level, alert_method, recipient,
                phone, email, status, message, prediction_id
            ))
            conn.commit()
            last_id = cursor.lastrowid
            conn.close()
            return last_id
        except Exception as e:
            print(f"Alert log error: {e}")
            return False

    def get_alerts(self, limit=100, days=30, location=None):
        """Get alerts as DataFrame, optionally filtered by location and days"""
        conn = sqlite3.connect(DB_PATH)
        if location:
            query = '''
                SELECT * FROM alerts
                WHERE timestamp >= datetime('now', ?)
                AND location = ?
                ORDER BY timestamp DESC
                LIMIT ?
            '''
            df = pd.read_sql_query(query, conn, params=(f'-{days} days', location, limit))
        else:
            query = '''
                SELECT * FROM alerts
                WHERE timestamp >= datetime('now', ?)
                ORDER BY timestamp DESC
                LIMIT ?
            '''
            df = pd.read_sql_query(query, conn, params=(f'-{days} days', limit))
        conn.close()
        return df

    def get_alert_stats(self, days=30):
        """Get alert statistics"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT COUNT(*) FROM alerts WHERE timestamp >= datetime('now', ?)",
            (f'-{days} days',)
        )
        total = cursor.fetchone()[0]

        cursor.execute(
            "SELECT COUNT(*) FROM alerts WHERE status = 'Sent' AND timestamp >= datetime('now', ?)",
            (f'-{days} days',)
        )
        sent = cursor.fetchone()[0]

        cursor.execute(
            "SELECT COUNT(*) FROM alerts WHERE status = 'Failed' AND timestamp >= datetime('now', ?)",
            (f'-{days} days',)
        )
        failed = cursor.fetchone()[0]

        cursor.execute(
            "SELECT COUNT(*) FROM alerts WHERE alert_method = 'SMS' AND timestamp >= datetime('now', ?)",
            (f'-{days} days',)
        )
        sms = cursor.fetchone()[0]

        cursor.execute(
            "SELECT COUNT(*) FROM alerts WHERE alert_method = 'Email' AND timestamp >= datetime('now', ?)",
            (f'-{days} days',)
        )
        email = cursor.fetchone()[0]

        cursor.execute(
            "SELECT COUNT(*) FROM alerts WHERE alert_method = 'WhatsApp' AND timestamp >= datetime('now', ?)",
            (f'-{days} days',)
        )
        whatsapp = cursor.fetchone()[0]

        conn.close()
        return {
            'total_alerts':   total,
            'sent_count':     sent,
            'failed_count':   failed,
            'sms_count':      sms,
            'email_count':    email,
            'whatsapp_count': whatsapp
        }

    # ── User methods ──────────────────────────────────────────────────────────

    def get_users_by_location(self, location):
        """Get users registered for a specific location"""
        conn = sqlite3.connect(DB_PATH)
        query = "SELECT * FROM users WHERE location = ? ORDER BY timestamp DESC"
        df = pd.read_sql_query(query, conn, params=(location,))
        conn.close()
        return df

    # ── Analytics methods ─────────────────────────────────────────────────────

    def get_risk_trends(self, location, days=30):
        """Get daily average flood probability trend for a location"""
        conn = sqlite3.connect(DB_PATH)
        query = '''
            SELECT DATE(timestamp) as date,
                   AVG(probability) as avg_probability,
                   COUNT(*) as event_count
            FROM predictions
            WHERE location = ?
            AND timestamp >= datetime('now', ?)
            GROUP BY DATE(timestamp)
            ORDER BY date ASC
        '''
        df = pd.read_sql_query(query, conn, params=(location, f'-{days} days'))
        conn.close()
        return df

    def get_location_comparison(self, days=90):
        """Compare high risk events across all locations"""
        conn = sqlite3.connect(DB_PATH)
        query = '''
            SELECT location,
                   COUNT(*) as total_predictions,
                   SUM(CASE WHEN risk_level IN ('High', 'Very High') THEN 1 ELSE 0 END) as high_risk_events,
                   AVG(probability) as avg_probability
            FROM predictions
            WHERE timestamp >= datetime('now', ?)
            GROUP BY location
            ORDER BY high_risk_events DESC
        '''
        df = pd.read_sql_query(query, conn, params=(f'-{days} days',))
        conn.close()
        return df

    def get_stats(self):
        """Get overall summary statistics"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute('SELECT COUNT(*) FROM predictions')
        total = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM predictions WHERE prediction = 1")
        flood_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM predictions WHERE risk_level = 'High'")
        high_risk = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM predictions WHERE risk_level = 'Very High'")
        very_high_risk = cursor.fetchone()[0]

        conn.close()
        return {
            'total':          total,
            'flood_count':    flood_count,
            'high_risk':      high_risk,
            'very_high_risk': very_high_risk,
            'safe_count':     total - flood_count
        }

    # ── Export methods ────────────────────────────────────────────────────────

    def export_to_csv(self, table_name, filepath):
        """Export a table to CSV file"""
        try:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            conn = sqlite3.connect(DB_PATH)
            df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
            conn.close()
            df.to_csv(filepath, index=False)
            print(f"Exported {table_name} to {filepath}")
            return True
        except Exception as e:
            print(f"Export error: {e}")
            return False