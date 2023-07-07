from typing import Dict, List, Optional
from sqlmodel import (
    Field,
    Session,
    SQLModel,
    create_engine,
    select,
)
import datetime


class Player(SQLModel, table=True):
    """
    This table is used to store the full information about a player.
    This player will be considered for the ranking / data visualization.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    pid: str = Field(index=True, unique=True)
    tag: str
    num_top8s: int = Field(default=0)
    badge_count: int = Field(default=0)
    has_been_norcal_pr: bool = Field(default=False)


class Tournament(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    pid: str = Field(index=True, unique=True)
    tournament_name: str
    start_time: datetime.datetime = Field(index=True)
    online: bool
    event_name: str
    num_attendees: int


class MeleeSet(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    pid: str = Field(index=True, unique=True)
    winner_id: int = Field(foreign_key="player.id", index=True)
    loser_id: int = Field(foreign_key="player.id", index=True)
    dq: bool = Field(default=False)
    tournament_id: int = Field(foreign_key="tournament.id")


SQLITE_DATABASE_URL = "sqlite:///./database.db"

engine = create_engine(SQLITE_DATABASE_URL, echo=False)

SQLModel.metadata.create_all(engine)


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


def create_players():
    with Session(engine) as session:
        tournament = Tournament(
            pid="123",
            tournament_name="test",
            start_time=datetime.datetime.now(),
            online=False,
            event_name="test",
            num_attendees=100,
        )
        kev = Player(
            pid="123",
            tag="KEVBOT",
        )

        p2 = Player(
            pid="aaa",
            tag="aaa",
        )
        session.add(kev)
        session.add(p2)
        session.add(tournament)
        session.commit()
        # session.refresh(kev)
        # session.refresh(p2)
        print(session.query(Player).all())
        for w in range(10):
            # win = MeleeSet(pid="123", winner_id=kev.id, loser_id=p2.id)
            # win2 = MeleeSet(pid="123", winner_id=kev.id, loser_id=p2.id)
            session.add(
                MeleeSet(
                    pid=str(w),
                    winner_id=kev.id,
                    loser_id=p2.id,
                    tournament_id=tournament.id,
                    dq=False,
                )
            )
        session.commit()
        session.refresh(kev)
        session.refresh(tournament)
        player = session.get(Player, kev.id)
        for set_, trny, opponent in session.exec(
            select(MeleeSet, Tournament, Player)
            .join(Tournament, Tournament.id == MeleeSet.tournament_id)
            .join(Player, Player.id == MeleeSet.loser_id)
        ).all():
            # print(trny, opponent, set_)
            print(opponent)
        breakpoint()


def main():
    create_db_and_tables()
    create_players()


if __name__ == "__main__":
    main()
