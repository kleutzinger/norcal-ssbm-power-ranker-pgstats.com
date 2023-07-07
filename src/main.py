"""
todo: what about DQs?
    nmw dq'd against spacepigeon
"""

from typing import Optional
from dotenv import load_dotenv

load_dotenv()

import csv
import json
import requests
import os
from datetime import datetime
import shelve
from sqlalchemy.exc import IntegrityError

from database import MeleeSet, Session, Player, SmallPlayer, Tournament


from loguru import logger


from collections import Counter, defaultdict

CSV_PATH = os.path.join(os.path.dirname(__file__), "good-players.csv")
JSON_DIR = os.path.join(os.path.dirname(__file__), "..", "json")


CUT_OFF_DATE_START = datetime(2022, 11, 1)
CUT_OFF_DATE_END = datetime(2023, 5, 7)

PLAYER_TO_WINS = defaultdict(Counter)
PLAYER_TO_LOSSES = defaultdict(Counter)
ID_TO_NAME = {}
ID_TO_NUM_TOURNAMENTS = defaultdict(int)
ID_TO_NUM_TOTAL_SETS = defaultdict(int)


def pg_url_to_id_url(url: str) -> tuple[str, str]:
    player_id = url.split("?id=")[1]
    return (
        player_id,
        f"https://api.pgstats.com/players/data?playerId={player_id}&game=melee",
    )


def id_to_url(player_id: str) -> str:
    return f"https://api.pgstats.com/players/data?playerId={player_id}&game=melee"


COMBINE_JSON = os.path.join(os.path.dirname(__file__), "combine_players.json")
with open(COMBINE_JSON) as f:
    combine_players = json.load(f)

COMBINE_LOOKUP = {}
for player_name, player_ids in combine_players.items():
    for player_id in player_ids:
        # combine duplicate players to the first player_id
        COMBINE_LOOKUP[pg_url_to_id_url(player_id)[0]] = pg_url_to_id_url(
            player_ids[0]
        )[0]


def add_tag(player_id: str, tag: str):
    tag = tag.replace(",", "-")
    if tag == "":
        tag = "_null"
    ID_TO_NAME[player_id] = tag


with open(CSV_PATH) as f:
    f_csv = csv.reader(f)
    headers = next(f_csv)
    pgstats_links = []
    for row in f_csv:
        pgstats_links.append(row)


players_badges = shelve.open("players_badges.db")


def get_or_set_player_badge_count(player_id: str) -> int:
    if player_id in players_badges:
        logger.debug(player_id, "in badge cache")
        return players_badges[player_id]
    else:
        data = requests.get(
            f"https://api.pgstats.com/players/profile?playerId={player_id}&game=melee"
        ).json()
        num_badges = len(data["result"]["badges"]["by_events"])
        players_badges[player_id] = num_badges
        return num_badges


def is_valid_tournament(tournament: dict) -> bool:
    if tournament["info"].get("online"):
        return False
    start_time = tournament["info"]["start_time"]
    # parse date
    date = datetime.strptime(start_time, "%Y-%m-%dT%H:%M:%S")
    if date < CUT_OFF_DATE_START or date > CUT_OFF_DATE_END:
        return False
    return True


def get_player_profile(player_id: str) -> dict:
    data = requests.get(
        f"https://api.pgstats.com/players/profile?playerId={player_id}&game=melee"
    ).json()
    result = data["result"]
    result["num_badges"] = len(result["badges"]["by_events"])
    del result["badges"]
    del result["placings"]
    return result


def get_player_results(player_id: str) -> dict:
    js = requests.get(id_to_url(player_id))
    results = js.json()["result"]
    return results


def refresh_db():
    for file in os.listdir(JSON_DIR):
        if file.endswith(".json"):
            os.remove(os.path.join(JSON_DIR, file))
    # for key in players_badges:
    #     del players_badges[key]
    init_all_players_in_db()


