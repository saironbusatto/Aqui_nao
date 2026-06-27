"""Tests for the Transfermarkt scraper collector."""

from unittest.mock import MagicMock, patch, mock_open

import pytest

from src.models.player import Player, SeasonStats, Injury


@pytest.mark.unit
class TestSearchPlayers:
    """Tests for search_players function."""

    @patch("src.collectors.transfermarkt_scraper.get_cached", return_value=None)
    @patch("src.collectors.transfermarkt_scraper.set_cached")
    @patch("src.collectors.transfermarkt_scraper._get_soup")
    def test_returns_list(self, mock_soup, mock_set, mock_get):
        from src.collectors.transfermarkt_scraper import search_players

        soup = MagicMock()
        soup.select.return_value = []
        mock_soup.return_value = soup

        result = search_players("messi")
        assert isinstance(result, list)

    @patch("src.collectors.transfermarkt_scraper.get_cached")
    def test_uses_cache_when_available(self, mock_get):
        from src.collectors.transfermarkt_scraper import search_players

        cached = [{"name": "Messi", "url": "http://x", "nationality": "Argentina", "club": "Miami"}]
        mock_get.return_value = cached

        result = search_players("messi")
        assert result == cached
        mock_get.assert_called_once_with("search", "messi")

    @patch("src.collectors.transfermarkt_scraper.get_cached", return_value=None)
    @patch("src.collectors.transfermarkt_scraper.set_cached")
    @patch("src.collectors.transfermarkt_scraper._get_soup")
    def test_returns_empty_on_network_error(self, mock_soup, mock_set, mock_get):
        from src.collectors.transfermarkt_scraper import search_players

        mock_soup.side_effect = Exception("Network error")
        result = search_players("unknown player xyz")
        assert result == []

    @patch("src.collectors.transfermarkt_scraper.get_cached", return_value=None)
    @patch("src.collectors.transfermarkt_scraper.set_cached")
    @patch("src.collectors.transfermarkt_scraper._get_soup")
    def test_brazilian_players_sorted_first(self, mock_soup, mock_set, mock_get):
        from src.collectors.transfermarkt_scraper import search_players
        from bs4 import BeautifulSoup

        html = """
        <table class="items"><tbody>
          <tr>
            <td class="hauptlink"><a href="/neymar/profil/spieler/1">Neymar</a></td>
            <td><img class="flaggenrahmen" title="Brazil"/></td>
            <td><a href="/psg/verein/123">PSG</a></td>
          </tr>
          <tr>
            <td class="hauptlink"><a href="/messi/profil/spieler/2">Messi</a></td>
            <td><img class="flaggenrahmen" title="Argentina"/></td>
            <td><a href="/miami/verein/456">Miami</a></td>
          </tr>
        </tbody></table>
        """
        mock_soup.return_value = BeautifulSoup(html, "html.parser")

        result = search_players("test")
        brazilian = [p for p in result if "brazil" in p["nationality"].lower()]
        others = [p for p in result if "brazil" not in p["nationality"].lower()]
        assert result == brazilian + others


@pytest.mark.unit
class TestScrapePlayer:
    """Tests for scrape_player function."""

    @patch("src.collectors.transfermarkt_scraper.get_cached")
    def test_uses_cache_when_available(self, mock_get):
        from src.collectors.transfermarkt_scraper import scrape_player

        cached = {
            "name": "Messi",
            "full_name": "Lionel Messi",
            "date_of_birth": "1987-06-24",
            "nationality": "Argentina",
            "position": "Forward",
            "current_team": "Inter Miami",
            "market_value": None,
            "sponsors": [],
            "career_seasons": [],
            "injuries": [],
            "world_cup_goals": 0,
            "world_cup_appearances": 0,
        }
        mock_get.return_value = cached

        result = scrape_player("messi")
        assert isinstance(result, Player)
        assert result.name == "Messi"

    @patch("src.collectors.transfermarkt_scraper.get_cached", return_value=None)
    @patch("src.collectors.transfermarkt_scraper.search_player_url", return_value=None)
    def test_returns_none_when_url_not_found(self, mock_url, mock_get):
        from src.collectors.transfermarkt_scraper import scrape_player

        result = scrape_player("unknown xyz abc")
        assert result is None

    @patch("src.collectors.transfermarkt_scraper.get_cached", return_value=None)
    @patch("src.collectors.transfermarkt_scraper.search_player_url", return_value="http://fake.url")
    @patch("src.collectors.transfermarkt_scraper.scrape_player_profile", return_value=None)
    def test_returns_none_when_profile_not_found(self, mock_profile, mock_url, mock_get):
        from src.collectors.transfermarkt_scraper import scrape_player

        result = scrape_player("unknown xyz")
        assert result is None


@pytest.mark.unit
class TestSearchPlayerUrl:
    @patch("src.collectors.transfermarkt_scraper._get_soup")
    def test_returns_url_when_found(self, mock_soup):
        from bs4 import BeautifulSoup
        from src.collectors.transfermarkt_scraper import search_player_url

        html = """
        <table class="items"><tbody>
          <tr><td class="hauptlink"><a href="/messi/profil/spieler/28003">Messi</a></td></tr>
        </tbody></table>
        """
        mock_soup.return_value = BeautifulSoup(html, "html.parser")
        result = search_player_url("messi")
        assert result is not None
        assert "messi" in result.lower()

    @patch("src.collectors.transfermarkt_scraper._get_soup")
    def test_returns_none_when_not_found(self, mock_soup):
        from bs4 import BeautifulSoup
        from src.collectors.transfermarkt_scraper import search_player_url

        mock_soup.return_value = BeautifulSoup("<html></html>", "html.parser")
        result = search_player_url("nonexistent")
        assert result is None

    @patch("src.collectors.transfermarkt_scraper._get_soup")
    def test_returns_none_on_network_error(self, mock_soup):
        from src.collectors.transfermarkt_scraper import search_player_url

        mock_soup.side_effect = Exception("timeout")
        result = search_player_url("messi")
        assert result is None


