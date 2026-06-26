"""TDD tests for football data collectors.

These tests define the expected interface for three collectors that have
not been implemented yet. They will FAIL in the RED phase and PASS once
the collectors are implemented.

All external API calls are mocked — no real network requests.
"""

from unittest.mock import MagicMock, patch

import pytest

from src.models.player import Injury, Player, SeasonStats


# ---------------------------------------------------------------------------
# FBref Collector
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestFbrefCollector:
    """Tests for src.collectors.fbref_collector."""

    @patch("src.collectors.fbref_collector.soccerdata")
    def test_search_player_returns_matches(self, mock_soccerdata):
        """search_player should return a list of matching player dicts."""
        from src.collectors.fbref_collector import search_player

        mock_fb = MagicMock()
        mock_soccerdata.FBref.return_value = mock_fb
        mock_fb.players.return_value = [
            {"player_id": "abc123", "name": "Lionel Messi", "team": "Inter Miami"},
        ]

        results = search_player("Messi")

        assert isinstance(results, list)
        assert len(results) >= 1
        assert results[0]["name"] == "Lionel Messi"
        mock_fb.players.assert_called_once_with("Messi")

    @patch("src.collectors.fbref_collector.soccerdata")
    def test_search_player_no_results(self, mock_soccerdata):
        """search_player returns empty list when no players match."""
        from src.collectors.fbref_collector import search_player

        mock_fb = MagicMock()
        mock_soccerdata.FBref.return_value = mock_fb
        mock_fb.players.return_value = []

        results = search_player("ZzzNonexistent99")

        assert results == []

    @patch("src.collectors.fbref_collector.soccerdata")
    def test_get_player_stats_returns_player_instance(self, mock_soccerdata):
        """get_player_stats should return a Player dataclass."""
        from src.collectors.fbref_collector import get_player_stats

        mock_fb = MagicMock()
        mock_soccerdata.FBref.return_value = mock_fb
        mock_fb.get_player_stats.return_value = {
            "full_name": "Lionel Andrés Messi Cuccittini",
            "date_of_birth": "1987-06-24",
            "nationality": "Argentina",
            "position": "Forward",
            "height_cm": 170.0,
            "current_team": "Inter Miami CF",
            "career_seasons": [
                SeasonStats(
                    season="2022-2023",
                    team="Paris Saint-Germain",
                    age=35,
                    appearances=32,
                    starts=29,
                    minutes_played=2520,
                    goals=16,
                    assists=16,
                    yellow_cards=2,
                    red_cards=0,
                ),
            ],
        }

        player = get_player_stats("abc123")

        assert isinstance(player, Player)
        assert player.name == "Lionel Messi"
        assert player.nationality == "Argentina"
        assert player.position == "Forward"
        assert len(player.career_seasons) == 1

    @patch("src.collectors.fbref_collector.soccerdata")
    def test_get_player_stats_raises_on_invalid_id(self, mock_soccerdata):
        """get_player_stats raises ValueError for unknown player IDs."""
        from src.collectors.fbref_collector import get_player_stats

        mock_fb = MagicMock()
        mock_soccerdata.FBref.return_value = mock_fb
        mock_fb.get_player_stats.return_value = None

        with pytest.raises(ValueError, match="Player not found"):
            get_player_stats("invalid_id_xyz")

    @patch("src.collectors.fbref_collector.soccerdata")
    def test_get_player_stats_handles_network_error(self, mock_soccerdata):
        """get_player_stats raises ConnectionError on network failures."""
        from src.collectors.fbref_collector import get_player_stats

        mock_fb = MagicMock()
        mock_soccerdata.FBref.return_value = mock_fb
        mock_fb.get_player_stats.side_effect = ConnectionError("Timeout")

        with pytest.raises(ConnectionError, match="Timeout"):
            get_player_stats("abc123")


