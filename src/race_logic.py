"""Race selection logic: finding current/next race, knockout series status, winner calculation."""

from __future__ import annotations

import math
from datetime import datetime, timezone


def parse_start_time_ms(race: dict) -> int | None:
    """Parse ISO 8601 startTime string to Unix milliseconds, or None."""
    st = race.get("startTime")
    if not st:
        return None
    try:
        dt = datetime.fromisoformat(st.replace("Z", "+00:00"))
        return int(dt.timestamp() * 1000)
    except (ValueError, TypeError):
        return None


def _is_unstarted(race: dict) -> bool:
    """A race is unstarted if not abandoned and status is missing/falsy or 'not_started'."""
    if race.get("abandoned", False):
        return False
    status = race.get("status")
    return not status or status == "not_started"


def race_winner(race: dict) -> str | None:
    """
    Determine winner of a finished race from its result array.
    result is e.g. [1,3,2,4] -- first half teamA positions, second half teamB.
    Lower total wins. Tie-break: team that did NOT get 1st place in any
    individual race wins.
    Returns 'teamA', 'teamB', or None if undetermined.
    """
    result = race.get("result")
    if not result or not isinstance(result, list) or len(result) < 2:
        return None
    mid = len(result) // 2
    team_a_positions = result[:mid]
    team_b_positions = result[mid:]
    sum_a = sum(team_a_positions)
    sum_b = sum(team_b_positions)
    if sum_a < sum_b:
        return "teamA"
    if sum_b < sum_a:
        return "teamB"
    a_has_first = 1 in team_a_positions
    b_has_first = 1 in team_b_positions
    if a_has_first and not b_has_first:
        return "teamB"
    if b_has_first and not a_has_first:
        return "teamA"
    return None


def _match_series_key(race: dict) -> tuple:
    """Grouping key for a knockout series: (stage, matchNumber, frozenset of teams)."""
    teams = frozenset([race.get("teamA", ""), race.get("teamB", "")])
    return (race.get("stage"), race.get("matchNumber"), teams)


def is_series_complete(race: dict, schedule: list[dict]) -> bool:
    """
    For a knockout race, check if its match series is already decided.
    Matches all races with the same (stage, matchNumber, team pairing).
    racesToWin = ceil(totalRacesInSeries / 2).
    """
    if not race.get("isKnockout"):
        return False

    key = _match_series_key(race)
    series_races = [r for r in schedule if r.get("isKnockout") and _match_series_key(r) == key]
    total_in_series = len(series_races)
    if total_in_series == 0:
        return False

    races_to_win = math.ceil(total_in_series / 2)

    wins = {"teamA": 0, "teamB": 0}
    for r in series_races:
        if r.get("result"):
            w = race_winner(r)
            if w:
                wins[w] += 1

    return wins["teamA"] >= races_to_win or wins["teamB"] >= races_to_win


def find_current_race(schedule: list[dict], now_ms: float) -> dict | None:
    """
    Find the first race whose startTime is in the future (countdown active).
    Races are checked in schedule order; first future startTime wins.
    """
    for race in schedule:
        if race.get("abandoned", False):
            continue
        st_ms = parse_start_time_ms(race)
        if st_ms is not None and st_ms > now_ms:
            return race
    return None


def find_next_race(schedule: list[dict], now_ms: float) -> dict | None:
    """
    When no race has an active countdown, find the next race to display as
    "Coming Up".  Priority chain:
      1. If knockouts exist in the schedule, try unstarted knockout races first
         (skip any whose series is already decided).
      2. Fall back to first unstarted regular (non-knockout) race.
      3. If no knockouts exist at all, just take the first unstarted race.
    """
    unstarted = [r for r in schedule if _is_unstarted(r)]

    has_knockouts = any(r.get("isKnockout") for r in schedule)

    if has_knockouts:
        # Try knockout races first
        for race in unstarted:
            if race.get("isKnockout") and not is_series_complete(race, schedule):
                return race
        # Fall back to regular races
        for race in unstarted:
            if not race.get("isKnockout"):
                return race
        return None

    return unstarted[0] if unstarted else None


STAGE_LABELS = {
    "quarter": "Quarter Final",
    "semi": "Semi Final",
    "final": "Final",
    "petit": "Petit Final",
}

LEAGUE_COLORS = {
    "gold": ("#000000", "#FFD700"),       # text, background
    "silver": ("#000000", "#C0C0C0"),
    "bronze": ("#000000", "#CD7F32"),
    "main": ("#FFFFFF", "#2196F3"),
}


def get_race_display_info(race: dict | None) -> dict:
    """Build a display-friendly dict from a race object."""
    if race is None:
        return {"state": "no_races"}

    info = {
        "state": "countdown" if parse_start_time_ms(race) else "coming_up",
        "race_number": race.get("raceNumber", "?"),
        "team_a": race.get("teamA", ""),
        "team_b": race.get("teamB", ""),
        "boat_a": (race.get("boats") or {}).get("teamA", ""),
        "boat_b": (race.get("boats") or {}).get("teamB", ""),
        "start_time_ms": parse_start_time_ms(race),
        "is_knockout": race.get("isKnockout", False),
        "stage": race.get("stage"),
        "match_number": race.get("matchNumber"),
        "league": race.get("league"),
        "round": race.get("round"),
    }

    if info["is_knockout"] and info["stage"]:
        label = STAGE_LABELS.get(info["stage"], info["stage"].title())
        if info["match_number"]:
            label += f" #{info['match_number']}"
        info["stage_label"] = label
    else:
        info["stage_label"] = None

    league = info["league"]
    if league and league in LEAGUE_COLORS:
        text_col, bg_col = LEAGUE_COLORS[league]
        display_name = "Overall" if league == "main" else league.title()
        info["league_pill"] = {"text": display_name, "text_color": text_col, "bg_color": bg_col}
    else:
        info["league_pill"] = None

    return info
