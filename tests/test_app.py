import pytest
from unittest.mock import patch, MagicMock

from src.models.player import Player, SeasonStats, Injury
from src.models.comparison import PlayerComparison
from src.app import create_app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-secret-key")
    app = create_app()
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def sample_player():
    return Player(
        name="Messi",
        full_name="Lionel Andrés Messi Cuccittini",
        date_of_birth="1987-06-24",
        nationality="Argentina",
        position="Forward",
        height_cm=170.0,
        current_team="Inter Miami",
        market_value="€35M",
        career_seasons=(
            SeasonStats(season="2004-2005", team="Barcelona", age=17, appearances=9, starts=4, minutes_played=456, goals=1, assists=1, yellow_cards=0, red_cards=0),
            SeasonStats(season="2009-2010", team="Barcelona", age=22, appearances=47, starts=45, minutes_played=4100, goals=47, assists=12, yellow_cards=3, red_cards=0),
            SeasonStats(season="2011-2012", team="Barcelona", age=24, appearances=55, starts=52, minutes_played=4800, goals=73, assists=30, yellow_cards=4, red_cards=0),
            SeasonStats(season="2023-2024", team="Inter Miami", age=36, appearances=15, starts=14, minutes_played=1200, goals=11, assists=5, yellow_cards=1, red_cards=0),
        ),
        injuries=(
            Injury(season="2013-2014", injury_type="Hamstring", date_from="2013-11-10", date_until="2013-12-03", days_missed=23, games_missed=4),
        ),
        world_cup_goals=13,
        world_cup_appearances=26,
    )


@pytest.fixture
def sample_player_2():
    return Player(
        name="Ronaldo",
        full_name="Cristiano Ronaldo dos Santos Aveiro",
        date_of_birth="1985-02-05",
        nationality="Portugal",
        position="Forward",
        height_cm=187.0,
        current_team="Al Nassr",
        market_value="€15M",
        career_seasons=(
            SeasonStats(season="2004-2005", team="Manchester United", age=19, appearances=29, starts=20, minutes_played=2100, goals=6, assists=4, yellow_cards=5, red_cards=1),
            SeasonStats(season="2007-2008", team="Manchester United", age=22, appearances=45, starts=42, minutes_played=3800, goals=32, assists=12, yellow_cards=5, red_cards=0),
            SeasonStats(season="2010-2011", team="Real Madrid", age=25, appearances=47, starts=45, minutes_played=4100, goals=53, assists=18, yellow_cards=2, red_cards=0),
            SeasonStats(season="2023-2024", team="Al Nassr", age=38, appearances=20, starts=19, minutes_played=1700, goals=15, assists=3, yellow_cards=2, red_cards=0),
        ),
        injuries=(),
        world_cup_goals=8,
        world_cup_appearances=22,
    )


# ===========================================================================
# Home page tests
# ===========================================================================

class TestHomePage:
    """Tests for GET / route."""

    @pytest.mark.integration
    def test_home_returns_200(self, client):
        response = client.get("/")
        assert response.status_code == 200

    @pytest.mark.integration
    def test_home_returns_html(self, client):
        response = client.get("/")
        assert response.content_type == "text/html"

    @pytest.mark.integration
    def test_home_contains_form(self, client):
        response = client.get("/")
        data = response.data.decode()
        assert "<form" in data.lower()

    @pytest.mark.integration
    def test_home_has_player_input_fields(self, client):
        response = client.get("/")
        data = response.data.decode()
        assert "player" in data.lower() or "name" in data.lower()

    @pytest.mark.integration
    def test_home_has_submit_button(self, client):
        response = client.get("/")
        data = response.data.decode()
        assert "submit" in data.lower() or "compare" in data.lower() or "type=\"submit\"" in data.lower()


# ===========================================================================
# Compare endpoint tests
# ===========================================================================