def rewrite_ids(set_data):
    for key in ["p1_id", "p2_id", "winner_id"]:
        if set_data[key] in COMBINE_LOOKUP:
            set_data[key] = COMBINE_LOOKUP[set_data[key]]
    return set_data


def add_small_player(player_id: str, profile: Optional[dict] = None):
    with Session() as session:
        # check if player already exists
        if session.query(
            session.query(SmallPlayer).filter_by(pid=player_id).exists()
        ).scalar():
            return
        if not profile:
            profile = get_player_profile(player_id)
        session.add(
            SmallPlayer(
                pid=player_id,
                tag=profile["tag"],
                badge_count=profile["num_badges"],
                num_top8s=profile["top_8s"] or 0,
                has_been_norcal_pr=None,
            )
        )
        session.commit()
        logger.info(f"added {profile['tag']} {player_id}")


def get_and_parse_player(api_url: str, player_id: str) -> None:
    results = get_player_results(player_id)
    profile = get_player_profile(player_id)

    add_small_player(player_id, profile)

    with Session() as session:
        player = Player(
            pid=player_id,
            tag=profile["tag"],
            profile=profile,
        )
    try:
        session.add(player)
        session.commit()
    except IntegrityError:
        session.rollback()

    for tournament_id, tournament_data in results.items():
        info = tournament_data["info"]
        with Session() as session:
            if session.query(
                session.query(Tournament).filter_by(pid=tournament_id).exists()
            ).scalar():
                pass
            else:
                logger.info(f"adding tournament {info['tournament_name']}")
                start_time = datetime.strptime(info["start_time"], "%Y-%m-%dT%H:%M:%S")
                session.add(
                    Tournament(
                        pid=tournament_id,
                        tournament_name=info["tournament_name"],
                        start_time=start_time,
                        online=info["online"],
                        event_name=info["event_name"],
                        num_attendees=info["attendees"],
                    )
                )
                session.commit()

        sets = tournament_data["sets"]
        for set_data in sets:
            set_id = set_data["id"]
            set_data = rewrite_ids(set_data)
            loser_id = (
                set([set_data["p1_id"], set_data["p2_id"]])
                - set([set_data["winner_id"]])
            ).pop()
            if set_data["winner_id"] != player_id:
                add_small_player(set_data["winner_id"])
            if loser_id != player_id:
                add_small_player(loser_id)
            with Session() as session:
                if session.query(
                    session.query(MeleeSet).filter_by(pid=set_id).exists()
                ).scalar():
                    pass
                    # logger.error("set EXISTS!, skipping " + set_id)
                else:
                    start_time = datetime.strptime(
                        info["start_time"], "%Y-%m-%dT%H:%M:%S"
                    )
                    session.add(
                        MeleeSet(
                            pid=set_id,
                            dq=bool(set_data["dq"]),
                            winner_pid=set_data["winner_id"],
                            loser_pid=loser_id,
                            tournament_pid=tournament_id,
                            start_time=start_time,
                        )
                    )
                    session.commit()

    # for tournament_id, tournament_data in results.items():
    #     if not is_valid_tournament(tournament_data):
    #         logger.debug(
    #             "skipping tournament" + tournament_data["info"]["tournament_name"]
    #         )
    #         continue
    #     logger.debug("reading " + tournament_data["info"]["tournament_name"])
    #     ID_TO_NUM_TOURNAMENTS[player_id] += 1
    #     parse_tournament(tournament_data, player_id)


def all_ids():
    for f in os.listdir(JSON_DIR):
        if f.endswith(".json"):
            yield f.split(".")[0]


