from __future__ import annotations

from pathlib import Path
from typing import Any

import diskcache

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache"
CACHE_TTL_SECONDS = 86400

_instances: dict[str, diskcache.Cache] = {}


def _get_cache() -> diskcache.Cache:
    path = str(CACHE_DIR)
    if path not in _instances:
        _instances[path] = diskcache.Cache(path)
    return _instances[path]


def _key(namespace: str, identifier: str) -> str:
    return f"{namespace}:{identifier}"


def get_cached(namespace: str, identifier: str) -> Any | None:
    return _get_cache().get(_key(namespace, identifier))


def set_cached(namespace: str, identifier: str, payload: Any) -> None:
    _get_cache().set(_key(namespace, identifier), payload, expire=CACHE_TTL_SECONDS)


def clear_cache() -> int:
    cache = _get_cache()
    count = len(cache)
    cache.clear()
    return count
