import sqlite3
from contextlib import closing
from pathlib import Path


DATABASE_PATH = Path(__file__).with_name("subscriptions.sqlite3")


def initialize_database() -> None:
    with closing(sqlite3.connect(DATABASE_PATH)) as connection, connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS subscriptions (
                chat_id INTEGER PRIMARY KEY,
                city TEXT NOT NULL,
                subscribed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )


def subscribe(chat_id: int, city: str) -> None:
    with closing(sqlite3.connect(DATABASE_PATH)) as connection, connection:
        connection.execute(
            """
            INSERT INTO subscriptions (chat_id, city)
            VALUES (?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET
                city = excluded.city,
                subscribed_at = CURRENT_TIMESTAMP
            """,
            (chat_id, city),
        )


def unsubscribe(chat_id: int) -> bool:
    with closing(sqlite3.connect(DATABASE_PATH)) as connection, connection:
        cursor = connection.execute(
            "DELETE FROM subscriptions WHERE chat_id = ?",
            (chat_id,),
        )
        return cursor.rowcount > 0


def get_subscriptions() -> list[tuple[int, str]]:
    with closing(sqlite3.connect(DATABASE_PATH)) as connection, connection:
        rows = connection.execute(
            "SELECT chat_id, city FROM subscriptions ORDER BY chat_id"
        ).fetchall()
    return [(int(chat_id), str(city)) for chat_id, city in rows]


def get_subscription(chat_id: int) -> str | None:
    with closing(sqlite3.connect(DATABASE_PATH)) as connection, connection:
        row = connection.execute(
            "SELECT city FROM subscriptions WHERE chat_id = ?",
            (chat_id,),
        ).fetchone()
    return str(row[0]) if row else None
