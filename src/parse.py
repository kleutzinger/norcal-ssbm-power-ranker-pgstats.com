from collections import Counter, defaultdict
from datetime import datetime

from pytz import timezone

from common import hex_to_rgb, url_to_id, xy_to_sheet
from scrape import (
    get_or_set_player_badge_count,
    get_player_tags_urls_list,
    get_duplicate_dict_from_sheet,
    get_banned_tournament_ids,
)
import gspread
from gspread_formatting import *
from database import getj
from encryption import get_service_account_file_path


from loguru import logger

# These are the sheets that we want to create if they don't exist
DESIRED_SHEETS = ["wins", "losses", "h2h", "meta"]

gc = gspread.service_account(filename=get_service_account_file_path())

# color schemes
bad = Color(*hex_to_rgb("#FF8696"))
badbad = Color(*hex_to_rgb("#FF3333"))
good = Color(*hex_to_rgb("#66FFB2"))
goodgood = Color(*hex_to_rgb("#00CC00"))
equal = Color(0.988, 0.91, 0.698)

# TODO: don't hardcode the sheet name value
logger.info("creating sheets if nonexistent")
relevant_doc = gc.open("Norcal PR Summer 2023")
present_titles = [w.title for w in relevant_doc.worksheets()]
for sheet_name in DESIRED_SHEETS:
    if sheet_name not in present_titles:
        relevant_doc.add_worksheet(title=sheet_name, rows=100, cols=20)
        logger.info(f"created sheet {sheet_name}")
    else:
        logger.info(f"found sheet {sheet_name}")

# Open a sheet from a spreadsheet in one go
wins_sheet = relevant_doc.worksheet("wins")
losses_sheet = relevant_doc.worksheet("losses")
h2h_sheet = relevant_doc.worksheet("h2h")
meta_sheet = relevant_doc.worksheet("meta")


CUT_OFF_DATE_START = datetime(2023, 5, 8)
CUT_OFF_DATE_END = datetime(2023, 12, 31)

PLAYER_TO_WINS = defaultdict(Counter)
PLAYER_TO_LOSSES = defaultdict(Counter)
ID_TO_NAME = {}
ID_TO_NUM_TOURNAMENTS = defaultdict(int)
ID_TO_NUM_TOTAL_SETS = defaultdict(int)
pvp_results_str = defaultdict(str)

BANNED_TOURNAMENT_IDS = get_banned_tournament_ids()


def add_tag(player_id: str, tag: str):
    for c in ["(", ")", "-"]:
        tag = tag.replace(c, "_")
    # literal null check (gio)
    if tag == "":
        tag = "_null"
    ID_TO_NAME[player_id] = tag


COMBINE_LOOKUP = get_duplicate_dict_from_sheet()


def player_to_player_history(player_id, opponent_id):
    results = getj(f"{player_id}:results")


def is_valid_tournament(
    tournament: dict, CUT_OFF_DATE_START: datetime, CUT_OFF_DATE_END: datetime
) -> bool:
    if tournament["info"]["id"] in BANNED_TOURNAMENT_IDS:
        logger.info(f"banned tournament found, skipping {tournament['info']['id']}")
        return False
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
        if player_id in COMBINE_LOOKUP:
            player_id = COMBINE_LOOKUP[player_id]
        set_data = rewrite_ids(set_data)
        add_tag(set_data["p1_id"], set_data["p1_tag"])
        add_tag(set_data["p2_id"], set_data["p2_tag"])
        get_or_set_player_badge_count(set_data["p1_id"])
        get_or_set_player_badge_count(set_data["p2_id"])
        if tournament["info"]["tournament_name"] is not None:
            short_trny = tournament["info"]["tournament_name"][:50]
        else:
            short_trny = "unknown"
        winner_id = set_data["winner_id"]
        loser_id = (
            set([set_data["p1_id"], set_data["p2_id"]]) - set([set_data["winner_id"]])
        ).pop()
        if set_data["p1_score"] is None or set_data["p2_score"] is None:
            winner_score, loser_score = "?", "?"
        else:
            winner_score = max(set_data["p1_score"], set_data["p2_score"])
            loser_score = min(set_data["p1_score"], set_data["p2_score"])
        logger.debug(f"{ID_TO_NAME[winner_id]} beats {ID_TO_NAME[loser_id]}")
        if set_data["dq"]:
            logger.info(
                f'dq found, skipping {set_data["p1_tag"]} vs {set_data["p2_tag"]}'
            )
            continue
        ID_TO_NUM_TOTAL_SETS[player_id] += 1
        if pvp_results_str[(winner_id, loser_id)] == "":
            pvp_results_str[
                (winner_id, loser_id)
            ] += f"{ID_TO_NAME[winner_id]} vs {ID_TO_NAME[loser_id]}\n"
        if pvp_results_str[(loser_id, winner_id)] == "":
            pvp_results_str[
                (loser_id, winner_id)
            ] += f"{ID_TO_NAME[loser_id]} vs {ID_TO_NAME[winner_id]}\n"

        if winner_id == player_id:
            # player won
            PLAYER_TO_WINS[player_id][loser_id] += 1
            pvp_results_str[
                (player_id, loser_id)
            ] += f"\n\nwin  {winner_score}-{loser_score} at {short_trny} {tournament['info']['start_time'].split('T')[0]} [{tournament['info']['id']}]"
        elif loser_id == player_id:
            # player lost
            PLAYER_TO_LOSSES[player_id][winner_id] += 1
            pvp_results_str[
                (player_id, winner_id)
            ] += f"\n\nloss  {loser_score}-{winner_score} at {short_trny} {tournament['info']['start_time'].split('T')[0]} [{tournament['info']['id']}]"
        else:
            logger.error("unknown result, no valid winner_id found")
            logger.info(set_data)
    ID_TO_NUM_TOURNAMENTS[player_id] += 1


