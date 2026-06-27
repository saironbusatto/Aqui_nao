"""Transfermarkt scraper - fetches real player data from transfermarkt.com."""

import re
import time
import logging
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

from src.models.player import Player, SeasonStats, Injury
from src.utils.cache import get_cached, set_cached

logger = logging.getLogger(__name__)

BASE_URL = "https://www.transfermarkt.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}

_session = requests.Session()
_session.headers.update(HEADERS)


def _get_soup(url: str) -> BeautifulSoup:
    """Fetch URL and return BeautifulSoup object."""
    resp = _session.get(url, timeout=30)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "html.parser")


def _parse_goals(text: str) -> int:
    """Parse goal count from text like '42 goals' or '42'."""
    match = re.search(r"(\d+)", text)
    return int(match.group(1)) if match else 0


def _parse_date(date_str: str) -> str:
    """Parse date from Transfermarkt format to YYYY-MM-DD."""
    parts = date_str.strip().split("/")
    if len(parts) == 3:
        return f"{parts[2]}-{parts[1]}-{parts[0]}"
    parts = date_str.strip().split(".")
    if len(parts) == 3:
        return f"{parts[2]}-{parts[1]}-{parts[0]}"
    return date_str.strip()


def search_player_url(name: str) -> str | None:
    """Search Transfermarkt for a player and return their profile URL."""
    search_url = f"{BASE_URL}/schnellsuche/ergebnis/schnellsuche"
    try:
        soup = _get_soup(f"{search_url}?query={quote(name)}")
    except Exception as e:
        logger.error("Failed to search for %s: %s", name, e)
        return None

    results = soup.select("table.items tbody tr")
    for row in results:
        link = row.select_one("td.hauptlink a")
        if link and link.get("href"):
            return BASE_URL + link["href"]

    return None


def search_players(name: str) -> list[dict]:
    """Search Transfermarkt for multiple players matching the name.

    Returns list of dicts with 'name', 'url', 'nationality', 'club'.
    Prioritizes Brazilian players.
    """
    cached = get_cached("search", name.lower())
    if cached is not None:
        return cached

    search_url = f"{BASE_URL}/schnellsuche/ergebnis/schnellsuche"
    try:
        soup = _get_soup(f"{search_url}?query={quote(name)}")
    except Exception as e:
        logger.error("Failed to search for %s: %s", name, e)
        return []

    players = []
    rows = soup.select("table.items tbody tr")

    for row in rows:
        link = row.select_one("td.hauptlink a")
        if not link or not link.get("href"):
            continue

        url = BASE_URL + link["href"]
        player_name = link.text.strip()

        cells = row.select("td")
        nationality = ""
        club = ""
        for cell in cells:
            img = cell.select_one("img.flaggenrahmen")
            if img and img.get("title"):
                nationality = img["title"]
            elif cell.select_one("a[href*='/verein/']"):
                club_link = cell.select_one("a[href*='/verein/']")
                club = club_link.text.strip() if club_link else ""

        players.append({
            "name": player_name,
            "url": url,
            "nationality": nationality,
            "club": club,
        })

    br = [p for p in players if "brazil" in p["nationality"].lower() or "brasil" in p["nationality"].lower()]
    others = [p for p in players if p not in br]

    result = br + others
    set_cached("search", name.lower(), result)
    return result


def scrape_player_profile(url: str) -> dict | None:
    """Scrape player profile page for bio data."""
    try:
        soup = _get_soup(url)
    except Exception as e:
        logger.error("Failed to fetch profile %s: %s", url, e)
        return None

    data = {}

    name_el = soup.select_one("h1")
    if name_el:
        strong = name_el.select_one("strong")
        data["full_name"] = strong.text.strip() if strong else name_el.text.strip()

    items = soup.select(".info-table__content")
    for i in range(0, len(items), 2):
        if i + 1 < len(items):
            label = items[i].text.strip().lower()
            value = items[i + 1].text.strip()

            if "full name" in label or "vollständiger name" in label:
                data["full_name"] = value
            elif "date of birth" in label or "geboren" in label:
                date_match = re.search(r"(\d{2}/\d{2}/\d{4})", value)
                if date_match:
                    parts = date_match.group(1).split("/")
                    data["date_of_birth"] = f"{parts[2]}-{parts[1]}-{parts[0]}"
            elif "citizenship" in label or "nationality" in label or "staatsbürgerschaft" in label:
                data["nationality"] = value.split("\n")[0].strip()
            elif "position" in label:
                data["position"] = value.split(" - ")[-1].strip() if " - " in value else value
            elif "current club" in label or "aktueller verein" in label:
                data["current_team"] = value
            elif "outfitter" in label or "sponsor" in label:
                sponsors = [s.strip() for s in value.split("\n") if s.strip()]
                data["sponsors"] = tuple(sponsors)

    market_el = soup.select_one(".tm-market-value")
    if market_el:
        data["market_value"] = market_el.text.strip()

    return data if data.get("full_name") else None


