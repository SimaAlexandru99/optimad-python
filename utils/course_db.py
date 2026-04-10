import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional


@dataclass
class CourseSession:
    id: str
    course_date: str
    start_time: str
    end_time: str
    duration_hours: float
    course_name: str
    group_name: str
    trainer: str
    is_recurring: str
    weekdays: str
    platform: str
    meeting_link: str
    created_at: str


@dataclass
class NewCourseSession:
    course_date: str
    start_time: str
    end_time: str
    duration_hours: float
    course_name: str
    group_name: str = ""
    trainer: str = ""
    is_recurring: str = ""
    weekdays: str = ""
    platform: str = ""
    meeting_link: str = ""


class CourseRepository:
    """Thin SQLite repository for imported course sessions."""

    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS course_sessions (
                    id TEXT PRIMARY KEY,
                    course_date TEXT NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT NOT NULL,
                    duration_hours REAL NOT NULL,
                    course_name TEXT NOT NULL,
                    group_name TEXT NOT NULL DEFAULT '',
                    trainer TEXT NOT NULL DEFAULT '',
                    is_recurring TEXT NOT NULL DEFAULT '',
                    weekdays TEXT NOT NULL DEFAULT '',
                    platform TEXT NOT NULL DEFAULT '',
                    meeting_link TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                )
                """
            )
            self._ensure_column(connection, "is_recurring", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(connection, "weekdays", "TEXT NOT NULL DEFAULT ''")

    def list_sessions(self) -> List[CourseSession]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    id,
                    course_date,
                    start_time,
                    end_time,
                    duration_hours,
                    course_name,
                    group_name,
                    trainer,
                    is_recurring,
                    weekdays,
                    platform,
                    meeting_link,
                    created_at
                FROM course_sessions
                ORDER BY course_date ASC, start_time ASC, course_name ASC
                """
            ).fetchall()

        return [CourseSession(*row) for row in rows]

    def replace_all_sessions(self, sessions: Iterable[NewCourseSession]) -> int:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._connect() as connection:
            connection.execute("DELETE FROM course_sessions")
            inserted = 0
            for session in sessions:
                connection.execute(
                    """
                    INSERT INTO course_sessions (
                        id,
                        course_date,
                        start_time,
                        end_time,
                        duration_hours,
                        course_name,
                        group_name,
                        trainer,
                        is_recurring,
                        weekdays,
                        platform,
                        meeting_link,
                        created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid.uuid4()),
                        session.course_date,
                        session.start_time,
                        session.end_time,
                        session.duration_hours,
                        session.course_name,
                        session.group_name,
                        session.trainer,
                        session.is_recurring,
                        session.weekdays,
                        session.platform,
                        session.meeting_link,
                        timestamp,
                    ),
                )
                inserted += 1
        return inserted

    def clear_all_sessions(self) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM course_sessions")

    def delete_session(self, session_id: str) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM course_sessions WHERE id = ?", (session_id,))

    def count_sessions(self) -> int:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) FROM course_sessions"
            ).fetchone()
        return int(row[0]) if row else 0

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _ensure_column(
        self, connection: sqlite3.Connection, column_name: str, column_definition: str
    ) -> None:
        columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(course_sessions)").fetchall()
        }
        if column_name not in columns:
            connection.execute(
                f"ALTER TABLE course_sessions ADD COLUMN {column_name} {column_definition}"
            )