def get_h2h_str(player_id, opponent_id) -> str:
    wins = PLAYER_TO_WINS[player_id][opponent_id]
    losses = PLAYER_TO_LOSSES[player_id][opponent_id]
    return f"{wins}-{losses}"


def leftmost_colum_gen(player_id) -> str:
    win_count = sum(PLAYER_TO_WINS[player_id].values())
    loss_count = sum(PLAYER_TO_LOSSES[player_id].values())
    set_count = win_count + loss_count
    trny_count = ID_TO_NUM_TOURNAMENTS[player_id]
    return f"{ID_TO_NAME[player_id]} ({set_count}),{win_count}-{loss_count} in {trny_count} "


def write_wins_and_losses_to_sheet():
    def sorted_opponent_ids(player_id, sets, rev_good_bad_order=False) -> str:
        for opponent_id, count in sorted(
            sets.items(),
            key=lambda x: get_or_set_player_badge_count(x[0]),
            reverse=not rev_good_bad_order,
        ):
            yield opponent_id

    def wins_losses_to_string(player_id, opponent_ids: list[str]) -> str:
        for opponent_id in opponent_ids:
            yield f"{get_h2h_str(player_id, opponent_id)} {ID_TO_NAME[opponent_id]}"

    def apply_formatting_win_loss(
        cur_sheet, res_array_2d, results_dict, notes_to_add: dict = {}
    ):
        rules = get_conditional_format_rules(cur_sheet)
        # results cells
        set_column_width(cur_sheet, "B:BB", 80)
        # player name on the left
        set_column_width(cur_sheet, "A:A", 200)
        # records are `L-R` i.e. 2-3
        L = 'INDEX(SPLIT(B1, " - "), 1)'
        R = 'INDEX(SPLIT(INDEX(SPLIT(B1, " - "), 2)," "),1)'
        rules.clear()
        formula_colors = [
            (f"=AND({L} < {R}, ({R} - {L} >= 2))", badbad),
            (f"=AND({L} < {R}, ({R} - {L} <  2))", bad),
            (f"=AND({L} > {R}, ({L} - {R} >= 2))", goodgood),
            (f"=AND({L} > {R}, ({L} - {R} <  2))", good),
            (f"={L} = {R}", equal),
        ]
        top_left = "B1"
        bottom_right = xy_to_sheet(
            len(results_dict) - 1, max([len(x) for x in res_array_2d]) - 1
        )
        cur_sheet.format(f"A1:{bottom_right}", {"wrapStrategy": "clip"})
        for formula, color in formula_colors:
            rule = ConditionalFormatRule(
                ranges=[
                    GridRange.from_a1_range(f"{top_left}:{bottom_right}", cur_sheet)
                ],
                booleanRule=BooleanRule(
                    condition=BooleanCondition("CUSTOM_FORMULA", [formula]),
                    format=CellFormat(backgroundColor=color),
                ),
            )
            rules.append(rule)

        cur_sheet.freeze(cols=1)
        rules.save()
        if notes_to_add:
            logger.info(f"clearing notes {top_left}:{bottom_right}")
            try:
                cur_sheet.clear_notes(f"{top_left}:{bottom_right}")
            except Exception as e:
                logger.error(e)
            cur_sheet.update_notes(notes_to_add)

    res_array_2d = []
    # WINS
    win_notes = {}
    for yidx, (player_id, wins) in enumerate(
        sorted(
            PLAYER_TO_WINS.items(),
            key=lambda x: get_or_set_player_badge_count(x[0]),
            reverse=True,
        )
    ):
        opponents = list(sorted_opponent_ids(player_id, wins, False))
        cur = [leftmost_colum_gen(player_id)] + list(
            wins_losses_to_string(player_id, opponents)
        )
        for xidx, opponent_id in enumerate(opponents):
            win_notes[xy_to_sheet(yidx, xidx + 1)] = pvp_results_str[
                (player_id, opponent_id)
            ]
        res_array_2d.append(cur)
    wins_sheet.clear()
    wins_sheet.update("A1", res_array_2d)
    apply_formatting_win_loss(wins_sheet, res_array_2d, PLAYER_TO_WINS, win_notes)

    # LOSSES
    loss_notes = {}
    res_array_2d = []
    for yidx, (player_id, losses) in enumerate(
        sorted(
            PLAYER_TO_LOSSES.items(),
            key=lambda x: get_or_set_player_badge_count(x[0]),
            reverse=True,
        )
    ):
        opponents = list(sorted_opponent_ids(player_id, losses, True))
        cur = [leftmost_colum_gen(player_id)] + list(
            wins_losses_to_string(player_id, opponents)
        )
        for xidx, opponent_id in enumerate(opponents):
            loss_notes[xy_to_sheet(yidx, xidx + 1)] = pvp_results_str[
                (player_id, opponent_id)
            ]
        res_array_2d.append(cur)
    losses_sheet.clear()
    losses_sheet.update("A1", res_array_2d)
    apply_formatting_win_loss(losses_sheet, res_array_2d, PLAYER_TO_LOSSES, loss_notes)


