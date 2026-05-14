"""Tiny SQLite-backed dedupe + history store.

We never want to publish the same source clip twice within
`dedupe_window_days`. We also keep a record of every published Short so
we can audit copyright-safety scores after the fact.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    create_engine,
    select,
)
from sqlalchemy.orm import DeclarativeBase, Session


class Base(DeclarativeBase):
    pass


class PublishedShort(Base):
    __tablename__ = "published_shorts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_video_id = Column(String(32), index=True, nullable=False)
    source_url = Column(Text, nullable=False)
    youtube_video_id = Column(String(32), nullable=True)
    title = Column(Text, nullable=False)
    niche = Column(String(64), nullable=True)
    region = Column(String(8), nullable=True)
    language = Column(String(8), nullable=True)
    copyright_score = Column(Float, nullable=True)
    viral_score = Column(Float, nullable=True)
    scheduled_for = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Database:
    def __init__(self, db_path: str):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(f"sqlite:///{db_path}", future=True)
        Base.metadata.create_all(self.engine)

    def already_published(self, source_video_id: str, window_days: int) -> bool:
        cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
        with Session(self.engine) as s:
            stmt = (
                select(PublishedShort)
                .where(PublishedShort.source_video_id == source_video_id)
                .where(PublishedShort.created_at >= cutoff)
                .limit(1)
            )
            return s.execute(stmt).first() is not None

    def record(self, **fields) -> int:
        with Session(self.engine) as s:
            row = PublishedShort(**fields)
            s.add(row)
            s.commit()
            return row.id

    def update_youtube_id(self, row_id: int, youtube_video_id: str) -> None:
        with Session(self.engine) as s:
            row = s.get(PublishedShort, row_id)
            if row:
                row.youtube_video_id = youtube_video_id
                s.commit()
