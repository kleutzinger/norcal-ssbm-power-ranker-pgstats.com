from collections import Counter, defaultdict
from datetime import datetime
import time

from pytz import timezone
from copy import deepcopy

from common import hex_to_rgb, url_to_id, xy_to_sheet
from scrape import (
    get_or_set_player_badge_count,
    get_player_tags_urls_list,
    get_duplicate_dict_from_sheet,
    get_banned_tournament_ids,
    get_player_swapper_dict,
)
import gspread
from gspread_formatting import *
from database import getj
from encryption import get_service_account_file_path


from loguru import logger

# These are the sheets that we want to create if they don't exist
DESIRED_SHEETS = ["wins", "losses", "h2h", "meta", "tournaments considered"]

gc = gspread.service_account(filename=get_service_account_file_path())

# color schemes
bad = Color(*hex_to_rgb("#FF8696"))
badbad = Color(*hex_to_rgb("#FF3333"))
good = Color(*hex_to_rgb("#66FFB2"))
goodgood = Color(*hex_to_rgb("#00CC00"))
equal = Color(0.988, 0.91, 0.698)

# TODO: don't hardcode the sheet name value
logger.info("creating sheets if nonexistent")
relevant_doc = gc.open("Current Norcal PR Data")
present_titles = [w.title for w in relevant_doc.worksheets()]
for sheet_name in DESIRED_SHEETS:
    if sheet_name not in present_titles:
        relevant_doc.add_worksheet(title=sheet_name, rows=200, cols=200)
        logger.info(f"created sheet {sheet_name}")
    else:
        logger.info(f"found sheet {sheet_name}")

# Open a sheet from a spreadsheet in one go
wins_sheet = relevant_doc.worksheet("wins")
losses_sheet = relevant_doc.worksheet("losses")
h2h_sheet = relevant_doc.worksheet("h2h")
meta_sheet = relevant_doc.worksheet("meta")
tournaments_considered_sheet = relevant_doc.worksheet("tournaments considered")


CUT_OFF_DATE_START = datetime(2024, 1, 1)
CUT_OFF_DATE_END = datetime(2024, 7, 1)

PLAYER_TO_WINS = defaultdict(Counter)
PLAYER_TO_LOSSES = defaultdict(Counter)
PLAYERS_SETS = defaultdict(set)
P2P_GAME_COUNTS = defaultdict(lambda: [0, 0])
ALL_SETS_EVER = dict()
TOURNAMENT_INFOS = dict()
TOURNAMENT_ATTENDEES_SHEETED = defaultdict(set)
PLAYER_TOURNAMENT_BEST_STANDING = defaultdict(lambda: 999999999)
ID_TO_NAME = {}
ID_TO_NUM_TOURNAMENTS = defaultdict(int)
ID_TO_NUM_TOTAL_SETS = defaultdict(int)
trny_history_strs = defaultdict(list)
UNIQUE_SET_COUNT = 0

BANNED_TOURNAMENT_IDS = get_banned_tournament_ids()
PLAYER_SWAPPER_DICT = get_player_swapper_dict()


def add_tag(player_id: str, tag: str):
    for c in ["(", ")", "-"]:
        tag = tag.replace(c, "_")
    # literal null check (gio)
    if tag == "":
        tag = "_null"
    if player_id not in ID_TO_NAME:
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


def rewrite_ids(set_data: dict) -> dict:
    """
    overwrite or combine player ids due to duplicate accts
    or players entering brackets under someone else's account
    """

    for key in ["p1_id", "p2_id", "winner_id"]:
        if set_data[key] in COMBINE_LOOKUP:
            set_data[key] = COMBINE_LOOKUP[set_data[key]]
        set_data[key] = player_at_tournament_swap(set_data["event_id"], set_data[key])
    return set_data


def player_at_tournament_swap(tournament_id, player_id):
    swaps_at_tournament = PLAYER_SWAPPER_DICT.get(tournament_id, [])
    for swap in swaps_at_tournament:
        if swap[0] == player_id:
            print("SWAPPING", player_id, "TO", swap[1])
            return swap[1]
    return player_id


