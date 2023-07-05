from sqlalchemy import JSON, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from typing import Any
from sqlalchemy import String
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
    relationship,
)


SQLITE_DATABASE_URL = "sqlite:///./database.db"

engine = create_engine(
    SQLITE_DATABASE_URL, echo=True, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


class Base(DeclarativeBase):
    type_annotation_map = {dict[str, Any]: JSON}


class Player(Base):
    __tablename__ = "players"
    id: Mapped[int] = mapped_column(primary_key=True)
    pg_id: Mapped[str] = mapped_column(String(20), index=True, unique=True)
    tag: Mapped[str] = mapped_column(String(100))
    profile: Mapped[dict[str, Any]] = mapped_column()
    results: Mapped[dict[str, Any]] = mapped_column()

    def __repr__(self) -> str:
        return f"Player(id={self.id!r}, tag={self.tag!r}, pg_id={self.pg_id!r})"


class SmallPlayer(Base):
    __tablename__ = "small_players"
    id: Mapped[int] = mapped_column(primary_key=True)
    pg_id: Mapped[str] = mapped_column(String(20), index=True, unique=True)
    tag: Mapped[str] = mapped_column(String(100))
    badge_count: Mapped[int] = mapped_column()

    def __repr__(self) -> str:
        return f"SmallPlayer(id={self.id!r}, tag={self.tag!r}, pg_id={self.pg_id!r}, badge_count={self.badge_count!r})"


Base.metadata.create_all(engine)
