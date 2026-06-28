#!/usr/bin/env python3
"""
Seeder de jogadores aposentados: FBref → Transfermarkt → Postgres.

1. Usa soccerdata (FBref) para achar lendas históricas dos top campeonatos
2. Pula quem já está no DB (por nome)
3. Busca o perfil no Transfermarkt via search + scrape completo
4. Marca is_retired=True, refresh em 36.500 dias (seed único)

Cron sugerido: domingo 05:00
  0 5 * * 0  cd /home/ubuntu/aqui-nao && DATABASE_URL=... python3 scripts/seeder_retired.py >> /var/log/aquinao/seeder_retired.log 2>&1
"""
from __future__ import annotations

import json
import logging
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg2
import psycopg2.extras
import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.collectors.transfermarkt_scraper import search_player_url
from scripts.seeder import (
    _get_conn,
    _make_session,
    _download_profile_image,
    scrape_full_player,
    compute_hash,
    compute_refresh_days,
    SCRAPE_DELAY,
    _IMAGE_DIR,
)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://aquinao:AquiNao_2026_Strong!@localhost:5433/aqui_nao",
)

LOG_DIR = Path("/var/log/aquinao")
RUNS_DIR = LOG_DIR / "runs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
RUNS_DIR.mkdir(parents=True, exist_ok=True)

RUN_ID = datetime.now().strftime("%Y%m%d_%H%M")
RUN_LOG = RUNS_DIR / f"seeder_retired_{RUN_ID}.log"

_fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

_fh = logging.FileHandler(LOG_DIR / "seeder_retired.log")
_fh.setFormatter(_fmt)

_rh = logging.FileHandler(RUN_LOG)
_rh.setFormatter(_fmt)

_sh = logging.StreamHandler()
_sh.setFormatter(_fmt)

logger = logging.getLogger("seeder_retired")
logger.setLevel(logging.DEBUG)
logger.addHandler(_fh)
logger.addHandler(_rh)
logger.addHandler(_sh)

MAX_PER_RUN = 50

TARGET_LEAGUES = [
    "ENG-Premier League",
    "ESP-La Liga",
    "GER-Bundesliga",
    "ITA-Serie A",
    "FRA-Ligue 1",
    "BRA-Série A",
]

# ---------------------------------------------------------------------------
# FBref → lista de nomes
# ---------------------------------------------------------------------------

def _get_historic_players() -> list[str]:
    """Retorna nomes de jogadores que jogaram nos top campeonatos
    e estão aposentados (última temporada < 2024)."""
    from soccerdata import FBref

    seen: dict[str, int] = {}  # name → last_year

    for league in TARGET_LEAGUES:
        logger.info("FBref: lendo %s...", league)
        try:
            fbref = FBref(leagues=league)
            df = fbref.read_player_season_info()
        except Exception as exc:
            logger.warning("FBref falhou para %s: %s", league, exc)
            continue

        if df is None or df.empty:
            continue

        df = df.reset_index()

        for _, row in df.iterrows():
            player = str(row.get("player", ""))
            season = str(row.get("season", ""))
            m = re.match(r"(\d{4})", season)
            year = int(m.group(1)) if m else 9999
            if player:
                seen[player] = max(seen.get(player, 0), year)

        logger.info("  %d jogadores (%d únicos no total)", len(df), len(seen))
        time.sleep(2)

    # Filtra aposentados (last season < 2024), ordena por nome
    retired = sorted(n for n, y in seen.items() if y < 2024)
    logger.info("FBref: %d aposentados de %d únicos", len(retired), len(seen))
    return retired


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def _is_seeded(conn, name: str) -> bool:
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM players WHERE LOWER(name) = LOWER(%s) LIMIT 1", (name,))
        return cur.fetchone() is not None


