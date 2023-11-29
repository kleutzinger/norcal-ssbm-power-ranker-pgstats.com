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


def hex_to_rgb(hex_color: str) -> tuple[float, ...]:
    # example: #FF0000 -> (1.0, 0.0, 0.0)
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i : i + 2], 16) / 255 for i in (0, 2, 4))


if __name__ == "__main__":
    raise NotImplementedError
