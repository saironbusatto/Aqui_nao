"""Transfermarkt data collector using requests + BeautifulSoup."""

import requests
from bs4 import BeautifulSoup

from src.models.player import Injury

BASE_URL = "https://www.transfermarkt.com"


def get_player_profile(name: str) -> dict:
    """Get player bio and injury data from Transfermarkt.

    Raises:
        ValueError: If player is not found (HTTP 404).
        ConnectionError: On network failures.
    """
    resp = requests.get(
        f"{BASE_URL}/schnellsuche/ergebnis/schnellsuche",
        params={"query": name},
        timeout=30,
    )

    if resp.status_code == 404:
        raise ValueError(f"Player not found: {name}")

    soup = BeautifulSoup(resp.text, "html.parser")
    elements = soup.select(".info-table__content--bold, .data-header__label")

    return {
        "name": elements[0].text.strip() if len(elements) > 0 else name,
        "date_of_birth": elements[1].text.strip() if len(elements) > 1 else "",
        "nationality": elements[2].text.strip() if len(elements) > 2 else "",
    }


def get_injury_history(player_id: str) -> list[Injury]:
    """Get injury history for a player from Transfermarkt.

    Raises:
        ValueError: If player is not found (HTTP 404).
        ConnectionError: On network failures.
    """
    resp = requests.get(
        f"{BASE_URL}/{player_id}/verletzungen",
        timeout=30,
    )

    if resp.status_code == 404:
        raise ValueError(f"Player not found: {player_id}")

    soup = BeautifulSoup(resp.text, "html.parser")
    elements = soup.select(
        ".items td, .responsive-table .inline-table td"
    )

    injuries: list[Injury] = []
    for i in range(0, len(elements), 6):
        if i + 5 < len(elements):
            try:
                days = int(elements[i + 4].text.strip())
            except ValueError:
                days = 0
            try:
                games = int(elements[i + 5].text.strip())
            except ValueError:
                games = 0
            injuries.append(Injury(
                season=elements[i].text.strip(),
                injury_type=elements[i + 1].text.strip(),
                date_from=elements[i + 2].text.strip(),
                date_until=elements[i + 3].text.strip(),
                days_missed=days,
                games_missed=games,
            ))

    return injuries
