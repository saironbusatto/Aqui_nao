import json
import hashlib
import time
from pathlib import Path
from typing import Any


CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache"
CACHE_TTL_SECONDS = 86400


def _ensure_cache_dir() -> None:
    """Create cache directory if it doesn't exist."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _cache_key(namespace: str, identifier: str) -> str:
    """Generate a cache key from namespace and identifier."""
    raw = f"{namespace}:{identifier}"
    return hashlib.sha256(raw.encode()).hexdigest()


def get_cached(namespace: str, identifier: str) -> Any | None:
    """Retrieve cached data if it exists and is not expired."""
    _ensure_cache_dir()
    key = _cache_key(namespace, identifier)
    cache_file = CACHE_DIR / f"{key}.json"

    if not cache_file.exists():
        return None

    with open(cache_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    if time.time() - data.get("timestamp", 0) > CACHE_TTL_SECONDS:
        cache_file.unlink(missing_ok=True)
        return None

    return data.get("payload")


def set_cached(namespace: str, identifier: str, payload: Any) -> None:
    """Store data in cache with timestamp."""
    _ensure_cache_dir()
    key = _cache_key(namespace, identifier)
    cache_file = CACHE_DIR / f"{key}.json"

    data = {
        "timestamp": time.time(),
        "payload": payload,
    }

    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def clear_cache() -> int:
    """Clear all cached data. Returns number of files removed."""
    _ensure_cache_dir()
    count = 0
    for cache_file in CACHE_DIR.glob("*.json"):
        cache_file.unlink()
        count += 1
    return count
