import csv
from datetime import timedelta
from io import StringIO
import time
from typing import Optional
import click
import requests
from loguru import logger
from database import r, setj
from common import id_to_url, url_to_id


SHEET_ID = "1EQmk2ElCjlC6LiYrmqBcjxpAHL49PTgJRuOwcY1MlPY"
PLAYERS_GID = "0"
COMBINE_GID = "1516543032"
PERIODS_GID = "841098674"
HISTORICALLY_RANKED_GID = "1016791450"


def get_sheet_dl(gid: str) -> str:
    return (
        f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={gid}"
    )


def fetch_url_with_retry(
    url,
    max_retries=5,
    request_timeout=10,
    retry_timeout=3,
) -> Optional[requests.Response]:
    """
    Fetch the content of a URL using the requests library with retry.

    Parameters:
        url (str): The URL to fetch the content from.
        max_retries (int, optional): The maximum number of retry attempts. Default is 5.
        request_timeout (int, optional): The timeout for the request in seconds. Default is 10.
        retry_timeout (int, optional): The timeout in seconds between retry attempts. Default is 3.

    Returns:
        str: The content of the URL if successfully fetched, or None if all retry attempts failed.
    """
    for retry in range(max_retries + 1):
        try:
            response = requests.get(url, timeout=request_timeout)
            response.raise_for_status()  # Raise an exception for non-200 status codes
            return response
        except (requests.RequestException, requests.HTTPError, requests.Timeout) as e:
            logger.info(f"Attempt {retry + 1}/{max_retries + 1} failed. Error: {e}")
            if retry < max_retries:
                logger.info(f"Retrying in {retry_timeout} seconds...")
                time.sleep(retry_timeout)

    return None  # Return None if all retry attempts fail


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


def get_duplicate_dict_from_sheet() -> dict:
    duplicate_table = dict()
    rows = get_player_list()
    last_valid_id = ""
    for tag, url in rows[1:]:
        if tag == "^":
            duplicate_table[url_to_id(url)] = last_valid_id
        else:
            last_valid_id = url_to_id(url)
    return duplicate_table


def get_and_parse_player(player_id: str) -> None:
    profile_key = f"{player_id}:profile"
    results_key = f"{player_id}:results"
    results = fetch_player_results(player_id)
    profile = fetch_player_profile(player_id)

    setj(profile_key, profile)
    setj(results_key, results)


def fetch_player_profile(player_id: str) -> dict:
    data = fetch_url_with_retry(
        f"https://api.pgstats.com/players/profile?playerId={player_id}&game=melee"
    ).json()
    profile = data["result"]
    profile["num_badges"] = len(profile["badges"]["by_events"])
    del profile["badges"]
    del profile["placings"]
    return profile


def fetch_player_results(player_id: str) -> dict:
    data = fetch_url_with_retry(id_to_url(player_id))
    results = data.json()["result"]
    return results


def scrape_all_players(skip_known: bool = False):
    for tag, pg_url in get_player_list():
        player_id = url_to_id(pg_url)
        if skip_known and r.exists(f"{player_id}:results"):
            logger.info(f"skipping {tag}")
            continue
        logger.info(f"scraping {tag}, {pg_url}")
        get_and_parse_player(player_id)


def get_or_set_player_badge_count(player_id: str) -> int:
    badge_key = f"{player_id}:num_badges"
    in_db = r.get(badge_key)
    if in_db is not None:
        return int(in_db)
    data = fetch_url_with_retry(
        f"https://api.pgstats.com/players/profile?playerId={player_id}&game=melee"
    ).json()
    num_badges = len(data["result"]["badges"]["by_events"])
    r.set(badge_key, num_badges, ex=timedelta(weeks=4))
    return num_badges


@click.command()
@click.option("--skip", is_flag=True, default=False, help="skip players already in db")
def main(skip):
    scrape_all_players(skip_known=skip)
    """Simple program that greets NAME for a total of COUNT times."""


if __name__ == "__main__":
    main()