# ---------------------------------------------------------------------------
# Transfermarkt Collector
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestTransfermarktCollector:
    """Tests for src.collectors.transfermarkt_collector."""

    @patch("src.collectors.transfermarkt_collector.requests")
    @patch("src.collectors.transfermarkt_collector.BeautifulSoup")
    def test_get_player_profile_returns_dict(self, mock_bs, mock_requests):
        """get_player_profile returns a dict with bio and injury data."""
        from src.collectors.transfermarkt_collector import get_player_profile

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "<html></html>"
        mock_requests.get.return_value = mock_resp

        mock_soup = MagicMock()
        mock_bs.return_value = mock_soup
        mock_soup.select.return_value = [
            MagicMock(text="Lionel Messi"),
            MagicMock(text="1987-06-24"),
            MagicMock(text="Argentina"),
        ]

        result = get_player_profile("Lionel Messi")

        assert isinstance(result, dict)
        assert "name" in result
        assert "date_of_birth" in result
        assert "nationality" in result
        mock_requests.get.assert_called_once()

    @patch("src.collectors.transfermarkt_collector.requests")
    def test_get_player_profile_raises_on_404(self, mock_requests):
        """get_player_profile raises ValueError when player is not found."""
        from src.collectors.transfermarkt_collector import get_player_profile

        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_requests.get.return_value = mock_resp

        with pytest.raises(ValueError, match="not found"):
            get_player_profile("FakePlayer999")

    @patch("src.collectors.transfermarkt_collector.requests")
    def test_get_player_profile_raises_on_network_error(self, mock_requests):
        """get_player_profile raises ConnectionError on network failures."""
        from src.collectors.transfermarkt_collector import get_player_profile

        mock_requests.get.side_effect = ConnectionError("DNS resolution failed")

        with pytest.raises(ConnectionError):
            get_player_profile("Messi")

    @patch("src.collectors.transfermarkt_collector.requests")
    @patch("src.collectors.transfermarkt_collector.BeautifulSoup")
    def test_get_injury_history_returns_list(self, mock_bs, mock_requests):
        """get_injury_history returns a list of Injury dataclasses."""
        from src.collectors.transfermarkt_collector import get_injury_history

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "<html></html>"
        mock_requests.get.return_value = mock_resp

        mock_soup = MagicMock()
        mock_bs.return_value = mock_soup
        mock_soup.select.return_value = [
            MagicMock(text="2022/2023"),
            MagicMock(text="Knee injury"),
            MagicMock(text="Sep 10, 2022"),
            MagicMock(text="Oct 5, 2022"),
            MagicMock(text="25"),
            MagicMock(text="3"),
        ]

        injuries = get_injury_history("abc123")

        assert isinstance(injuries, list)
        assert len(injuries) >= 1
        assert isinstance(injuries[0], Injury)
        assert injuries[0].season == "2022/2023"
        assert injuries[0].injury_type == "Knee injury"

    @patch("src.collectors.transfermarkt_collector.requests")
    def test_get_injury_history_empty_when_no_injuries(self, mock_requests):
        """get_injury_history returns empty list for injury-free players."""
        from src.collectors.transfermarkt_collector import get_injury_history

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "<html><table></table></html>"
        mock_requests.get.return_value = mock_resp

        with patch("src.collectors.transfermarkt_collector.BeautifulSoup") as mock_bs:
            mock_soup = MagicMock()
            mock_bs.return_value = mock_soup
            mock_soup.select.return_value = []

            injuries = get_injury_history("abc123")

        assert injuries == []

    @patch("src.collectors.transfermarkt_collector.requests")
    def test_get_injury_history_raises_on_invalid_player(self, mock_requests):
        """get_injury_history raises ValueError for invalid player IDs."""
        from src.collectors.transfermarkt_collector import get_injury_history

        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_requests.get.return_value = mock_resp

        with pytest.raises(ValueError, match="Player not found"):
            get_injury_history("nonexistent_id")


