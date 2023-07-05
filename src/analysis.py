from database import Session, Player, SmallPlayer, CombinePlayers


def main():
    with Session() as session:
        # players = session.query(Player).with_entities(Player.id, Player.pg_id).all()
        players = session.query(Player).all()
        print(players)


if __name__ == "__main__":
    main()
