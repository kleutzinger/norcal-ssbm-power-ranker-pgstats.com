import datetime
from sqlalchemy import JSON, Date, DateTime, create_engine
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
    SQLITE_DATABASE_URL, echo=False, connect_args={"check_same_thread": False}
)
Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


class Base(DeclarativeBase):
    type_annotation_map = {dict[str, Any]: JSON}


class Player(Base):
    """
    This table is used to store the full information about a player.
    This player will be considered for the ranking / data visualization.
    """

    __tablename__ = "players"
    id: Mapped[int] = mapped_column(primary_key=True)
    pg_id: Mapped[str] = mapped_column(String(20), index=True, unique=True)
    tag: Mapped[str] = mapped_column(String(100))
    profile: Mapped[dict[str, Any]] = mapped_column()
    results: Mapped[dict[str, Any]] = mapped_column()

    def __repr__(self) -> str:
        return f"Player(id={self.id!r}, tag={self.tag!r}, pg_id={self.pg_id!r})"


class SmallPlayer(Base):
    """
    This table is used to store the bare minimum information about a player.
    This collects data from the field of players who may or many not be ranked.
    """

    __tablename__ = "small_players"
    id: Mapped[int] = mapped_column(primary_key=True)
    pg_id: Mapped[str] = mapped_column(String(20), index=True, unique=True)
    tag: Mapped[str] = mapped_column(String(100))
    badge_count: Mapped[int] = mapped_column()
    has_been_norcal_pr: Mapped[bool | None] = mapped_column()

    def __repr__(self) -> str:
        return f"SmallPlayer(id={self.id!r}, tag={self.tag!r}, pg_id={self.pg_id!r}, badge_count={self.badge_count!r})"


class CombinePlayers(Base):
    """
    This table is used to combine players that are the same person.
    """

    __tablename__ = "combine_players"
    id: Mapped[int] = mapped_column(primary_key=True)
    parent_pg_id: Mapped[str] = mapped_column(String(20))
    child_pg_id: Mapped[str] = mapped_column(String(20), index=True, unique=True)

    def __repr__(self) -> str:
        return f"CombinePlayers(id={self.id!r}, parent_id={self.parent_id!r}, child_id={self.child_id!r})"


class MeleeSet(Base):
    __tablename__ = "melee_sets"

    id: Mapped[int] = mapped_column(primary_key=True)
    pg_id: Mapped[str] = mapped_column(String(20), unique=True)
    dq: Mapped[bool] = mapped_column()
    p1_pg_id: Mapped[str] = mapped_column(String(20), index=True)
    p2_pg_id: Mapped[str] = mapped_column(String(20), index=True)
    winner_id: Mapped[str] = mapped_column(String(20))
    tournament_pg_id: Mapped[str] = mapped_column(String(20), index=True)
    start_time: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True))


class Tournament(Base):
    __tablename__ = "tournaments"

    id: Mapped[int] = mapped_column(primary_key=True)
    pg_id: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    tournament_name: Mapped[str] = mapped_column(String(200))
    start_time: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True))
    online: Mapped[bool] = mapped_column()
    event_name: Mapped[str] = mapped_column(String(200))
    num_attendees: Mapped[int] = mapped_column()


Base.metadata.create_all(engine)