def parse_tournament(tournament: dict, player_id=None) -> None:
    # collect all wins and losses
    for set_data in tournament["sets"]:
        if player_id in COMBINE_LOOKUP:
            player_id = COMBINE_LOOKUP[player_id]
        set_data = rewrite_ids(deepcopy(set_data))
        add_tag(set_data["p1_id"], set_data["p1_tag"])
        add_tag(set_data["p2_id"], set_data["p2_tag"])
        get_or_set_player_badge_count(set_data["p1_id"])
        get_or_set_player_badge_count(set_data["p2_id"])
        if tournament["info"]["tournament_name"] is not None:
            short_trny = tournament["info"]["tournament_name"][:50]
        else:
            short_trny = "unknown"
        TOURNAMENT_INFOS[tournament["info"]["id"]] = tournament["info"]
        t_id = tournament["info"]["id"]
        winner_id = set_data["winner_id"]
        loser_id = (
            set([set_data["p1_id"], set_data["p2_id"]]) - set([set_data["winner_id"]])
        ).pop()
        if set_data["p1_score"] is None or set_data["p2_score"] is None:
            winner_score, loser_score = "?", "?"
        else:
            winner_score = max(set_data["p1_score"], set_data["p2_score"])
            loser_score = min(set_data["p1_score"], set_data["p2_score"])
        PLAYER_TOURNAMENT_BEST_STANDING[(t_id, set_data["p1_id"])] = min(
            PLAYER_TOURNAMENT_BEST_STANDING[(t_id, set_data["p1_id"])],
            set_data["p1_standing"],
        )
        PLAYER_TOURNAMENT_BEST_STANDING[(t_id, set_data["p2_id"])] = min(
            PLAYER_TOURNAMENT_BEST_STANDING[(t_id, set_data["p2_id"])],
            set_data["p2_standing"],
        )
        logger.debug(f"{ID_TO_NAME[winner_id]} beats {ID_TO_NAME[loser_id]}")
        if set_data["dq"]:
            logger.info(
                f'dq found, skipping {set_data["p1_tag"]} vs {set_data["p2_tag"]}'
            )
            continue
        ID_TO_NUM_TOTAL_SETS[player_id] += 1
        set_identifier = (
            f"{winner_id}-{loser_id}-{tournament['info']['id']}-{set_data['id']}"
        )
        set_seen_before = set_identifier in ALL_SETS_EVER
        ALL_SETS_EVER[set_identifier] = set_data
        if not set_seen_before:
            global UNIQUE_SET_COUNT
            UNIQUE_SET_COUNT += 1
            # add the game counts
            try:
                P2P_GAME_COUNTS[(winner_id, loser_id)][0] += int(winner_score)
                P2P_GAME_COUNTS[(loser_id, winner_id)][1] += int(winner_score)
                P2P_GAME_COUNTS[(winner_id, loser_id)][1] += int(loser_score)
                P2P_GAME_COUNTS[(loser_id, winner_id)][0] += int(loser_score)
            except ValueError:
                logger.error(f"invalid score found: {winner_score}-{loser_score}")
        t_date = datetime.strptime(
            tournament["info"]["start_time"], "%Y-%m-%dT%H:%M:%S"
        )
        ymd = t_date.strftime("%Y-%m-%d")
        days_ago = (datetime.now() - t_date).days

        if winner_id == player_id:
            # player won
            PLAYER_TO_WINS[player_id][loser_id] += 1
            trny_history_strs[(player_id, loser_id)].append(
                f"win {winner_score}-{loser_score} at {short_trny} {ymd} ({days_ago}d) [{t_id}]\n\n"
            )
            PLAYERS_SETS[frozenset((winner_id, loser_id))].add(set_identifier)
            TOURNAMENT_ATTENDEES_SHEETED[t_id].add(winner_id)

        elif loser_id == player_id:
            # player lost
            PLAYER_TO_LOSSES[player_id][winner_id] += 1
            trny_history_strs[(player_id, winner_id)].append(
                f"loss {loser_score}-{winner_score} at {short_trny} {ymd} ({days_ago}d) [{t_id}]\n\n"
            )
            TOURNAMENT_ATTENDEES_SHEETED[t_id].add(loser_id)
        else:
            logger.error("unknown result, no valid winner_id found")
            logger.info(set_data)
    ID_TO_NUM_TOURNAMENTS[player_id] += 1


def clear_and_update_notes(cur_sheet, range_: str, notes_to_add: dict) -> None:
    logger.info(f"updating notes for {range_} on {cur_sheet}")
    if notes_to_add:
        logger.info(f"clearing notes f{range_}")
        try:
            cur_sheet.clear_notes(range_)
        except Exception as e:
            logger.error(e)
        logger.info("updating notes")
        try:
            cur_sheet.update_notes(notes_to_add)
        except Exception as e:
            logger.error(e)


def get_h2h_record_str(player_id, opponent_id) -> str:
    wins = PLAYER_TO_WINS[player_id][opponent_id]
    losses = PLAYER_TO_LOSSES[player_id][opponent_id]
    return f"{wins}-{losses}"