# ---------------------------------------------------------------------------
# Football-Data.org Collector
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestFootballDataCollector:
    """Tests for src.collectors.footballdata_collector."""

    @patch("src.collectors.footballdata_collector.requests")
    def test_get_world_cup_stats_returns_dict(self, mock_requests):
        """get_world_cup_stats returns a dict with WC goals and appearances."""
        from src.collectors.footballdata_collector import get_world_cup_stats

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "player": "Lionel Messi",
            "world_cup_goals": 13,
            "world_cup_appearances": 26,
            "world_cups_played": [2006, 2010, 2014, 2018, 2022],
        }
        mock_requests.get.return_value = mock_resp

        result = get_world_cup_stats("Lionel Messi")

        assert isinstance(result, dict)
        assert result["world_cup_goals"] == 13
        assert result["world_cup_appearances"] == 26
        assert 2022 in result["world_cups_played"]

    @patch("src.collectors.footballdata_collector.requests")
    def test_get_world_cup_stats_raises_on_player_not_found(self, mock_requests):
        """get_world_cup_stats raises ValueError when player is unknown."""
        from src.collectors.footballdata_collector import get_world_cup_stats

        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_requests.get.return_value = mock_resp

        with pytest.raises(ValueError, match="not found"):
            get_world_cup_stats("FakePlayerXYZ")

    @patch("src.collectors.footballdata_collector.requests")
    def test_get_world_cup_stats_raises_on_api_key_error(self, mock_requests):
        """get_world_cup_stats raises PermissionError for invalid API keys."""
        from src.collectors.footballdata_collector import get_world_cup_stats

        mock_resp = MagicMock()
        mock_resp.status_code = 403
        mock_resp.json.return_value = {"message": "Invalid API key"}
        mock_requests.get.return_value = mock_resp

        with pytest.raises(PermissionError, match="API key"):
            get_world_cup_stats("Messi")

    @patch("src.collectors.footballdata_collector.requests")
    def test_get_world_cup_stats_raises_on_network_error(self, mock_requests):
        """get_world_cup_stats raises ConnectionError on network failures."""
        from src.collectors.footballdata_collector import get_world_cup_stats

        mock_requests.get.side_effect = ConnectionError("Service unavailable")

        with pytest.raises(ConnectionError):
            get_world_cup_stats("Messi")

    @patch("src.collectors.footballdata_collector.requests")
    def test_get_world_cup_stats_returns_zero_for_no_wc(self, mock_requests):
        """Players with no WC history get zeros."""
        from src.collectors.footballdata_collector import get_world_cup_stats

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "player": "Some New Player",
            "world_cup_goals": 0,
            "world_cup_appearances": 0,
            "world_cups_played": [],
        }
        mock_requests.get.return_value = mock_resp

        result = get_world_cup_stats("Some New Player")

        assert result["world_cup_goals"] == 0
        assert result["world_cup_appearances"] == 0
        assert result["world_cups_played"] == []

    @patch("src.collectors.footballdata_collector.requests")
    def test_get_world_cup_stats_uses_correct_api_key(self, mock_requests):
        """get_world_cup_stats sends the X-Auth-Token header."""
        from src.collectors.footballdata_collector import get_world_cup_stats

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"player": "Messi", "world_cup_goals": 13}
        mock_requests.get.return_value = mock_resp

        get_world_cup_stats("Messi")

        _, kwargs = mock_requests.get.call_args
        assert "headers" in kwargs
        assert "X-Auth-Token" in kwargs["headers"]


# ---------------------------------------------------------------------------
# Collector integration: models round-trip
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCollectorModelIntegration:
    """Verify collectors produce dataclass instances that work correctly."""

    @patch("src.collectors.fbref_collector.soccerdata")
    def test_fbref_player_has_computed_properties(self, mock_soccerdata):
        """Player from FBref collector exposes totals via properties."""
        from src.collectors.fbref_collector import get_player_stats

        mock_fb = MagicMock()
        mock_soccerdata.FBref.return_value = mock_fb
        mock_fb.get_player_stats.return_value = {
            "full_name": "Test Player",
            "date_of_birth": "1990-01-01",
            "nationality": "Brazil",
            "position": "Midfielder",
            "career_seasons": [
                SeasonStats("2021-2022", "Team A", 31, 30, 28, 2500, 10, 5, 3, 0),
                SeasonStats("2022-2023", "Team B", 32, 35, 30, 2700, 15, 8, 2, 0),
            ],
        }

        player = get_player_stats("test123")

        assert player.total_goals == 25
        assert player.total_assists == 13
        assert player.total_appearances == 65
        assert player.teams_played == ("Team A", "Team B")

    @patch("src.collectors.transfermarkt_collector.requests")
    @patch("src.collectors.transfermarkt_collector.BeautifulSoup")
    def test_injury_history_is_frozen(self, mock_bs, mock_requests):
        """Injury dataclasses from collector are immutable."""
        from src.collectors.transfermarkt_collector import get_injury_history

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "<html></html>"
        mock_requests.get.return_value = mock_resp

        mock_soup = MagicMock()
        mock_bs.return_value = mock_soup
        mock_soup.select.return_value = [
            MagicMock(text="2023/2024"),
            MagicMock(text="Ankle sprain"),
            MagicMock(text="Jan 5, 2024"),
            MagicMock(text="Feb 10, 2024"),
            MagicMock(text="36"),
            MagicMock(text="4"),
        ]

        injuries = get_injury_history("test123")
        injury = injuries[0]

        with pytest.raises(AttributeError):
            injury.injury_type = "changed"  # type: ignore[misc]
