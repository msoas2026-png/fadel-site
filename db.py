import os
import sqlite3
from datetime import datetime

# إذا موجود DATABASE_URL => نستخدم Postgres (Supabase)
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

# مسار SQLite (للتشغيل المحلي بدون Supabase)
DB_PATH = os.path.join(os.path.dirname(__file__), "app.db")


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ========= Postgres Wrapper (حتى يشتغل كأنه sqlite) =========
def _is_postgres():
    return DATABASE_URL.startswith("postgres://") or DATABASE_URL.startswith("postgresql://")


def _translate_sql(sql: str) -> str:
    # sqlite يستخدم ? ، psycopg2 يستخدم %s
    return sql.replace("?", "%s")


class _PgCursorWrapper:
    def __init__(self, cur):
        self.cur = cur

    def fetchone(self):
        return self.cur.fetchone()

    def fetchall(self):
        return self.cur.fetchall()


class _PgConnWrapper:
    def __init__(self, conn):
        self.conn = conn

    def execute(self, sql, params=()):
        cur = self.conn.cursor(cursor_factory=__import__("psycopg2.extras").extras.RealDictCursor)
        cur.execute(_translate_sql(sql), params or ())
        return _PgCursorWrapper(cur)

    def commit(self):
        self.conn.commit()

    def close(self):
        self.conn.close()


def connect():
    if _is_postgres():
        import psycopg2
        # Supabase يعطي postgresql://...
        conn = psycopg2.connect(DATABASE_URL)
        return _PgConnWrapper(conn)

    # SQLite fallback
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


# ========= Init DB (SQLite أو Postgres) =========
def init_db():
    con = connect()

    if _is_postgres():
        # جداول Postgres
        con.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            id SERIAL PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'security'
        );
        """)

        con.execute("""
        CREATE TABLE IF NOT EXISTS technicians (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            phone TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            specialty TEXT,
            points INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        );
        """)

        con.execute("""
        CREATE TABLE IF NOT EXISTS gifts (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            points_required INTEGER NOT NULL,
            image_filename TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        );
        """)

        con.execute("""
        CREATE TABLE IF NOT EXISTS points_tx (
            id SERIAL PRIMARY KEY,
            tech_id INTEGER NOT NULL,
            purchase_amount INTEGER NOT NULL,
            points_added INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            admin_id INTEGER
        );
        """)

        con.execute("""
        CREATE TABLE IF NOT EXISTS redemptions (
            id SERIAL PRIMARY KEY,
            tech_id INTEGER NOT NULL,
            gift_id INTEGER NOT NULL,
            points_spent INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending'
        );
        """)

        con.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        """)

        # ✅ winners (Postgres فقط)
        con.execute("""
        CREATE TABLE IF NOT EXISTS winners (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            points INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        );
        """)

        # setting default
        con.execute("""
        INSERT INTO settings(key,value)
        VALUES(%s,%s)
        ON CONFLICT (key) DO NOTHING
        """, ("iqd_per_point", "10000"))

        con.commit()
        con.close()
        return

    # ===== SQLite (مثل قبل) =====
    cur = con.cursor()
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS admins (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'security'
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
        admin_id INTEGER
    );

    CREATE TABLE IF NOT EXISTS redemptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tech_id INTEGER NOT NULL,
        gift_id INTEGER NOT NULL,
        points_spent INTEGER NOT NULL,
        created_at TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending'
    );

    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );

    -- ✅ winners (SQLite فقط)
    CREATE TABLE IF NOT EXISTS winners (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        points INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL
    );
    """)
    cur.execute("INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)", ("iqd_per_point", "10000"))
    con.commit()
    con.close()


def get_setting(key, default=None):
    con = connect()
    row = con.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    con.close()
    return (row["value"] if row else default)


# ملاحظة: إذا بعدك تستخدم هذني بدوال winners خليهن لاحقاً نكملهن


def get_gift_by_id(gift_id: int):
    con = connect()
    row = con.execute("SELECT * FROM gifts WHERE id=?", (gift_id,)).fetchone()
    con.close()
    return row


def delete_gift(gift_id: int):
    con = connect()
    con.execute("DELETE FROM gifts WHERE id=?", (gift_id,))
    con.commit()
    con.close()


def get_winners(limit: int = 20):
    """
    إذا جدول winners موجود نقرأ منه،
    وإذا ما موجود (أو فارغ) نجيب أعلى الفنيين نقاط.
    """
    con = connect()
    try:
        rows = con.execute("SELECT * FROM winners ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        if rows:
            con.close()
            return rows
    except Exception:
        pass

    # fallback: أعلى نقاط من الفنيين
    rows = con.execute("""
        SELECT name, points
        FROM technicians
        ORDER BY points DESC, id DESC
        LIMIT ?
    """, (limit,)).fetchall()
    con.close()
    return rows
