import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

DB_PATH = DATA_DIR / "kyle.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_database():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS trades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        time TEXT,
        side TEXT,
        symbol TEXT,
        qty INTEGER,
        price REAL,
        total REAL,
        realized_pnl REAL,
        strategy TEXT,
        sector TEXT,
        confidence REAL,
        market_bias TEXT,
        outcome TEXT,
        exit_reason TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS portfolio (
        id INTEGER PRIMARY KEY,
        cash REAL,
        equity REAL,
        updated TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS positions (
        symbol TEXT PRIMARY KEY,
        qty INTEGER,
        avg_price REAL
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS execution_queue (
        id INTEGER PRIMARY KEY,
        symbol TEXT,
        status TEXT,
        payload TEXT,
        created TEXT,
        last_updated TEXT
    )
    """)

    columns = [row["name"] for row in cur.execute("PRAGMA table_info(execution_queue)")]

    for name, ddl in {
        "symbol": "ALTER TABLE execution_queue ADD COLUMN symbol TEXT",
        "status": "ALTER TABLE execution_queue ADD COLUMN status TEXT",
        "payload": "ALTER TABLE execution_queue ADD COLUMN payload TEXT",
        "created": "ALTER TABLE execution_queue ADD COLUMN created TEXT",
        "last_updated": "ALTER TABLE execution_queue ADD COLUMN last_updated TEXT",
    }.items():
        if name not in columns:
            cur.execute(ddl)

    conn.commit()
    conn.close()


initialize_database()
