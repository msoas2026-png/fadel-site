import os
import sqlite3
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "app.db")

def connect():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con

def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def init_db():
    con = connect()
    cur = con.cursor()

    cur.executescript("""
    CREATE TABLE IF NOT EXISTS admins (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'security' -- super / security
    );

    CREATE TABLE IF NOT EXISTS technicians (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        phone TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        specialty TEXT,
        points INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS gifts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        points_required INTEGER NOT NULL,
        image_filename TEXT,
        is_active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS points_tx (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tech_id INTEGER NOT NULL,
        purchase_amount INTEGER NOT NULL,
        points_added INTEGER NOT NULL,
        created_at TEXT NOT NULL,
        admin_id INTEGER,
        FOREIGN KEY (tech_id) REFERENCES technicians(id),
        FOREIGN KEY (admin_id) REFERENCES admins(id)
    );

    CREATE TABLE IF NOT EXISTS redemptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tech_id INTEGER NOT NULL,
        gift_id INTEGER NOT NULL,
        points_spent INTEGER NOT NULL,
        created_at TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        FOREIGN KEY (tech_id) REFERENCES technicians(id),
        FOREIGN KEY (gift_id) REFERENCES gifts(id)
    );

    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );
    """)

    # كل 10,000 دينار = 1 نقطة  (يعني 1,000,000 = 100 نقطة)
    cur.execute("INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)", ("iqd_per_point", "10000"))

    con.commit()
    con.close()

def get_setting(key, default=None):
    con = connect()
    row = con.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    con.close()
    return row["value"] if row else default
