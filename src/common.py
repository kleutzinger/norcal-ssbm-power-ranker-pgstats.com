"""
"""

from dotenv import load_dotenv
from gspread.utils import rowcol_to_a1

load_dotenv()


def id_to_url(player_id: str) -> str:
    return f"https://api.pgstats.com/players/data?playerId={player_id}&game=melee"


def url_to_id(player_id: str) -> str:
    return player_id.split("?id=")[1]


def xy_to_sheet(row: int, column: int) -> str:
    return rowcol_to_a1(row + 1, column + 1)


if __name__ == "__main__":
    raise NotImplementedError
