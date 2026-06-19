"""Track which jobs we've already applied to, so we never double-apply."""

from __future__ import annotations

import csv
import datetime as _dt
import os
import sqlite3
from contextlib import closing


class Tracker:
    """SQLite-backed record of applications, with a human-readable CSV mirror."""

    def __init__(self, db_path: str, csv_path: str | None = None) -> None:
        self.db_path = db_path
        self.csv_path = csv_path
        os.makedirs(os.path.dirname(os.path.abspath(db_path)) or ".", exist_ok=True)
        self._conn = sqlite3.connect(db_path)
        self._init_schema()

    def _init_schema(self) -> None:
        with closing(self._conn.cursor()) as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS applications (
                    job_id      TEXT PRIMARY KEY,
                    title       TEXT,
                    company     TEXT,
                    location    TEXT,
                    url         TEXT,
                    status      TEXT,      -- applied | submitted | drafted | skipped | error
                    detail      TEXT,
                    created_at  TEXT
                )
                """
            )
            self._conn.commit()

    def already_seen(self, job_id: str) -> bool:
        with closing(self._conn.cursor()) as cur:
            cur.execute(
                "SELECT 1 FROM applications WHERE job_id = ? LIMIT 1", (job_id,)
            )
            return cur.fetchone() is not None

    def record(
        self,
        *,
        job_id: str,
        title: str,
        company: str,
        location: str,
        url: str,
        status: str,
        detail: str = "",
    ) -> None:
        created = _dt.datetime.now().isoformat(timespec="seconds")
        with closing(self._conn.cursor()) as cur:
            cur.execute(
                """
                INSERT INTO applications
                    (job_id, title, company, location, url, status, detail, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(job_id) DO UPDATE SET
                    status=excluded.status,
                    detail=excluded.detail,
                    created_at=excluded.created_at
                """,
                (job_id, title, company, location, url, status, detail, created),
            )
            self._conn.commit()

        if self.csv_path:
            self._append_csv(
                [job_id, title, company, location, url, status, detail, created]
            )

    def count_status(self, status: str) -> int:
        with closing(self._conn.cursor()) as cur:
            cur.execute(
                "SELECT COUNT(*) FROM applications WHERE status = ?", (status,)
            )
            return int(cur.fetchone()[0])

    def _append_csv(self, row: list[str]) -> None:
        new_file = not os.path.exists(self.csv_path)
        os.makedirs(os.path.dirname(os.path.abspath(self.csv_path)) or ".", exist_ok=True)
        with open(self.csv_path, "a", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            if new_file:
                writer.writerow(
                    ["job_id", "title", "company", "location", "url",
                     "status", "detail", "created_at"]
                )
            writer.writerow(row)

    def close(self) -> None:
        self._conn.close()