def parse_tournament(tournament: dict, player_id=None) -> None:
    # collect all wins and losses
    for set_data in tournament["sets"]:
        # data = dict(p1_tag=set_data["p1_tag"], p2_tag=set_data["p2_tag"])
        if player_id in COMBINE_LOOKUP:
            player_id = COMBINE_LOOKUP[player_id]
        set_data = rewrite_ids(set_data)
        add_tag(set_data["p1_id"], set_data["p1_tag"])
        add_tag(set_data["p2_id"], set_data["p2_tag"])
        get_or_set_player_badge_count(set_data["p1_id"])
        get_or_set_player_badge_count(set_data["p2_id"])
        winner_id = set_data["winner_id"]
        loser_id = (
            set([set_data["p1_id"], set_data["p2_id"]]) - set([set_data["winner_id"]])
        ).pop()
        logger.debug(f"{ID_TO_NAME[winner_id]} beats {ID_TO_NAME[loser_id]}")
        if set_data["dq"]:
            logger.info(
                f'dq found, skipping {set_data["p1_tag"]} vs {set_data["p2_tag"]}'
            )
            continue
        ID_TO_NUM_TOTAL_SETS[player_id] += 1
        if winner_id == player_id:
            # player won
            PLAYER_TO_WINS[player_id][loser_id] += 1
        elif loser_id == player_id:
            # player lost
            PLAYER_TO_LOSSES[player_id][winner_id] += 1
        else:
            logger.error("unknown result, no valid winner_id found")
            logger.info(set_data)


def show_results():
    for player_id, wins in PLAYER_TO_WINS.items():
        for win, count in wins.items():
            print(ID_TO_NAME[win], count, end=",")
    # losses:
    for player_id, losses in PLAYER_TO_LOSSES.items():
        for loss, count in losses.items():
            print(ID_TO_NAME[loss], count, end=",")


def get_h2h_str(player_id, opponent_id) -> str:
    wins = PLAYER_TO_WINS[player_id][opponent_id]
    losses = PLAYER_TO_LOSSES[player_id][opponent_id]
    return f"{wins}-{losses}"


def write_wins_and_losses_to_csv():
    def leftmost_colum_gen(player_id) -> str:
        # get total number of wins for a player
        w = sum(PLAYER_TO_WINS[player_id].values())
        l = sum(PLAYER_TO_LOSSES[player_id].values())
        tot = w + l
        trny = ID_TO_NUM_TOURNAMENTS[player_id]
        return f"{ID_TO_NAME[player_id]} ({tot}),{w}-{l} in {trny} "

    def wins_losses_to_string(player_id, sets) -> str:
        for opponent_id, count in sorted(
            sets.items(),
            key=lambda x: players_badges[x[0]],
            reverse=True,
        ):
            yield f"{ID_TO_NAME[opponent_id]} ({get_h2h_str(player_id, opponent_id)})"

    with open("wins.csv", "w", newline="") as f:
        for player_id, losses in sorted(
            PLAYER_TO_WINS.items(),
            key=lambda x: players_badges[x[0]],
            reverse=True,
        ):
            f.write(
                leftmost_colum_gen(player_id)
                + ","
                + ", ".join(list(wins_losses_to_string(player_id, losses)))
                + "\n"
            )

    with open("losses.csv", "w", newline="") as f:
        for player_id, losses in sorted(
            PLAYER_TO_LOSSES.items(),
            key=lambda x: players_badges[x[0]],
            reverse=True,
        ):
            f.write(
                leftmost_colum_gen(player_id)
                + ","
                + ", ".join(reversed(list(wins_losses_to_string(player_id, losses))))
                + "\n"
            )


def init_all_players_in_db():
    # create db session

    for link in pgstats_links:
        player_name = link[0]
        logger.debug("parsing, player_name=" + player_name)
        player_id, player_link = pg_url_to_id_url(link[1])
        if player_id in COMBINE_LOOKUP:
            player_id = COMBINE_LOOKUP[player_id]
        get_and_parse_player(player_link, player_id)
        logger.info("got player " + player_name)
    show_results()
    write_wins_and_losses_to_csv()
    # badge_db.close()


if __name__ == "__main__":
    init_all_players_in_db()