def scrape_career_stats(url: str) -> tuple[SeasonStats, ...]:
    """Scrape career statistics table from player profile."""
    try:
        soup = _get_soup(url)
    except Exception as e:
        logger.error("Failed to fetch career stats %s: %s", url, e)
        return ()

    stats_url = url.rstrip("/") + "/leistungsdatendetails"
    if "/detaillist" not in url:
        stats_url = url.replace("/profil/", "/leistungsdaten/")

    try:
        soup = _get_soup(url)
    except Exception:
        return ()

    career_table = soup.select_one("table.items")
    if not career_table:
        tables = soup.select("table")
        for t in tables:
            rows = t.select("tr")
            if len(rows) > 5:
                career_table = t
                break

    if not career_table:
        return ()

    seasons = []
    rows = career_table.select("tr")

    for row in rows:
        cells = row.select("td")
        if len(cells) < 6:
            continue

        season_text = cells[0].text.strip()
        if not season_text or "Season" in season_text:
            continue

        team_el = row.select_one("td a[href*='/verein/']")
        team = team_el.text.strip() if team_el else "Unknown"

        try:
            appearances = int(cells[4].text.strip()) if cells[4].text.strip().isdigit() else 0
        except (ValueError, IndexError):
            appearances = 0

        try:
            goals = int(cells[5].text.strip()) if cells[5].text.strip().isdigit() else 0
        except (ValueError, IndexError):
            goals = 0

        try:
            assists = int(cells[6].text.strip()) if cells[6].text.strip().isdigit() else 0
        except (ValueError, IndexError):
            assists = 0

        seasons.append(SeasonStats(
            season=season_text,
            team=team,
            age=0,
            appearances=appearances,
            starts=0,
            minutes_played=0,
            goals=goals,
            assists=assists,
            yellow_cards=0,
            red_cards=0,
        ))

    return tuple(seasons)


def scrape_injuries(url: str) -> tuple[Injury, ...]:
    """Scrape injury history from player profile."""
    injury_url = url.rstrip("/").replace("/profil/", "/verletzungen/")
    if "/verletzungen" not in injury_url:
        injury_url = url.rstrip("/") + "/verletzungen"

    try:
        soup = _get_soup(injury_url)
    except Exception as e:
        logger.error("Failed to fetch injuries %s: %s", injury_url, e)
        return ()

    injuries = []
    rows = soup.select("table.items tbody tr")

    for row in rows:
        cells = row.select("td")
        if len(cells) < 6:
            continue

        season = cells[0].text.strip()
        injury_type = cells[1].text.strip()
        date_from = cells[2].text.strip()
        date_until = cells[3].text.strip()

        try:
            days = int(cells[4].text.strip())
        except (ValueError, IndexError):
            days = 0

        try:
            games = int(cells[5].text.strip())
        except (ValueError, IndexError):
            games = 0

        if season and injury_type:
            injuries.append(Injury(
                season=season,
                injury_type=injury_type,
                date_from=date_from,
                date_until=date_until,
                days_missed=days,
                games_missed=games,
            ))

    return tuple(injuries)


def scrape_player(name: str) -> Player | None:
    """Full scrape: search, get profile, stats, and injuries."""
    cache_key = name.lower()
    cached = get_cached("player", cache_key)
    if cached is not None:
        return Player(**{k: tuple(v) if isinstance(v, list) else v for k, v in cached.items()})

    url = search_player_url(name)
    if not url:
        logger.warning("No URL found for player: %s", name)
        return None

    profile = scrape_player_profile(url)
    if not profile:
        return None

    career = scrape_career_stats(url)
    injuries = scrape_injuries(url)

    display_name = name.title()

    player = Player(
        name=display_name,
        full_name=profile.get("full_name", display_name),
        date_of_birth=profile.get("date_of_birth", ""),
        nationality=profile.get("nationality", ""),
        position=profile.get("position", ""),
        current_team=profile.get("current_team"),
        market_value=profile.get("market_value"),
        sponsors=profile.get("sponsors", ()),
        career_seasons=career,
        injuries=injuries,
    )

    import dataclasses
    set_cached("player", cache_key, dataclasses.asdict(player))
    return player
