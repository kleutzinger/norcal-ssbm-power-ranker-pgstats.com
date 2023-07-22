"""
"""

from dotenv import load_dotenv

load_dotenv()

import csv
import os

from database import setj, getj, r


from loguru import logger


from collections import Counter, defaultdict

CSV_PATH = os.path.join(os.path.dirname(__file__), "good-players.csv")
JSON_DIR = os.path.join(os.path.dirname(__file__), "..", "json")


def pg_url_to_id_url(url: str) -> tuple[str, str]:
    player_id = url.split("?id=")[1]
    return (
        player_id,
        f"https://api.pgstats.com/players/data?playerId={player_id}&game=melee",
    )


def id_to_url(player_id: str) -> str:
    return f"https://api.pgstats.com/players/data?playerId={player_id}&game=melee"


def url_to_id(player_id: str) -> str:
    return player_id.split("?id=")[1]


with open(CSV_PATH) as f:
    f_csv = csv.reader(f)
    headers = next(f_csv)
    pgstats_links = []
    for row in f_csv:
        pgstats_links.append(row)


def refresh_db():
    for file in os.listdir(JSON_DIR):
        if file.endswith(".json"):
            os.remove(os.path.join(JSON_DIR, file))
    init_all_players_in_db()


def all_ids():
    for f in os.listdir(JSON_DIR):
        if f.endswith(".json"):
            yield f.split(".")[0]


def init_all_players_in_db():
    # create db session
    pass


if __name__ == "__main__":
    raise NotImplementedError