def parse_good_player(player_id: str) -> None:
    player_tournaments = getj(f"{player_id}:results")

    def data_to_start_time(data):
        return datetime.strptime(data["info"]["start_time"], "%Y-%m-%dT%H:%M:%S")

    for tournament_id, tournament_data in sorted(
        player_tournaments.items(), key=lambda x: data_to_start_time(x[1])
    ):
        info = tournament_data["info"]
        if not is_valid_tournament(
            tournament_data, CUT_OFF_DATE_START, CUT_OFF_DATE_END
        ):
            continue
        logger.info(f"adding tournament {info['tournament_name']}")
        parse_tournament(tournament_data, player_id)


def write_h2h_to_sheet():
    player_list = [
        url_to_id(x[1]) for x in get_player_tags_urls_list(include_duplicates=False)
    ]
    player_list = sorted(
        player_list,
        key=get_or_set_player_badge_count,
        reverse=True,
    )
    top_left = "B2"
    bottom_right = xy_to_sheet(len(player_list), len(player_list))
    logger.info(f"clearing notes {top_left}:{bottom_right}")
    h2h_sheet.clear_notes(f"{top_left}:{bottom_right}")
    notes_to_add = {}
    res_array_2d = []
    res_array_2d.append([""] + [ID_TO_NAME[player_id] for player_id in player_list])
    for yidx, main_player in enumerate(player_list):
        row = [ID_TO_NAME[main_player]]
        for xidx, opponent in enumerate(player_list):
            h2h_str = get_h2h_str(main_player, opponent)
            if h2h_str == "0-0":
                h2h_str = ""
            row.append(h2h_str)
            notes_to_add[xy_to_sheet(yidx + 1, xidx + 1)] = pvp_results_str[
                (main_player, opponent)
            ]
        res_array_2d.append(row)
    h2h_sheet.clear()
    h2h_sheet.update("A1", res_array_2d)
    h2h_sheet.freeze(rows=1, cols=1)

    # --- Formatting  ---

    rules = get_conditional_format_rules(h2h_sheet)
    set_column_width(h2h_sheet, "A:BB", 40)
    rules.clear()
    L = 'INDEX(SPLIT(B2, " - "), 1)'
    R = 'INDEX(SPLIT(B2, " - "), 2)'
    formula_colors = [
        (f"=AND({L} < {R}, ({R} - {L} >= 2))", badbad),
        (f"=AND({L} < {R}, ({R} - {L} <  2))", bad),
        (f"=AND({L} > {R}, ({L} - {R} >= 2))", goodgood),
        (f"=AND({L} > {R}, ({L} - {R} <  2))", good),
        (f"={L} = {R}", equal),
    ]
    for formula, color in formula_colors:
        rule = ConditionalFormatRule(
            ranges=[GridRange.from_a1_range(f"{top_left}:{bottom_right}", h2h_sheet)],
            booleanRule=BooleanRule(
                condition=BooleanCondition("CUSTOM_FORMULA", [formula]),
                format=CellFormat(
                    textFormat=textFormat(bold=True), backgroundColor=color
                ),
            ),
        )
        rules.append(rule)
    rules.save()
    h2h_sheet.insert_notes(notes_to_add)


def write_meta_to_sheet():
    # write time to meta sheet
    sa_time = datetime.now(timezone("America/Los_Angeles"))
    updated_time = sa_time.strftime("%Y-%m-%d %I:%M %p")
    update_string = f"last updated {updated_time}"
    meta_sheet.update("A1", [[update_string]])
    logger.info(f"successfully updated sheet at {updated_time}")


def main():
    for player_name, player_url in get_player_tags_urls_list():
        logger.debug("parsing, player_name=" + player_name)
        player_id = url_to_id(player_url)
        ID_TO_NAME[player_id] = player_name
        parse_good_player(player_id)
        logger.info("got player " + player_name)

    write_wins_and_losses_to_sheet()
    write_h2h_to_sheet()
    write_meta_to_sheet()

    # batch add notes
    # https://github.com/burnash/gspread/pull/1189/commits/c192725dfbd2c922134cdd6de3201088acd1dfd6


if __name__ == "__main__":
    main()
