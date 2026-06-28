#!/usr/bin/env python3
"""
One-off: download profile images for all existing DB players
that have a profile_image_url pointing to Transfermarkt CDN.
"""
from __future__ import annotations

import logging
import os
import re
import sys
import time

import psycopg2
import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

_log = logging.getLogger(__name__)

_IMAGE_DIR = "src/static/images/players"


def _download(url: str, tm_url: str) -> str | None:
    m = re.search(r"/spieler/(\d+)", tm_url)
    if not m:
        return None
    tm_id = m.group(1)
    path = url.split("?")[0].rstrip("/")
    _, ext = os.path.splitext(path)
    ext = ext or ".jpg"
    filename = f"{tm_id}{ext}"
    os.makedirs(_IMAGE_DIR, exist_ok=True)
    local = os.path.join(_IMAGE_DIR, filename)
    if os.path.exists(local):
        return f"/static/images/players/{filename}"
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        with open(local, "wb") as f:
            f.write(r.content)
        _log.info("OK  %s (%d bytes)", filename, len(r.content))
        return f"/static/images/players/{filename}"
    except Exception as e:
        _log.warning("ERR %s: %s", filename, e)
        return None


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        _log.error("DATABASE_URL não definida")
        return
    conn = psycopg2.connect(db_url, connect_timeout=5)
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, name, profile_image_url, transfermarkt_url "
            "FROM players "
            "WHERE profile_image_url IS NOT NULL "
            "AND profile_image_url LIKE '%%transfermarkt%%' "
            "AND transfermarkt_url IS NOT NULL "
            "ORDER BY id"
        )
        rows = cur.fetchall()
    total = len(rows)
    _log.info("%d imagens para baixar", total)
    updated = 0
    for i, (pid, name, img_url, tm_url) in enumerate(rows, 1):
        local = _download(img_url, tm_url)
        if local:
            with conn.cursor() as c2:
                c2.execute("UPDATE players SET profile_image_url = %s WHERE id = %s", (local, pid))
            conn.commit()
            updated += 1
        time.sleep(0.3)
    _log.info("Concluído: %d/%d atualizadas", updated, total)
    conn.close()


if __name__ == "__main__":
    main()
