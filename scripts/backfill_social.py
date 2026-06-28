#!/usr/bin/env python3
"""
One-time backfill: scrape social_media and profile_image_url for all existing players.

Usage:
  cd /home/ubuntu/aqui-nao
  DATABASE_URL=postgresql://aquinao:AquiNao_2026_Strong!@localhost:5433/aqui_nao python3 scripts/backfill_social.py
"""
from __future__ import annotations

import json
import logging
import os
import re
import sys
import time

import psycopg2
import psycopg2.extras
import requests
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("backfill")

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    logger.error("DATABASE_URL nao definida")
    sys.exit(1)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
}
SCRAPE_DELAY = 1.5


def _scrape_social_and_image(tm_url: str) -> dict:
    """Scrape social media handles and profile image from Transfermarkt profile."""
    result: dict = {}
    try:
        r = requests.get(tm_url, headers=HEADERS, timeout=15)
        r.raise_for_status()
    except Exception as exc:
        logger.warning("  erro HTTP: %s", exc)
        return result

    soup = BeautifulSoup(r.text, "html.parser")

    social: dict[str, str] = {}
    for a in soup.select("a[href]"):
        href = a["href"]
        if "instagram.com/" in href and "transfermarkt" not in href:
            handle = href.rstrip("/").split("/")[-1]
            if handle:
                social["instagram"] = handle
        elif ("x.com/" in href or "twitter.com/" in href) and "transfermarkt" not in href:
            handle = href.rstrip("/").split("/")[-1]
            if handle and handle != "home":
                social["twitter"] = handle
    if social:
        result["social_media"] = social

    img = soup.select_one("img.data-header__profile-image")
    if img:
        src = img.get("src", "")
        if src and "default" not in src:
            result["profile_image_url"] = src

    return result


def main():
    conn = psycopg2.connect(DATABASE_URL, connect_timeout=5)

    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, name, transfermarkt_url FROM players "
            "WHERE transfermarkt_url IS NOT NULL "
            "ORDER BY id"
        )
        players = cur.fetchall()

    logger.info("%d jogadores com transfermarkt_url", len(players))

    updated = 0
    for pid, name, tm_url in players:
        profile_url = re.sub(r"/(leistungsdaten|verletzungen|transfers)/", "/profil/", tm_url)
        profile_url = re.sub(r"\?.*", "", profile_url)

        logger.info("[%d/%d] %s", updated + 1, len(players), name)
        data = _scrape_social_and_image(profile_url)

        if not data:
            time.sleep(SCRAPE_DELAY)
            continue

        with conn.cursor() as cur:
            cur.execute(
                """UPDATE players SET
                    social_media = %s,
                    profile_image_url = COALESCE(%s, profile_image_url),
                    last_scraped_at = NOW()
                WHERE id = %s""",
                (
                    json.dumps(data.get("social_media")) if data.get("social_media") else None,
                    data.get("profile_image_url"),
                    pid,
                ),
            )
        conn.commit()
        updated += 1

        if data.get("social_media"):
            logger.info("  social: %s", data["social_media"])
        if data.get("profile_image_url"):
            logger.info("  image: OK")

        time.sleep(SCRAPE_DELAY)

    conn.close()
    logger.info("Concluido! %d jogadores atualizados", updated)


if __name__ == "__main__":
    main()
