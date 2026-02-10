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

    cur.execute("INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)", ("iqd_per_point", "10000"))

    con.commit()
    con.close()


def get_setting(key, default=None):
    con = connect()
    row = con.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    con.close()
    return row["value"] if row else default


def get_gift_by_id(gift_id: int):
    con = connect()
    row = con.execute("SELECT * FROM gifts WHERE id=?", (gift_id,)).fetchone()
    con.close()
    return row


def delete_gift(gift_id: int):
    """
    يحذف الهدية + يحذف كل عمليات الاستبدال المرتبطة بيها من redemptions
    (حتى ما تبقى بيانات مكسورة)
    """
    con = connect()
    con.execute("DELETE FROM redemptions WHERE gift_id=?", (gift_id,))
    con.execute("DELETE FROM gifts WHERE id=?", (gift_id,))
    con.commit()
    con.close()


def get_winners():
    """
    الرابحين = كل اللي استبدلوا هدية (من redemptions)
    نرجّع: اسم الفني + اسم الهدية + تاريخ
    """
    con = connect()
    rows = con.execute("""
        SELECT
          t.name AS tech_name,
          g.name AS gift_name,
          r.created_at AS won_at
        FROM redemptions r
        JOIN technicians t ON t.id = r.tech_id
        JOIN gifts g ON g.id = r.gift_id
        ORDER BY r.id DESC
    """).fetchall()
    con.close()
    return rows