@pytest.mark.unit
class TestScrapePlayerProfile:
    @patch("src.collectors.transfermarkt_scraper._get_soup")
    def test_returns_dict_with_full_name(self, mock_soup):
        from bs4 import BeautifulSoup
        from src.collectors.transfermarkt_scraper import scrape_player_profile

        html = """
        <html><body>
          <h1><strong>Lionel Messi</strong></h1>
          <div class="info-table__content">Full name</div>
          <div class="info-table__content">Lionel Andrés Messi</div>
        </body></html>
        """
        mock_soup.return_value = BeautifulSoup(html, "html.parser")
        result = scrape_player_profile("http://fake.url")
        assert result is not None
        assert "full_name" in result

    @patch("src.collectors.transfermarkt_scraper._get_soup")
    def test_returns_none_when_no_name_found(self, mock_soup):
        from bs4 import BeautifulSoup
        from src.collectors.transfermarkt_scraper import scrape_player_profile

        mock_soup.return_value = BeautifulSoup("<html><body></body></html>", "html.parser")
        result = scrape_player_profile("http://fake.url")
        assert result is None

    @patch("src.collectors.transfermarkt_scraper._get_soup")
    def test_returns_none_on_network_error(self, mock_soup):
        from src.collectors.transfermarkt_scraper import scrape_player_profile

        mock_soup.side_effect = Exception("network")
        result = scrape_player_profile("http://fake.url")
        assert result is None


@pytest.mark.unit
class TestScrapeCareerStats:
    @patch("src.collectors.transfermarkt_scraper._get_soup")
    def test_returns_empty_tuple_when_no_table(self, mock_soup):
        from bs4 import BeautifulSoup
        from src.collectors.transfermarkt_scraper import scrape_career_stats

        mock_soup.return_value = BeautifulSoup("<html><body></body></html>", "html.parser")
        result = scrape_career_stats("http://fake.url")
        assert result == ()

    @patch("src.collectors.transfermarkt_scraper._get_soup")
    def test_returns_empty_tuple_on_network_error(self, mock_soup):
        from src.collectors.transfermarkt_scraper import scrape_career_stats

        mock_soup.side_effect = Exception("network")
        result = scrape_career_stats("http://fake.url")
        assert result == ()

    @patch("src.collectors.transfermarkt_scraper._get_soup")
    def test_parses_season_rows(self, mock_soup):
        from bs4 import BeautifulSoup
        from src.collectors.transfermarkt_scraper import scrape_career_stats

        html = """
        <table class="items"><tbody>
          <tr>
            <td>2023-2024</td><td></td><td></td><td></td>
            <td>50</td><td>44</td><td>12</td>
            <td><a href="/miami/verein/123">Inter Miami</a></td>
          </tr>
        </tbody></table>
        """
        mock_soup.return_value = BeautifulSoup(html, "html.parser")
        result = scrape_career_stats("http://fake.url")
        assert isinstance(result, tuple)


@pytest.mark.unit
class TestScrapeInjuries:
    @patch("src.collectors.transfermarkt_scraper._get_soup")
    def test_returns_empty_tuple_when_no_rows(self, mock_soup):
        from bs4 import BeautifulSoup
        from src.collectors.transfermarkt_scraper import scrape_injuries

        mock_soup.return_value = BeautifulSoup("<html><body></body></html>", "html.parser")
        result = scrape_injuries("http://fake.url/profil/spieler/1")
        assert result == ()

    @patch("src.collectors.transfermarkt_scraper._get_soup")
    def test_returns_empty_tuple_on_network_error(self, mock_soup):
        from src.collectors.transfermarkt_scraper import scrape_injuries

        mock_soup.side_effect = Exception("network")
        result = scrape_injuries("http://fake.url")
        assert result == ()

    @patch("src.collectors.transfermarkt_scraper._get_soup")
    def test_parses_injury_rows(self, mock_soup):
        from bs4 import BeautifulSoup
        from src.collectors.transfermarkt_scraper import scrape_injuries
        from src.models.player import Injury

        html = """
        <table class="items"><tbody>
          <tr>
            <td>2023-2024</td><td>Hamstring</td>
            <td>2024-01-10</td><td>2024-02-05</td>
            <td>26</td><td>3</td>
          </tr>
        </tbody></table>
        """
        mock_soup.return_value = BeautifulSoup(html, "html.parser")
        result = scrape_injuries("http://fake.url/profil/spieler/1")
        assert isinstance(result, tuple)
        assert len(result) == 1
        assert isinstance(result[0], Injury)
        assert result[0].injury_type == "Hamstring"


@pytest.mark.unit
class TestParseHelpers:
    """Tests for internal parse helpers."""

    def test_parse_goals_extracts_number(self):
        from src.collectors.transfermarkt_scraper import _parse_goals

        assert _parse_goals("42 goals") == 42
        assert _parse_goals("0") == 0
        assert _parse_goals("no number") == 0

    def test_parse_date_slash_format(self):
        from src.collectors.transfermarkt_scraper import _parse_date

        assert _parse_date("24/06/1987") == "1987-06-24"

    def test_parse_date_dot_format(self):
        from src.collectors.transfermarkt_scraper import _parse_date

        assert _parse_date("24.06.1987") == "1987-06-24"

    def test_parse_date_passthrough_unknown_format(self):
        from src.collectors.transfermarkt_scraper import _parse_date

        assert _parse_date("unknown") == "unknown"
