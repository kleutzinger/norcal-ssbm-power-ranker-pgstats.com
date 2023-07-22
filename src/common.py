"""
"""

from dotenv import load_dotenv

load_dotenv()


def id_to_url(player_id: str) -> str:
    return f"https://api.pgstats.com/players/data?playerId={player_id}&game=melee"


def url_to_id(player_id: str) -> str:
    return player_id.split("?id=")[1]


if __name__ == "__main__":
    raise NotImplementedError
