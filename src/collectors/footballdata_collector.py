"""Football-Data.org API collector."""

import os

import requests

BASE_URL = "https://api.football-data.org/v4"


def _get_api_key() -> str:
    """Retrieve API key from environment."""
    return os.environ.get("FOOTBALL_DATA_API_KEY", "")


def get_world_cup_stats(player_name: str) -> dict:
    """Get World Cup statistics for a player.

    Raises:
        ValueError: If player is not found (HTTP 404).
        PermissionError: If API key is invalid (HTTP 403).
        ConnectionError: On network failures.
    """
    api_key = _get_api_key()
    headers = {"X-Auth-Token": api_key}

    resp = requests.get(
        f"{BASE_URL}/players",
        params={"name": player_name},
        headers=headers,
        timeout=30,
    )

    if resp.status_code == 403:
        raise PermissionError("API key error: invalid or missing API key")
    if resp.status_code == 404:
        raise ValueError(f"Player not found: {player_name}")

    data = resp.json()
    return {
        "player": data.get("player", player_name),
        "world_cup_goals": data.get("world_cup_goals", 0),
        "world_cup_appearances": data.get("world_cup_appearances", 0),
        "world_cups_played": data.get("world_cups_played", []),
    }