def leftmost_colum_gen(player_id) -> str:
    win_count = sum(PLAYER_TO_WINS[player_id].values())
    loss_count = sum(PLAYER_TO_LOSSES[player_id].values())
    set_count = win_count + loss_count
    trny_count = ID_TO_NUM_TOURNAMENTS[player_id]
    pname = ID_TO_NAME[player_id]
    pstats = f"https://www.pgstats.com/melee/player/{pname}?id={player_id}"
    return f"{pname} ({set_count}s | {trny_count}t)"


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
            yield f"{get_h2h_record_str(player_id, opponent_id)} {ID_TO_NAME[opponent_id]}"

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
        clear_and_update_notes(cur_sheet, f":{top_left}:{bottom_right}", notes_to_add)

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
            win_notes[xy_to_sheet(yidx, xidx + 1)] = get_pvp_note_str(
                player_id, opponent_id
            )
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
            loss_notes[xy_to_sheet(yidx, xidx + 1)] = get_pvp_note_str(
                player_id, opponent_id
            )
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


def get_pvp_note_str(player_id, opponent_id):
    won_games, lost_games = P2P_GAME_COUNTS[(player_id, opponent_id)]
    if won_games == 0 and lost_games == 0:
        return ""
    player_name = ID_TO_NAME[player_id].upper()
    opponent_name = ID_TO_NAME[opponent_id]
    total_sets_between = (PLAYER_TO_WINS[player_id][opponent_id]) + (
        PLAYER_TO_LOSSES[player_id][opponent_id]
    )
    out = f"{player_name} vs {opponent_name} "
    out += f"({get_h2h_record_str(player_id, opponent_id)})"
    out += f"\ngame count: {won_games}-{lost_games} in {total_sets_between} sets\n\n"
    out += f"""{"".join(trny_history_strs[player_id, opponent_id][::-1])}""".strip()
    return out


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
    notes_to_add = {}
    res_array_2d = []
    res_array_2d.append([""] + [ID_TO_NAME[player_id] for player_id in player_list])
    for yidx, main_player in enumerate(player_list):
        row = [ID_TO_NAME[main_player]]
        for xidx, opponent in enumerate(player_list):
            h2h_str = get_h2h_record_str(main_player, opponent)
            if h2h_str == "0-0":
                h2h_str = ""
            row.append(h2h_str)
            notes_to_add[xy_to_sheet(yidx + 1, xidx + 1)] = get_pvp_note_str(
                main_player, opponent
            )
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
    clear_and_update_notes(h2h_sheet, f":{top_left}:{bottom_right}", notes_to_add)


def write_meta_to_sheet():
    # write time to meta sheet
    vals = []
    sa_time = datetime.now(timezone("America/Los_Angeles"))
    updated_time = sa_time.strftime("%Y-%m-%d %I:%M:%S %p")
    update_string = f"last updated {updated_time}"
    vals.append(update_string)
    vals.append(f"total number of players: {len(ID_TO_NAME)}")
    vals.append(f"total sets considered: {UNIQUE_SET_COUNT}")
    meta_sheet.update("A1", [vals])
    logger.info(f"successfully updated sheet at {updated_time}")


def write_tournament_info_to_sheet():
    columns = [
        "start_time",
        "tournament_name",
        "id",
        "event_name",
        "location",
        "total_attendees",
        "sheet_attendees",
    ]
    vals = [columns]
    for trny_info in sorted(TOURNAMENT_INFOS.values(), key=lambda t: t["start_time"], reverse=True):
        tournament_id = trny_info["id"]
        attendees = TOURNAMENT_ATTENDEES_SHEETED[tournament_id]

        def id_to_placing(id_):
            return PLAYER_TOURNAMENT_BEST_STANDING[(tournament_id, id_)]

        attendees_str = ", ".join(
            [
                f"{ID_TO_NAME[x]} {id_to_placing(x)}"
                for x in sorted(attendees, key=id_to_placing)
            ]
        )
        trny_info["sheet_attendees"] = attendees_str
        trny_info["total_attendees"] = trny_info["attendees"]
        loc = trny_info.get("location", {})
        trny_info[
            "location"
        ] = f"{loc.get('city', '')}, {loc.get('state', '')} {loc.get('country', '')}"
        inner_val = []
        for key in columns:
            inner_val.append(trny_info.get(key, ""))
        vals.append(inner_val)
    from pprint import pprint

    pprint(vals)
    tournaments_considered_sheet.update("A1", vals)


def main():
    start = time.time()
    for player_name, player_url in get_player_tags_urls_list():
        logger.debug("parsing, player_name=" + player_name)
        player_id = url_to_id(player_url)
        ID_TO_NAME[player_id] = player_name
        parse_good_player(player_id)
        logger.info("got player " + player_name)

    write_wins_and_losses_to_sheet()
    write_h2h_to_sheet()
    write_tournament_info_to_sheet()
    finish = time.time()
    time_taken_parse = finish - start
    # write time taken to file
    # time_taken_scrape = r.get("time_taken_scrape")

    write_meta_to_sheet()

    # batch add notes
    # https://github.com/burnash/gspread/pull/1189/commits/c192725dfbd2c922134cdd6de3201088acd1dfd6


if __name__ == "__main__":
    main()
