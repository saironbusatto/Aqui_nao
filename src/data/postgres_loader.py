from __future__ import annotations

import logging
import os
from typing import Any

from src.models.player import Injury, Player, SeasonStats

logger = logging.getLogger(__name__)

_DATABASE_URL = os.environ.get("DATABASE_URL")


def _get_conn():
    import psycopg2
    return psycopg2.connect(_DATABASE_URL, connect_timeout=5)


def _row_to_player(row: tuple, seasons: list[tuple], injuries: list[tuple]) -> Player:
    _, name, full_name, dob, nationality, position, team, market_value, wc_goals, wc_apps, _ = row
    return Player(
        name=name,
        full_name=full_name or name,
        date_of_birth=str(dob) if dob else "1990-01-01",
        nationality=nationality or "",
        position=position or "",
        current_team=team,
        market_value=market_value,
        world_cup_goals=wc_goals or 0,
        world_cup_appearances=wc_apps or 0,
        career_seasons=tuple(
            SeasonStats(
                season=s[0], team=s[1], age=s[2],
                appearances=s[3], starts=s[4], minutes_played=s[5],
                goals=s[6], assists=s[7], yellow_cards=s[8], red_cards=s[9],
            )
            for s in seasons
        ),
        injuries=tuple(
            Injury(
                season=i[0], injury_type=i[1],
                date_from=str(i[2]) if i[2] else "",
                date_until=str(i[3]) if i[3] else "",
                days_missed=i[4] or 0, games_missed=i[5] or 0,
            )
            for i in injuries
        ),
    )


def load_all_players() -> list[Player] | None:
    if not _DATABASE_URL:
        return None
    try:
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM players ORDER BY id")
            player_rows = cur.fetchall()
            if not player_rows:
                return None

            cur.execute(
                "SELECT player_id, season, team, age, appearances, starts, "
                "minutes_played, goals, assists, yellow_cards, red_cards "
                "FROM season_stats ORDER BY player_id, season"
            )
            all_seasons = cur.fetchall()

            cur.execute(
                "SELECT player_id, season, injury_type, date_from, date_until, "
                "days_missed, games_missed FROM injuries ORDER BY player_id"
            )
            all_injuries = cur.fetchall()

        conn.close()

        seasons_by_player: dict[int, list] = {}
        for row in all_seasons:
            seasons_by_player.setdefault(row[0], []).append(row[1:])

        injuries_by_player: dict[int, list] = {}
        for row in all_injuries:
            injuries_by_player.setdefault(row[0], []).append(row[1:])

        players = []
        for prow in player_rows:
            pid = prow[0]
            players.append(_row_to_player(
                prow,
                seasons_by_player.get(pid, []),
                injuries_by_player.get(pid, []),
            ))

        logger.info("Postgres: %d jogadores carregados", len(players))
        return players

    except Exception as exc:
        logger.warning("Postgres indisponível, usando dados locais: %s", exc)
        return None
