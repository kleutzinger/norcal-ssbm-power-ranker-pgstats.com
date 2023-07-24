"""
"""

from dotenv import load_dotenv

load_dotenv()


def id_to_url(player_id: str) -> str:
    return f"https://api.pgstats.com/players/data?playerId={player_id}&game=melee"


def url_to_id(player_id: str) -> str:
    return player_id.split("?id=")[1]


def xy_to_sheet(row, column):
    if not isinstance(row, int) or not isinstance(column, int):
        raise ValueError("Row and column must be integers.")

    column_number = column + 1

    column_str = ""
    while column_number > 0:
        column_number -= 1
        column_str = chr(column_number % 26 + ord("A")) + column_str
        column_number //= 26

    row_str = str(row + 1)

    return f"{column_str}{row_str}"


if __name__ == "__main__":
    raise NotImplementedError
