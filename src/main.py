"""
todo: what about DQs?
    nmw dq'd against spacepigeon
"""

import csv
import requests
import os
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

from collections import Counter, defaultdict

CSV_PATH = os.path.join(os.path.dirname(__file__), "good-players.csv")
CUT_OFF_DATE_START = datetime(2022, 11, 1)
CUT_OFF_DATE_END = datetime(2023, 5, 7)

PLAYER_TO_WINS = defaultdict(Counter)
PLAYER_TO_LOSSES = defaultdict(Counter)
ID_TO_NAME = {}


with open(CSV_PATH) as f:
    f_csv = csv.reader(f)
    headers = next(f_csv)
    pgstats_links = []
    for row in f_csv:
        pgstats_links.append(row)


def player_id_and_api_url(url: str) -> tuple[str, str]:
    # 'https://api.pgstats.com/players/data?playerId=S155114&game=melee'
    # 'https://www.pgstats.com/melee/player/Kevbot?id=S12293'
    # get player_id
    player_id = url.split("?id=")[1]
    print(player_id)
    return (
        player_id,
        f"https://api.pgstats.com/players/data?playerId={player_id}&game=melee",
    )


def is_valid_tournament(tournament: dict) -> bool:
    if tournament["info"].get("online"):
        return False
    start_time = tournament["info"]["start_time"]
    # parse date
    date = datetime.strptime(start_time, "%Y-%m-%dT%H:%M:%S")
    if date < CUT_OFF_DATE_START or date > CUT_OFF_DATE_END:
        return False
    return True


def parse_player(api_url: str, player_id: str) -> dict:
    js = requests.get(api_url)
    results = js.json()["result"]
    for tournament_id, tournament_data in results.items():
        if not is_valid_tournament(tournament_data):
            print("skipping tournament", tournament_data["info"]["tournament_name"])
            continue
        print("reading ", tournament_data["info"]["tournament_name"])
        parse_tournament(tournament_data, player_id)
    pass


def parse_tournament(tournament: dict, player_id=None) -> dict:
    # collect all wins and losses
    for set_data in tournament["sets"]:
        # data = dict(p1_tag=set_data["p1_tag"], p2_tag=set_data["p2_tag"])
        ID_TO_NAME[set_data["p1_id"]] = set_data["p1_tag"]
        ID_TO_NAME[set_data["p2_id"]] = set_data["p2_tag"]
        winner_id = set_data["winner_id"]
        loser_id = (
            set([set_data["p1_id"], set_data["p2_id"]]) - set([set_data["winner_id"]])
        ).pop()
        print(f"{ID_TO_NAME[winner_id]} beats {ID_TO_NAME[loser_id]}")
        if set_data["dq"]:
            logger.info(
                f'dq found, skipping {set_data["p1_tag"]} vs {set_data["p2_tag"]}'
            )
            continue
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
    def wins_losses_to_string(player_id, sets) -> str:
        for opponent_id, count in sets.items():
            yield f"{ID_TO_NAME[opponent_id]} ({get_h2h_str(player_id, opponent_id)})"

    with open("wins.csv", "w", newline="") as f:
        for player_id, losses in PLAYER_TO_WINS.items():
            f.write(
                ID_TO_NAME[player_id]
                + ","
                + ", ".join(list(wins_losses_to_string(player_id, losses)))
                + "\n"
            )

    with open("losses.csv", "w", newline="") as f:
        for player_id, losses in PLAYER_TO_LOSSES.items():
            f.write(
                ID_TO_NAME[player_id]
                + ","
                + ", ".join(list(wins_losses_to_string(player_id, losses)))
                + "\n"
            )


def main():
    for link in pgstats_links:
        player_name = link[0]
        print("parsing, player_name=", player_name)
        player_id, player_link = player_id_and_api_url(link[1])
        parse_player(player_link, player_id)
    show_results()
    write_wins_and_losses_to_csv()


if __name__ == "__main__":
    main()
