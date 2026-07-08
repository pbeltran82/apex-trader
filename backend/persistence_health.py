from datetime import datetime

from backend.database import get_connection


REQUIRED_TABLES = [
    "portfolio",
    "positions",
    "trades",
    "execution_queue",
    "burn_in_state",
]


REQUIRED_EXECUTION_QUEUE_COLUMNS = [
    "id",
    "symbol",
    "status",
    "payload",
    "created",
    "last_updated",
]


REQUIRED_BURN_IN_COLUMNS = [
    "id",
    "payload",
    "updated",
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


def _count_rows(conn, table_name):
    if not _table_exists(conn, table_name):
        return 0

    return int(
        conn.execute(
            f"SELECT COUNT(*) AS count FROM {table_name}"
        ).fetchone()["count"]
    )


def build_persistence_health():
    generated = datetime.utcnow().isoformat()

    try:
        conn = get_connection()

        tables = {
            table: _table_exists(conn, table)
            for table in REQUIRED_TABLES
        }

        execution_queue_columns = _table_columns(conn, "execution_queue")
        burn_in_columns = _table_columns(conn, "burn_in_state")

        execution_queue_ready = all(
            column in execution_queue_columns
            for column in REQUIRED_EXECUTION_QUEUE_COLUMNS
        )

        burn_in_ready = all(
            column in burn_in_columns
            for column in REQUIRED_BURN_IN_COLUMNS
        )

        queue_count = _count_rows(conn, "execution_queue")
        burn_in_state_count = _count_rows(conn, "burn_in_state")

        conn.close()

        connected = (
            all(tables.values())
            and execution_queue_ready
            and burn_in_ready
        )

        return {
            "generated": generated,
            "connected": connected,
            "database": "sqlite",
            "tables": tables,
            "execution_queue_ready": execution_queue_ready,
            "execution_queue_columns": execution_queue_columns,
            "execution_queue_count": queue_count,
            "order_persistence_ready": execution_queue_ready,
            "burn_in_ready": burn_in_ready,
            "burn_in_columns": burn_in_columns,
            "burn_in_state_count": burn_in_state_count,
            "burn_in_persistence_ready": burn_in_ready,
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
            "burn_in_ready": False,
            "burn_in_columns": [],
            "burn_in_state_count": 0,
            "burn_in_persistence_ready": False,
            "error": str(error),
        }
