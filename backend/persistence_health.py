from datetime import datetime

from backend.database import get_connection


REQUIRED_TABLES = [
    "portfolio",
    "positions",
    "trades",
    "execution_queue",
]


REQUIRED_EXECUTION_QUEUE_COLUMNS = [
    "id",
    "symbol",
    "status",
    "payload",
    "created",
    "last_updated",
]


def _table_exists(conn, table_name):
    row = conn.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
        AND name = ?
        """,
        (table_name,),
    ).fetchone()

    return row is not None


def _table_columns(conn, table_name):
    return [
        row["name"]
        for row in conn.execute(f"PRAGMA table_info({table_name})")
    ]


def build_persistence_health():
    generated = datetime.utcnow().isoformat()

    try:
        conn = get_connection()

        tables = {
            table: _table_exists(conn, table)
            for table in REQUIRED_TABLES
        }

        execution_queue_columns = _table_columns(conn, "execution_queue")

        execution_queue_ready = all(
            column in execution_queue_columns
            for column in REQUIRED_EXECUTION_QUEUE_COLUMNS
        )

        queue_count = conn.execute(
            "SELECT COUNT(*) AS count FROM execution_queue"
        ).fetchone()["count"]

        conn.close()

        connected = all(tables.values()) and execution_queue_ready

        return {
            "generated": generated,
            "connected": connected,
            "database": "sqlite",
            "tables": tables,
            "execution_queue_ready": execution_queue_ready,
            "execution_queue_columns": execution_queue_columns,
            "execution_queue_count": int(queue_count),
            "order_persistence_ready": execution_queue_ready,
            "error": None,
        }

    except Exception as error:
        return {
            "generated": generated,
            "connected": False,
            "database": "sqlite",
            "tables": {},
            "execution_queue_ready": False,
            "execution_queue_columns": [],
            "execution_queue_count": 0,
            "order_persistence_ready": False,
            "error": str(error),
        }
