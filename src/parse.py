from collections import Counter, defaultdict
from datetime import datetime

from common import url_to_id
from scrape import (
    get_or_set_player_badge_count,
    get_player_list,
    get_duplicate_dict_from_sheet,
)
import gspread
from database import getj
from encryption import get_service_account_file_path

from loguru import logger

gc = gspread.service_account(filename=get_service_account_file_path())

logger.info("creating sheets if nonexistent")
for sheet_name in ["wins", "losses", "h2h"]:
    try:
        gc.open("test-gspread").add_worksheet(title=sheet_name, rows=100, cols=20)
        logger.info(f"created sheet {sheet_name}")
    except gspread.exceptions.APIError:
        pass

# Open a sheet from a spreadsheet in one go
wins_sheet = gc.open("test-gspread").worksheet("wins")
losses_sheet = gc.open("test-gspread").worksheet("losses")
h2h_sheet = gc.open("test-gspread").worksheet("h2h")


CUT_OFF_DATE_START = datetime(2023, 5, 8)
CUT_OFF_DATE_END = datetime(2023, 12, 31)

PLAYER_TO_WINS = defaultdict(Counter)
PLAYER_TO_LOSSES = defaultdict(Counter)
ID_TO_NAME = {}
ID_TO_NUM_TOURNAMENTS = defaultdict(int)
ID_TO_NUM_TOTAL_SETS = defaultdict(int)


def add_tag(player_id: str, tag: str):
    tag = tag.replace(",", "-")
    if tag == "":
        tag = "_null"
    ID_TO_NAME[player_id] = tag


COMBINE_LOOKUP = get_duplicate_dict_from_sheet()


def is_valid_tournament(
    tournament: dict, CUT_OFF_DATE_START: datetime, CUT_OFF_DATE_END: datetime
) -> bool:
    if tournament["info"].get("online"):
        return False
    start_time = tournament["info"]["start_time"]
    # parse date
    date = datetime.strptime(start_time, "%Y-%m-%dT%H:%M:%S")
    if date < CUT_OFF_DATE_START or date > CUT_OFF_DATE_END:
        return False
    return True


def rewrite_ids(set_data):
    for key in ["p1_id", "p2_id", "winner_id"]:
        if set_data[key] in COMBINE_LOOKUP:
            set_data[key] = COMBINE_LOOKUP[set_data[key]]
    return set_data


def parse_tournament(tournament: dict, player_id=None) -> None:
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
        logger.debug(f"{ID_TO_NAME[winner_id]} beats {ID_TO_NAME[loser_id]}")
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


def write_wins_and_losses_to_sheet():
    def leftmost_colum_gen(player_id) -> str:
        # get total number of wins for a player
        w = sum(PLAYER_TO_WINS[player_id].values())
        l = sum(PLAYER_TO_LOSSES[player_id].values())
        tot = w + l
        trny = ID_TO_NUM_TOURNAMENTS[player_id]
        return f"{ID_TO_NAME[player_id]} ({tot}),{w}-{l} in {trny} "

    def wins_losses_to_string(player_id, sets) -> str:
        for opponent_id, count in sorted(
            sets.items(),
            key=lambda x: get_or_set_player_badge_count(x[0]),
            reverse=True,
        ):
            yield f"{ID_TO_NAME[opponent_id]} ({get_h2h_str(player_id, opponent_id)})"

    res_array_2d = []
    # WINS
    for player_id, wins in sorted(
        PLAYER_TO_WINS.items(),
        key=lambda x: get_or_set_player_badge_count(x[0]),
        reverse=True,
    ):
        cur = [leftmost_colum_gen(player_id)] + list(
            wins_losses_to_string(player_id, wins)
        )
        res_array_2d.append(cur)
    wins_sheet.clear()
    wins_sheet.update("A1", res_array_2d)

    # LOSSES
    res_array_2d = []
    for player_id, losses in sorted(
        PLAYER_TO_LOSSES.items(),
        key=lambda x: get_or_set_player_badge_count(x[0]),
        reverse=True,
    ):
        cur = [leftmost_colum_gen(player_id)] + list(
            wins_losses_to_string(player_id, losses)
        )
        res_array_2d.append(cur)
    losses_sheet.clear()
    losses_sheet.update("A1", res_array_2d)


def parse_good_player(player_id: str) -> None:
    player_tournaments = getj(f"{player_id}:results")
    for tournament_id, tournament_data in player_tournaments.items():
        info = tournament_data["info"]
        if not is_valid_tournament(
            tournament_data, CUT_OFF_DATE_START, CUT_OFF_DATE_END
        ):
            logger.debug(
                "skipping tournament" + tournament_data["info"]["tournament_name"]
            )
            continue
        logger.info(f"adding tournament {info['tournament_name']}")

        ID_TO_NUM_TOURNAMENTS[player_id] += 1
        start_time = datetime.strptime(info["start_time"], "%Y-%m-%dT%H:%M:%S")
        parse_tournament(tournament_data, player_id)


def main():
    for player_name, player_url in get_player_list():
        logger.debug("parsing, player_name=" + player_name)
        player_id = url_to_id(player_url)
        if player_id in COMBINE_LOOKUP:
            player_id = COMBINE_LOOKUP[player_id]
        parse_good_player(player_id)
        logger.info("got player " + player_name)
    show_results()
    write_wins_and_losses_to_sheet()
    # badge_db.close()


if __name__ == "__main__":
    main()
