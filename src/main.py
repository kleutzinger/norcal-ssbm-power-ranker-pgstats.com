"""
todo: what about DQs?
    nmw dq'd against spacepigeon
"""

import csv
import json
import requests
import os
from datetime import datetime
import logging
import shelve

logger = logging.getLogger(__name__)

from collections import Counter, defaultdict

CSV_PATH = os.path.join(os.path.dirname(__file__), "good-players.csv")


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

print(COMBINE_LOOKUP)


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


players = shelve.open("players.db")


def get_or_set_player_badge_count(player_id: str) -> int:
    if player_id + "_badges" in players:
        return players[player_id + "_badges"]
    else:
        data = requests.get(
            f"https://api.pgstats.com/players/profile?playerId={player_id}&game=melee"
        ).json()
        num_badges = len(data["result"]["badges"]["by_events"])
        players[player_id + "_badges"] = num_badges
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


def parse_player(api_url: str, player_id: str) -> dict:
    js = requests.get(api_url)
    results = js.json()["result"]
    for tournament_id, tournament_data in results.items():
        if not is_valid_tournament(tournament_data):
            print("skipping tournament", tournament_data["info"]["tournament_name"])
            continue
        print("reading ", tournament_data["info"]["tournament_name"])
        ID_TO_NUM_TOURNAMENTS[player_id] += 1
        parse_tournament(tournament_data, player_id)
    pass


def parse_tournament(tournament: dict, player_id=None) -> None:
    def rewrite_ids(set_data):
        for key in ["p1_id", "p2_id", "winner_id"]:
            if set_data[key] in COMBINE_LOOKUP:
                set_data[key] = COMBINE_LOOKUP[set_data[key]]
        return set_data

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
        print(f"{ID_TO_NAME[winner_id]} beats {ID_TO_NAME[loser_id]}")
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
    def total_win_loss_tournies(player_id) -> str:
        # get total number of wins for a player
        w = sum(PLAYER_TO_WINS[player_id].values())
        l = sum(PLAYER_TO_LOSSES[player_id].values())
        tot = w + l
        trny = ID_TO_NUM_TOURNAMENTS[player_id]
        return f",{w}-{l} record, {tot} sets, {trny} tournaments, "

    def wins_losses_to_string(player_id, sets) -> str:
        for opponent_id, count in sorted(
            sets.items(), key=lambda x: players[x[0] + "_badges"], reverse=True
        ):
            yield f"{ID_TO_NAME[opponent_id]} ({get_h2h_str(player_id, opponent_id)})"

    with open("wins.csv", "w", newline="") as f:
        for player_id, losses in sorted(
            PLAYER_TO_WINS.items(),
            key=lambda x: players[x[0] + "_badges"],
            reverse=True,
        ):
            f.write(
                ID_TO_NAME[player_id]
                + total_win_loss_tournies(player_id)
                + ","
                + ", ".join(list(wins_losses_to_string(player_id, losses)))
                + "\n"
            )

    with open("losses.csv", "w", newline="") as f:
        for player_id, losses in sorted(
            PLAYER_TO_LOSSES.items(),
            key=lambda x: players[x[0] + "_badges"],
            reverse=True,
        ):
            f.write(
                ID_TO_NAME[player_id]
                + total_win_loss_tournies(player_id)
                + ","
                + ", ".join(reversed(list(wins_losses_to_string(player_id, losses))))
                + "\n"
            )


def main():
    for link in pgstats_links:
        player_name = link[0]
        print("parsing, player_name=", player_name)
        player_id, player_link = pg_url_to_id_url(link[1])
        if player_id in COMBINE_LOOKUP:
            player_id = COMBINE_LOOKUP[player_id]
        parse_player(player_link, player_id)
    show_results()
    write_wins_and_losses_to_csv()
    players.close()


if __name__ == "__main__":
    main()
