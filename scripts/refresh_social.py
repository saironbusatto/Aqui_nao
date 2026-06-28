#!/usr/bin/env python3
"""
Refresh social media handles and profile images for all DB players.
Scrapes only the profile page (1 request, lightweight) — no stats/injuries.

Cron suggestion: weekly (domingo 04:00)
  0 4 * * 0  cd /home/ubuntu/aqui-nao && DATABASE_URL=... python3 scripts/refresh_social.py >> /var/log/aquinao/refresh_social.log 2>&1
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
import sys
from datetime import datetime

import psycopg2
import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.collectors.transfermarkt_scraper import scrape_player_profile as _scrape_profile

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

SCRAPE_DELAY = 1.5
_IMAGE_DIR = "src/static/images/players"

_log = logging.getLogger(__name__)


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("/var/log/aquinao/refresh_social.log"),
        ],
    )


def _download_image(image_url: str, tm_url: str) -> str | None:
    if not image_url or "default" in image_url:
        return None
    m = re.search(r"/spieler/(\d+)", tm_url)
    if not m:
        return None
    tm_id = m.group(1)
    path = image_url.split("?")[0].rstrip("/")
    _, ext = os.path.splitext(path)
    ext = ext or ".jpg"
    filename = f"{tm_id}{ext}"
    os.makedirs(_IMAGE_DIR, exist_ok=True)
    local = os.path.join(_IMAGE_DIR, filename)
    if os.path.exists(local):
        return f"/static/images/players/{filename}"
    try:
        r = requests.get(image_url, timeout=15)
        r.raise_for_status()
        with open(local, "wb") as f:
            f.write(r.content)
        _log.info("Imagem salva: %s (%d bytes)", filename, len(r.content))
        return f"/static/images/players/{filename}"
    except Exception as e:
        _log.warning("Falha ao baixar imagem %s: %s", image_url, e)
        return None


def refresh_all() -> None:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        _log.error("DATABASE_URL não definida")
        return

    conn = psycopg2.connect(database_url, connect_timeout=5)
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, name, transfermarkt_url FROM players WHERE transfermarkt_url IS NOT NULL ORDER BY id"
        )
        rows = cur.fetchall()

    total = len(rows)
    _log.info("%d jogadores com transfermarkt_url", total)

    updated = 0
    errors = 0
    start = time.time()

    for i, (pid, pname, tm_url) in enumerate(rows, 1):
        progress = f"[{i}/{total}]"
        _log.info("%s %s", progress, pname)

        try:
            data = _scrape_profile(tm_url)
        except Exception as e:
            _log.warning("%s ERRO: %s", progress, e)
            errors += 1
            time.sleep(SCRAPE_DELAY)
            continue

        if not data:
            _log.warning("%s sem dados retornados", progress)
            errors += 1
            time.sleep(SCRAPE_DELAY)
            continue

        social = data.get("social_media")
        image_url = data.get("profile_image_url")

        if image_url:
            local = _download_image(image_url, tm_url)
            if local:
                image_url = local

        if social:
            _log.info("  social: %s", social)
        if image_url:
            img_short = image_url.split("/")[-1]
            _log.info("  image: %s", img_short)

        with conn.cursor() as cur:
            cur.execute(
                "UPDATE players SET social_media = %s, profile_image_url = COALESCE(%s, profile_image_url) WHERE id = %s",
                (json.dumps(social) if social else None, image_url, pid),
            )
        conn.commit()
        updated += 1
        time.sleep(SCRAPE_DELAY)

    elapsed = int(time.time() - start)
    _log.info(
        "Concluído em %dm%ds | atualizados=%d erros=%d",
        elapsed // 60, elapsed % 60, updated, errors,
    )
    conn.close()


if __name__ == "__main__":
    _setup_logging()
    refresh_all()