class TestCompareEndpoint:
    """Tests for POST /compare route."""

    @pytest.mark.integration
    def test_compare_post_with_valid_players(self, client, sample_player, sample_player_2):
        response = client.post("/compare", data={
            "player1": "Messi",
            "player2": "Ronaldo",
        })
        assert response.status_code == 302
        assert "p1=Messi" in response.headers["Location"]
        assert "p2=Ronaldo" in response.headers["Location"]

    @pytest.mark.integration
    def test_compare_returns_html(self, client, sample_player, sample_player_2):
        with patch("src.app.search_player") as mock_search:
            mock_search.side_effect = [sample_player, sample_player_2]
            response = client.post("/compare", data={
                "player1": "Messi",
                "player2": "Ronaldo",
            })
            assert "text/html" in response.content_type

    @pytest.mark.integration
    def test_compare_contains_player_names(self, client, sample_player, sample_player_2):
        with patch("src.app.search_player") as mock_search:
            mock_search.side_effect = [sample_player, sample_player_2]
            response = client.post("/compare", data={
                "player1": "Messi",
                "player2": "Ronaldo",
            })
            data = response.data.decode()
            assert "Messi" in data
            assert "Ronaldo" in data

    @pytest.mark.integration
    def test_compare_empty_player1_returns_error(self, client):
        response = client.post("/compare", data={
            "player1": "",
            "player2": "Ronaldo",
        })
        assert response.status_code in (400, 422)

    @pytest.mark.integration
    def test_compare_empty_player2_returns_error(self, client):
        response = client.post("/compare", data={
            "player1": "Messi",
            "player2": "",
        })
        assert response.status_code in (400, 422)

    @pytest.mark.integration
    def test_compare_both_empty_returns_error(self, client):
        response = client.post("/compare", data={
            "player1": "",
            "player2": "",
        })
        assert response.status_code in (400, 422)

    @pytest.mark.integration
    def test_compare_player_not_found(self, client):
        with patch("src.app.search_player") as mock_search:
            mock_search.side_effect = ValueError("Player not found: XYZ")
            response = client.get("/compare", query_string={"p1": "XYZ", "p2": "Messi"})
            assert response.status_code in (404, 400)

    @pytest.mark.integration
    def test_compare_no_data_returns_error(self, client):
        response = client.post("/compare", data={})
        assert response.status_code in (400, 422)

    @pytest.mark.integration
    def test_compare_get_without_params_shows_home(self, client):
        response = client.get("/compare")
        assert response.status_code == 200


# ===========================================================================
# API player search endpoint tests
# ===========================================================================

class TestPlayerSearchAPI:
    """Tests for GET /api/player/<name> route."""

    @pytest.mark.integration
    def test_api_player_returns_200(self, client, sample_player):
        with patch("src.app.search_player") as mock_search:
            mock_search.return_value = sample_player
            response = client.get("/api/player/Messi")
            assert response.status_code == 200

    @pytest.mark.integration
    def test_api_player_returns_json(self, client, sample_player):
        with patch("src.app.search_player") as mock_search:
            mock_search.return_value = sample_player
            response = client.get("/api/player/Messi")
            assert response.content_type == "application/json"

    @pytest.mark.integration
    def test_api_player_json_has_name(self, client, sample_player):
        with patch("src.app.search_player") as mock_search:
            mock_search.return_value = sample_player
            response = client.get("/api/player/Messi")
            data = response.get_json()
            assert data["name"] == "Messi"

    @pytest.mark.integration
    def test_api_player_json_has_key_fields(self, client, sample_player):
        with patch("src.app.search_player") as mock_search:
            mock_search.return_value = sample_player
            response = client.get("/api/player/Messi")
            data = response.get_json()
            required_keys = {"name", "full_name", "nationality", "position"}
            assert required_keys.issubset(data.keys())

    @pytest.mark.integration
    def test_api_player_not_found(self, client):
        with patch("src.app.search_player") as mock_search:
            mock_search.side_effect = ValueError("Player not found: Unknown")
            response = client.get("/api/player/Unknown")
            assert response.status_code == 404

    @pytest.mark.integration
    def test_api_player_not_found_returns_json(self, client):
        with patch("src.app.search_player") as mock_search:
            mock_search.side_effect = ValueError("Player not found: Unknown")
            response = client.get("/api/player/Unknown")
            assert response.content_type == "application/json"

    @pytest.mark.integration
    def test_api_player_not_found_has_error_field(self, client):
        with patch("src.app.search_player") as mock_search:
            mock_search.side_effect = ValueError("Player not found: Unknown")
            response = client.get("/api/player/Unknown")
            data = response.get_json()
            assert "error" in data

    @pytest.mark.integration
    def test_api_player_lowercase_name(self, client, sample_player):
        with patch("src.app.search_player") as mock_search:
            mock_search.return_value = sample_player
            response = client.get("/api/player/messi")
            assert response.status_code == 200


# ===========================================================================
# Error handling tests
# ===========================================================================

class TestErrorHandling:
    """Tests for general error handling across the app."""

    @pytest.mark.integration
    def test_404_for_unknown_route(self, client):
        response = client.get("/nonexistent")
        assert response.status_code == 404

    @pytest.mark.integration
    def test_api_compare_not_found(self, client):
        with patch("src.app.search_player") as mock_search:
            mock_search.side_effect = ValueError("Player not found")
            response = client.get("/api/player/???")
            assert response.status_code in (404, 200)

    @pytest.mark.integration
    def test_compare_handles_internal_error(self, client, sample_player, sample_player_2):
        with patch("src.app.search_player") as mock_search, \
             patch("src.app.compare_players") as mock_compare:
            mock_search.side_effect = [sample_player, sample_player_2]
            mock_compare.side_effect = RuntimeError("Internal error")
            response = client.get("/compare", query_string={"p1": "Messi", "p2": "Ronaldo"})
            assert response.status_code in (500, 400)

    @pytest.mark.integration
    def test_post_to_nonexistent_route(self, client):
        response = client.post("/does-not-exist", data={"key": "value"})
        assert response.status_code in (404, 405)
