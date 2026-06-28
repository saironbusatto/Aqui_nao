from __future__ import annotations

import logging
import os
import re

import requests

logger = logging.getLogger(__name__)

_IMAGE_DIR_REL = "static/images/players"


def download_profile_image(image_url: str, tm_url: str, project_root: str) -> str | None:
    if not image_url or "default" in image_url:
        return None
    m = re.search(r"/spieler/(\d+)", tm_url)
    if not m:
        logger.warning("TM ID não encontrado em: %s", tm_url)
        return None
    tm_id = m.group(1)
    ext = _get_ext(image_url)
    filename = f"{tm_id}{ext}"
    img_dir = os.path.join(project_root, _IMAGE_DIR_REL)
    os.makedirs(img_dir, exist_ok=True)
    local_path = os.path.join(img_dir, filename)
    if os.path.exists(local_path):
        return f"/{_IMAGE_DIR_REL}/{filename}"
    try:
        r = requests.get(image_url, timeout=15)
        r.raise_for_status()
        with open(local_path, "wb") as f:
            f.write(r.content)
        logger.info("Imagem salva: %s (%d bytes)", filename, len(r.content))
        return f"/{_IMAGE_DIR_REL}/{filename}"
    except Exception as e:
        logger.warning("Falha ao baixar imagem %s: %s", image_url, e)
        return None


def _get_ext(url: str) -> str:
    path = url.split("?")[0].rstrip("/")
    _, ext = os.path.splitext(path)
    return ext or ".jpg"
