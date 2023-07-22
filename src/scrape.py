import csv
from io import StringIO
import requests
from database import r, setj
from main import id_to_url, pg_url_to_id_url


SHEET_ID = "1EQmk2ElCjlC6LiYrmqBcjxpAHL49PTgJRuOwcY1MlPY"
PLAYERS_GID = "0"
COMBINE_GID = "1516543032"
PERIODS_GID = "841098674"
HISTORICALLY_RANKED_GID = "1016791450"


def get_sheet_dl(gid: str) -> str:
    return (
        f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={gid}"
    )


def get_csv(csv_dl) -> list:
    resp = requests.get(csv_dl)
    scsv = resp.text

    f = StringIO(scsv)
    reader = csv.reader(f, delimiter=",")
    rows = []
    for row in reader:
        rows.append(row)
        print("\t".join(row))
    return rows


def get_player_list(include_duplicates: bool = True) -> list:
    dl_link = get_sheet_dl(PLAYERS_GID)
    rows = get_csv(dl_link)
    if not include_duplicates:
        return [row for row in rows[1:] if row[0] != "^"]
    return rows[1:]


def get_and_parse_player(player_id: str) -> None:
    profile_key = f"{player_id}:profile"
    results_key = f"{player_id}:results"
    # if r.exists(profile_key) and r.exists(results_key):
    #     return
    results = fetch_player_results(player_id)
    profile = fetch_player_profile(player_id)

    setj(profile_key, profile)
    setj(results_key, results)


def fetch_player_profile(player_id: str) -> dict:
    data = requests.get(
        f"https://api.pgstats.com/players/profile?playerId={player_id}&game=melee"
    ).json()
    result = data["result"]
    result["num_badges"] = len(result["badges"]["by_events"])
    del result["badges"]
    del result["placings"]
    return result


def fetch_player_results(player_id: str) -> dict:
    js = requests.get(id_to_url(player_id))
    results = js.json()["result"]
    return results


def scrape_all_players():
    for tag, pg_url in get_player_list():
        print(tag)
        get_and_parse_player(pg_url_to_id_url(pg_url)[0])


def get_or_set_player_badge_count(player_id: str) -> int:
    badge_key = f"{player_id}:num_badges"
    in_db = r.get(badge_key)
    if in_db is not None:
        return int(in_db)
    data = requests.get(
        f"https://api.pgstats.com/players/profile?playerId={player_id}&game=melee"
    ).json()
    num_badges = len(data["result"]["badges"]["by_events"])
    r.set(badge_key, num_badges)
    return num_badges


def main():
    scrape_all_players()


if __name__ == "__main__":
    main()
