from sqlalchemy import or_
from database import MeleeSet, Session, Player, SmallPlayer, CombinePlayers


def main():
    with Session() as session:
        # players = session.query(Player).with_entities(Player.id, Player.pid).all()
        players = session.query(Player).all()
        kev = players[0]
        print(kev)
        for ss, aa, bb in (
            session.query(MeleeSet, SmallPlayer, SmallPlayer)
            .join(
                SmallPlayer,
                MeleeSet.winner_pid == SmallPlayer.pid,
            )
            .join(SmallPlayer, MeleeSet.loser_pid == SmallPlayer.pid)
            .filter(or_(MeleeSet.winner_pid == kev.pid, MeleeSet.loser_pid == kev.pid))
            .all()
        ):
            breakpoint()
            print(ss, aa, bb)
            exit()


if __name__ == "__main__":
    main()
