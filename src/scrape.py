import csv
from datetime import timedelta
from io import StringIO
import json
import time
from typing import Optional, DefaultDict
import click
import requests
from loguru import logger
from database import r, setj
from common import id_to_url, url_to_id
from collections import defaultdict


SHEET_ID = "1EQmk2ElCjlC6LiYrmqBcjxpAHL49PTgJRuOwcY1MlPY"
PLAYERS_GID = "0"
INPUT_SHEET_LINK = (
    f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit#gid={PLAYERS_GID}"
)
COMBINE_GID = "1516543032"
PERIODS_GID = "841098674"
HISTORICALLY_RANKED_GID = "1016791450"
BANNED_TOURNAMENTS_GID = "1111402135"
PAST_RANKING_PERIODS_GID = "841098674"
PLAYER_SWAPPER_GID = "1035380690"

JSON_DIR = "jsons"


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


def get_csv(csv_dl, column_limit=None) -> list:
    resp = fetch_url_with_retry(csv_dl)
    scsv = resp.text

    f = StringIO(scsv)
    reader = csv.reader(f, delimiter=",")
    output = []
    # TODO: handle copy_badge_count_from
    for row in reader:
        if column_limit is not None:
            output.append(row[:column_limit])
        else:
            output.append(row)
    return output


def get_player_tags_urls_list(include_duplicates: bool = True, column_limit=2) -> list[tuple]:
    dl_link = get_sheet_dl(PLAYERS_GID)
    rows = get_csv(dl_link, column_limit=column_limit)
    if not include_duplicates:
        return [row for row in rows[1:] if row[0] != "^"]
    return rows[1:]


def get_banned_tournament_ids() -> list[str]:
    dl_link = get_sheet_dl(BANNED_TOURNAMENTS_GID)
    rows = get_csv(dl_link)
    return [row[0] for row in rows[1:]]


def get_duplicate_dict_from_sheet() -> dict:
    duplicate_table = dict()
    rows = get_player_tags_urls_list()
    last_valid_id = ""
    for tag, url in rows[1:]:
        if tag == "^":
            duplicate_table[url_to_id(url)] = last_valid_id
        else:
            last_valid_id = url_to_id(url)
    return duplicate_table


def get_player_swapper_dict() -> DefaultDict[str, list[tuple[str, str]]]:
    """
    {pg_stats_id: {tournament_id: [bracket_player_pgstats, actual_player_pgstats]}
    sometimes players enter brackets under someone else's account
    """
    dl_link = get_sheet_dl(PLAYER_SWAPPER_GID)
    output = defaultdict(list)
    rows = get_csv(dl_link, column_limit=4)
    for row in rows[1:]:
        tournament_id, bracket_player_pgstats, actual_player_pgstats, note = row
        brack_id = url_to_id(bracket_player_pgstats)
        actual_id = url_to_id(actual_player_pgstats)
        output[tournament_id].append([brack_id, actual_id])
    return output


def get_and_parse_player(player_id: str) -> None:
    profile_key = f"{player_id}:profile"
    results_key = f"{player_id}:results"
    results = fetch_player_results(player_id)
    profile = fetch_player_profile(player_id)

    with open(f"{JSON_DIR}/{player_id}_results.json", "w") as f:
        json.dump(results, f, indent=2)
    with open(f"{JSON_DIR}/{player_id}_profile.json", "w") as f:
        json.dump(profile, f, indent=2)

    setj(profile_key, profile)
    setj(results_key, results)


def fetch_player_profile(player_id: str) -> dict:
    data = fetch_url_with_retry(
        f"https://api.pgstats.com/players/profile?playerId={player_id}&game=melee"
    ).json()
    profile = data["result"]
    profile["num_badges"] = len(
        [i for i in profile["badges"]["by_events"] if not i["online"]]
    )

    del profile["badges"]
    del profile["placings"]
    return profile


def fetch_player_results(player_id: str) -> dict:
    data = fetch_url_with_retry(id_to_url(player_id))
    results = data.json()["result"]
    return results


def scrape_all_players(skip_known: bool = False):
    for tag, pg_url in get_player_tags_urls_list():
        player_id = url_to_id(pg_url)
        if skip_known and r.exists(f"{player_id}:results"):
            logger.info(f"skipping {tag}")
            continue
        logger.info(f"scraping {tag}, {pg_url}")
        get_and_parse_player(player_id)


def write_copy_badge_count_from_sheet() -> dict:
    r.delete("copy_badge_count_from")
    id2idmap = dict()
    rows = get_player_tags_urls_list(column_limit=3)
    for tag, url, copy_url in rows[1:]:
        print(f'MAPPING {tag}, {url}, {copy_url}')
        a = url_to_id(url)
        if not copy_url:
            continue
        b = url_to_id(copy_url)
        id2idmap[a] = b
    r.set("copy_badge_count_from", json.dumps(id2idmap), ex=timedelta(days=3))


def improved_hash_to_float(s: str) -> float:
    # lengthen string
    s = s * 10
    # Define a base and a prime modulus
    base = 31
    modulus = 2**64 - 1  # A large prime number close to 64-bit integer max
    # Compute a hash-like integer value based on character codes
    hash_value = 0
    for char in s:
        hash_value = (hash_value * base + ord(char)) % modulus
    # Normalize the hash value to the range [0, 1]
    normalized_value = hash_value / modulus
    return normalized_value

def get_or_set_player_badge_count(player_id: str, copy_dict=None) -> float:
    copy_dict = json.loads(r.get("copy_badge_count_from")) or dict()
    offset = 0
    if copy_dict is not None and player_id in copy_dict:
            offset = improved_hash_to_float(player_id)
            player_id = copy_dict[player_id]
    badge_key = f"{player_id}:num_badges"
    in_db = r.get(badge_key)
    if in_db is not None:
        return float(in_db)
    data = fetch_url_with_retry(
        f"https://api.pgstats.com/players/profile?playerId={player_id}&game=melee"
    ).json()
    num_badges = len(
        [i for i in data["result"]["badges"]["by_events"] if not i["online"]]
    )
    num_badges -= offset
    r.set(badge_key, num_badges, ex=timedelta(days=3))
    return num_badges


@click.command()
@click.option("--skip", is_flag=True, default=False, help="skip players already in db")
def main(skip):
    write_copy_badge_count_from_sheet()
    scrape_all_players(skip_known=skip)


if __name__ == "__main__":
    start = time.time()
    main()
    finish = time.time()
    # write time taken to file
    r.set("time_taken_scrape", finish - start)
