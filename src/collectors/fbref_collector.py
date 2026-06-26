"""FBref data collector using soccerdata library."""

import soccerdata

from src.models.player import Player, SeasonStats


def search_player(name: str) -> list[dict]:
    """Search FBref for players matching the given name."""
    fb = soccerdata.FBref()
    return fb.players(name)


def get_player_stats(player_id: str) -> Player:
    """Get full player stats from FBref.

    Raises:
        ValueError: If player is not found.
        ConnectionError: On network failures.
    """
    fb = soccerdata.FBref()
    data = fb.get_player_stats(player_id)

    if data is None:
        raise ValueError(f"Player not found: {player_id}")

    full_name = data["full_name"]
    parts = full_name.split()
    if len(parts) >= 3:
        name = f"{parts[0]} {parts[-2]}"
    else:
        name = full_name

    career_seasons = tuple(data.get("career_seasons", []))

    return Player(
        name=name,
        full_name=full_name,
        date_of_birth=data["date_of_birth"],
        nationality=data["nationality"],
        position=data["position"],
        height_cm=data.get("height_cm"),
        current_team=data.get("current_team"),
        career_seasons=career_seasons,
    )