def _insert_retired(
    conn, name: str, data: dict, new_hash: str,
    next_refresh: datetime, tm_url: str,
) -> None:
    """Insere ou atualiza jogador aposentado no DB (inclui seasons + injuries)."""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO players
                (name, full_name, date_of_birth, nationality, position,
                 current_team, market_value, social_media, profile_image_url,
                 transfermarkt_url, is_retired, is_injured,
                 last_scraped_at, next_refresh_at, data_hash,
                 market_value_rank)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    TRUE, FALSE, NOW(), %s, %s, 99999)
            ON CONFLICT (name) DO UPDATE SET
                full_name         = COALESCE(EXCLUDED.full_name, players.full_name),
                date_of_birth     = COALESCE(EXCLUDED.date_of_birth, players.date_of_birth),
                nationality       = COALESCE(EXCLUDED.nationality, players.nationality),
                position          = COALESCE(EXCLUDED.position, players.position),
                current_team      = EXCLUDED.current_team,
                market_value      = EXCLUDED.market_value,
                social_media      = EXCLUDED.social_media,
                profile_image_url = COALESCE(EXCLUDED.profile_image_url, players.profile_image_url),
                transfermarkt_url = COALESCE(EXCLUDED.transfermarkt_url, players.transfermarkt_url),
                is_retired        = TRUE,
                last_scraped_at   = NOW(),
                next_refresh_at   = EXCLUDED.next_refresh_at,
                data_hash         = EXCLUDED.data_hash
            RETURNING id
            """,
            (
                name,
                data.get("full_name", name),
                _normalize_date(data.get("date_of_birth") or ""),
                data.get("nationality", ""),
                data.get("position", ""),
                data.get("current_team"),
                data.get("market_value"),
                json.dumps(data.get("social_media")) if data.get("social_media") else None,
                data.get("profile_image_url"),
                next_refresh,
                new_hash,
            ),
        )
        row = cur.fetchone()
        if not row:
            conn.commit()
            return
        player_id = row[0]

        cur.execute("DELETE FROM season_stats WHERE player_id = %s", (player_id,))
        if data.get("seasons"):
            psycopg2.extras.execute_values(
                cur,
                """INSERT INTO season_stats
                       (player_id, season, team, age, appearances, starts,
                        minutes_played, goals, assists, yellow_cards, red_cards)
                   VALUES %s""",
                [
                    (player_id, s["season"], s.get("team", ""), 0,
                     s["appearances"], 0, 0, s["goals"], s.get("assists", 0), 0, 0)
                    for s in data["seasons"]
                ],
            )

        cur.execute("DELETE FROM injuries WHERE player_id = %s", (player_id,))
        if data.get("injuries"):
            psycopg2.extras.execute_values(
                cur,
                """INSERT INTO injuries
                       (player_id, season, injury_type, date_from, date_until,
                        days_missed, games_missed)
                   VALUES %s""",
                [
                    (player_id, i["season"], i["injury_type"],
                     _normalize_date(i.get("date_from", "")),
                     _normalize_date(i.get("date_until", "")),
                     i.get("days_missed", 0), i.get("games_missed", 0))
                    for i in data["injuries"]
                ],
            )

    conn.commit()


def _normalize_date(raw: str) -> str | None:
    if not raw:
        return None
    raw = raw.strip()
    m = re.match(r"(\d{1,2})[/.](\d{1,2})[/.](\d{4})", raw)
    if m:
        return f"{m.group(3)}-{m.group(2).zfill(2)}-{m.group(1).zfill(2)}"
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", raw)
    if m:
        return raw
    for fmt in ("%b %d, %Y", "%d %b %Y", "%B %d, %Y", "%d %B %Y"):
        try:
            from datetime import datetime as _dt
            return _dt.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return None


def seed_retired() -> None:
    start = time.time()
    logger.info("=" * 60)
    logger.info("RUN %s — Seeder de aposentados iniciado", RUN_ID)
    logger.info("Log: %s", RUN_LOG)
    logger.info("=" * 60)

    conn = _get_conn()

    all_players = _get_historic_players()
    logger.info("FBref: %d nomes únicos", len(all_players))

    to_process = [n for n in all_players if not _is_seeded(conn, n)]
    logger.info("%d já no DB, %d pendentes", len(all_players) - len(to_process), len(to_process))

    to_process = to_process[:MAX_PER_RUN]
    if not to_process:
        logger.info("Nada a fazer.")
        conn.close()
        return

    logger.info("Processando %d nesta execução", len(to_process))

    session = _make_session()
    processed = errors = skipped = 0

    for idx, name in enumerate(to_process, 1):
        logger.info("[%d/%d] %s", idx, len(to_process), name)

        try:
            tm_url = search_player_url(name)
        except Exception as exc:
            logger.warning("  TM search falhou: %s", exc)
            errors += 1
            continue

        if not tm_url:
            logger.info("  sem resultado no TM")
            skipped += 1
            continue

        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM players WHERE transfermarkt_url = %s LIMIT 1", (tm_url,))
            if cur.fetchone():
                logger.info("  já existe (URL duplicada)")
                skipped += 1
                continue

        try:
            data = scrape_full_player(session, tm_url)
        except Exception as exc:
            logger.warning("  scrape falhou: %s", exc)
            errors += 1
            continue

        if not data:
            logger.warning("  scrape vazio")
            errors += 1
            continue

        if data.get("profile_image_url"):
            local_url = _download_profile_image(data["profile_image_url"], tm_url)
            if local_url:
                data["profile_image_url"] = local_url

        data["is_retired"] = True
        new_hash = compute_hash(data)
        refresh_days = compute_refresh_days(99, 9999, True)
        next_refresh = datetime.now(timezone.utc) + timedelta(days=refresh_days)

        _insert_retired(conn, name, data, new_hash, next_refresh, tm_url)
        processed += 1
        logger.info("  INSERIDO (refresh em %dd)", refresh_days)

        time.sleep(SCRAPE_DELAY)

    elapsed = int(time.time() - start)
    conn.close()

    logger.info("=" * 60)
    logger.info("RUN %s CONCLUÍDO em %dm%ds | processados=%d erros=%d pulados=%d",
                RUN_ID, elapsed // 60, elapsed % 60, processed, errors, skipped)
    logger.info("Log completo: %s", RUN_LOG)
    logger.info("=" * 60)


if __name__ == "__main__":
    try:
        seed_retired()
    except Exception:
        logger.exception("CRASH FATAL no seeder_retired — traceback completo acima")
        raise
