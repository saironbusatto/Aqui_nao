import pytest
from unittest.mock import patch, MagicMock

from src.models.player import Player, SeasonStats, Injury
from src.models.comparison import (
    PlayerComparison,
    AgeComparison,
    TeamComparison,
    GoalProjection,
    InjuryComparison,
    PlayingTimeComparison,
)
from src.services.comparison_engine import (
    compare_players,
    compare_at_age,
    compare_by_team,
)
from src.services.projection import (
    calculate_projection,
    project_goals_at_age,
)
from src.services.report import (
    generate_comparison_chart,
    generate_report,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def messi() -> Player:
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
            SeasonStats(season="2005-2006", team="Barcelona", age=18, appearances=25, starts=18, minutes_played=1900, goals=8, assists=4, yellow_cards=3, red_cards=0),
            SeasonStats(season="2006-2007", team="Barcelona", age=19, appearances=36, starts=28, minutes_played=2700, goals=14, assists=7, yellow_cards=5, red_cards=0),
            SeasonStats(season="2007-2008", team="Barcelona", age=20, appearances=40, starts=35, minutes_played=3200, goals=16, assists=12, yellow_cards=4, red_cards=1),
            SeasonStats(season="2008-2009", team="Barcelona", age=21, appearances=45, starts=42, minutes_played=3800, goals=38, assists=18, yellow_cards=6, red_cards=0),
            SeasonStats(season="2009-2010", team="Barcelona", age=22, appearances=47, starts=45, minutes_played=4100, goals=47, assists=12, yellow_cards=3, red_cards=0),
            SeasonStats(season="2010-2011", team="Barcelona", age=23, appearances=50, starts=48, minutes_played=4400, goals=53, assists=24, yellow_cards=2, red_cards=0),
            SeasonStats(season="2011-2012", team="Barcelona", age=24, appearances=55, starts=52, minutes_played=4800, goals=73, assists=30, yellow_cards=4, red_cards=0),
            SeasonStats(season="2012-2013", team="Barcelona", age=25, appearances=50, starts=47, minutes_played=4300, goals=60, assists=16, yellow_cards=5, red_cards=0),
            SeasonStats(season="2023-2024", team="Inter Miami", age=36, appearances=15, starts=14, minutes_played=1200, goals=11, assists=5, yellow_cards=1, red_cards=0),
        ),
        injuries=(
            Injury(season="2013-2014", injury_type="Hamstring", date_from="2013-11-10", date_until="2013-12-03", days_missed=23, games_missed=4),
            Injury(season="2015-2016", injury_type="Knee", date_from="2016-04-02", date_until="2016-04-20", days_missed=18, games_missed=3),
        ),
        world_cup_goals=13,
        world_cup_appearances=26,
    )


@pytest.fixture
def ronaldo() -> Player:
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
            SeasonStats(season="2005-2006", team="Manchester United", age=20, appearances=33, starts=28, minutes_played=2600, goals=12, assists=6, yellow_cards=4, red_cards=1),
            SeasonStats(season="2006-2007", team="Manchester United", age=21, appearances=40, starts=35, minutes_played=3200, goals=17, assists=14, yellow_cards=3, red_cards=0),
            SeasonStats(season="2007-2008", team="Manchester United", age=22, appearances=45, starts=42, minutes_played=3800, goals=32, assists=12, yellow_cards=5, red_cards=0),
            SeasonStats(season="2008-2009", team="Manchester United", age=23, appearances=43, starts=40, minutes_played=3600, goals=26, assists=8, yellow_cards=4, red_cards=0),
            SeasonStats(season="2009-2010", team="Real Madrid", age=24, appearances=35, starts=30, minutes_played=2800, goals=26, assists=8, yellow_cards=3, red_cards=0),
            SeasonStats(season="2010-2011", team="Real Madrid", age=25, appearances=47, starts=45, minutes_played=4100, goals=53, assists=18, yellow_cards=2, red_cards=0),
            SeasonStats(season="2011-2012", team="Real Madrid", age=26, appearances=50, starts=48, minutes_played=4400, goals=60, assists=15, yellow_cards=3, red_cards=0),
            SeasonStats(season="2012-2013", team="Real Madrid", age=27, appearances=45, starts=42, minutes_played=3800, goals=55, assists=12, yellow_cards=2, red_cards=0),
            SeasonStats(season="2023-2024", team="Al Nassr", age=38, appearances=20, starts=19, minutes_played=1700, goals=15, assists=3, yellow_cards=2, red_cards=0),
        ),
        injuries=(
            Injury(season="2014-2015", injury_type="Knee", date_from="2014-09-15", date_until="2014-10-01", days_missed=16, games_missed=3),
        ),
        world_cup_goals=8,
        world_cup_appearances=22,
    )


@pytest.fixture
def neymar() -> Player:
    return Player(
        name="Neymar",
        full_name="Neymar da Silva Santos Júnior",
        date_of_birth="1992-02-05",
        nationality="Brazil",
        position="Forward",
        height_cm=175.0,
        current_team="Al Hilal",
        market_value="€60M",
        career_seasons=(
            SeasonStats(season="2011-2012", team="Santos", age=19, appearances=21, starts=20, minutes_played=1800, goals=13, assists=5, yellow_cards=2, red_cards=0),
            SeasonStats(season="2012-2013", team="Santos", age=20, appearances=23, starts=22, minutes_played=2000, goals=14, assists=3, yellow_cards=3, red_cards=0),
            SeasonStats(season="2013-2014", team="Barcelona", age=21, appearances=26, starts=22, minutes_played=2100, goals=9, assists=10, yellow_cards=4, red_cards=0),
            SeasonStats(season="2014-2015", team="Barcelona", age=22, appearances=40, starts=35, minutes_played=3100, goals=22, assists=9, yellow_cards=5, red_cards=1),
            SeasonStats(season="2015-2016", team="Barcelona", age=23, appearances=42, starts=38, minutes_played=3400, goals=31, assists=12, yellow_cards=3, red_cards=0),
        ),
        injuries=(
            Injury(season="2014-2015", injury_type="Fracture", date_from="2014-11-23", date_until="2014-12-10", days_missed=17, games_missed=3),
            Injury(season="2015-2016", injury_type="Metatarsal", date_from="2016-02-25", date_until="2016-04-15", days_missed=50, games_missed=7),
            Injury(season="2016-2017", injury_type="Hamstring", date_from="2016-10-15", date_until="2016-11-02", days_missed=18, games_missed=4),
        ),
        world_cup_goals=7,
        world_cup_appearances=12,
    )


@pytest.fixture
def messi_vs_ronaldo_comparison(messi: Player, ronaldo: Player) -> PlayerComparison:
    return PlayerComparison(player1=messi, player2=ronaldo)


# ===========================================================================
# comparison_engine tests
# ===========================================================================

class TestComparePlayers:
    """Tests for the full player comparison function."""

    @pytest.mark.unit
    def test_returns_player_comparison_instance(self, messi: Player, ronaldo: Player):
        result = compare_players(messi, ronaldo)
        assert isinstance(result, PlayerComparison)

    @pytest.mark.unit
    def test_comparison_preserves_player_references(self, messi: Player, ronaldo: Player):
        result = compare_players(messi, ronaldo)
        assert result.player1 is messi
        assert result.player2 is ronaldo

    @pytest.mark.unit
    def test_comparison_includes_age_comparisons(self, messi: Player, ronaldo: Player):
        result = compare_players(messi, ronaldo)
        assert len(result.age_comparisons) > 0
        for ac in result.age_comparisons:
            assert isinstance(ac, AgeComparison)

    @pytest.mark.unit
    def test_age_comparisons_cover_shared_ages(self, messi: Player, ronaldo: Player):
        result = compare_players(messi, ronaldo)
        shared_ages = {ac.age for ac in result.age_comparisons}
        p1_ages = {s.age for s in messi.career_seasons}
        p2_ages = {s.age for s in ronaldo.career_seasons}
        expected = p1_ages & p2_ages
        assert shared_ages == expected

    @pytest.mark.unit
    def test_comparison_includes_team_comparisons(self, messi: Player, ronaldo: Player):
        result = compare_players(messi, ronaldo)
        for tc in result.team_comparisons:
            assert isinstance(tc, TeamComparison)

    @pytest.mark.unit
    def test_team_comparisons_cover_shared_teams(self, messi: Player, ronaldo: Player):
        result = compare_players(messi, ronaldo)
        shared_teams = {tc.team for tc in result.team_comparisons}
        p1_teams = set(messi.teams_played)
        p2_teams = set(ronaldo.teams_played)
        expected = p1_teams & p2_teams
        assert shared_teams == expected

    @pytest.mark.unit
    def test_comparison_includes_projections(self, messi: Player, ronaldo: Player):
        result = compare_players(messi, ronaldo)
        assert result.player1_projection is not None
        assert result.player2_projection is not None
        assert isinstance(result.player1_projection, GoalProjection)
        assert isinstance(result.player2_projection, GoalProjection)

    @pytest.mark.unit
    def test_comparison_includes_injury_comparison(self, messi: Player, ronaldo: Player):
        result = compare_players(messi, ronaldo)
        assert result.injury_comparison is not None
        assert isinstance(result.injury_comparison, InjuryComparison)

    @pytest.mark.unit
    def test_comparison_includes_playing_time(self, messi: Player, ronaldo: Player):
        result = compare_players(messi, ronaldo)
        assert result.playing_time_comparison is not None
        assert isinstance(result.playing_time_comparison, PlayingTimeComparison)

    @pytest.mark.unit
    def test_compare_players_same_player(self, messi: Player):
        result = compare_players(messi, messi)
        assert result.player1 is result.player2
        assert result.player1.name == result.player2.name

    @pytest.mark.unit
    def test_injury_comparison_correct_totals(self, messi: Player, ronaldo: Player):
        result = compare_players(messi, ronaldo)
        ic = result.injury_comparison
        assert ic.player1_total_injuries == messi.total_injuries
        assert ic.player2_total_injuries == ronaldo.total_injuries
        assert ic.player1_days_injured == messi.total_days_injured
        assert ic.player2_days_injured == ronaldo.total_days_injured
        assert ic.player1_games_missed == messi.total_games_injured
        assert ic.player2_games_missed == ronaldo.total_games_injured

    @pytest.mark.unit
    def test_playing_time_comparison_correct_totals(self, messi: Player, ronaldo: Player):
        result = compare_players(messi, ronaldo)
        pt = result.playing_time_comparison
        assert pt.player1_total_minutes == messi.total_minutes
        assert pt.player2_total_minutes == ronaldo.total_minutes
        assert pt.player1_starts == sum(s.starts for s in messi.career_seasons)
        assert pt.player2_starts == sum(s.starts for s in ronaldo.career_seasons)


class TestCompareAtAge:
    """Tests for same-age comparison."""

    @pytest.mark.unit
    def test_returns_age_comparison(self, messi: Player, ronaldo: Player):
        result = compare_at_age(messi, ronaldo, age=21)
        assert isinstance(result, AgeComparison)

    @pytest.mark.unit
    def test_result_age_matches_request(self, messi: Player, ronaldo: Player):
        result = compare_at_age(messi, ronaldo, age=21)
        assert result.age == 21

    @pytest.mark.unit
    def test_goals_match_model_data(self, messi: Player, ronaldo: Player):
        result = compare_at_age(messi, ronaldo, age=21)
        assert result.player1_goals == messi.goals_at_age(21)
        assert result.player2_goals == ronaldo.goals_at_age(21)

    @pytest.mark.unit
    def test_appearances_match_model_data(self, messi: Player, ronaldo: Player):
        result = compare_at_age(messi, ronaldo, age=21)
        p1_app = sum(s.appearances for s in messi.seasons_at_age(21))
        p2_app = sum(s.appearances for s in ronaldo.seasons_at_age(21))
        assert result.player1_appearances == p1_app
        assert result.player2_appearances == p2_app

    @pytest.mark.unit
    def test_minutes_match_model_data(self, messi: Player, ronaldo: Player):
        result = compare_at_age(messi, ronaldo, age=21)
        p1_min = sum(s.minutes_played for s in messi.seasons_at_age(21))
        p2_min = sum(s.minutes_played for s in ronaldo.seasons_at_age(21))
        assert result.player1_minutes == p1_min
        assert result.player2_minutes == p2_min

    @pytest.mark.unit
    def test_age_no_data_returns_zeros(self, messi: Player, ronaldo: Player):
        result = compare_at_age(messi, ronaldo, age=5)
        assert result.player1_goals == 0
        assert result.player2_goals == 0
        assert result.player1_appearances == 0
        assert result.player2_appearances == 0

    @pytest.mark.unit
    def test_age_with_one_player_missing(self, messi: Player, ronaldo: Player):
        result = compare_at_age(messi, ronaldo, age=19)
        assert result.player1_goals == messi.goals_at_age(19)
        assert result.player2_goals == ronaldo.goals_at_age(19)


class TestCompareByTeam:
    """Tests for team-based comparison."""

    @pytest.mark.unit
    def test_returns_team_comparison(self, messi: Player, ronaldo: Player):
        result = compare_by_team(messi, ronaldo, team="Barcelona")
        assert isinstance(result, TeamComparison)

    @pytest.mark.unit
    def test_team_name_preserved(self, messi: Player, ronaldo: Player):
        result = compare_by_team(messi, ronaldo, team="Barcelona")
        assert result.team == "Barcelona"

    @pytest.mark.unit
    def test_goals_match_model_data(self, messi: Player, ronaldo: Player):
        result = compare_by_team(messi, ronaldo, team="Barcelona")
        assert result.player1_goals == messi.goals_by_team("Barcelona")
        assert result.player2_goals == ronaldo.goals_by_team("Barcelona")

    @pytest.mark.unit
    def test_team_neither_played(self, messi: Player, ronaldo: Player):
        result = compare_by_team(messi, ronaldo, team="Bayern Munich")
        assert result.player1_goals == 0
        assert result.player2_goals == 0

    @pytest.mark.unit
    def test_team_only_one_played(self, messi: Player, ronaldo: Player):
        result = compare_by_team(messi, ronaldo, team="Inter Miami")
        assert result.player1_goals == messi.goals_by_team("Inter Miami")
        assert result.player2_goals == 0

    @pytest.mark.unit
    def test_team_real_madrid(self, messi: Player, ronaldo: Player):
        result = compare_by_team(messi, ronaldo, team="Real Madrid")
        assert result.player1_goals == 0
        assert result.player2_goals == ronaldo.goals_by_team("Real Madrid")


# ===========================================================================
# projection tests
# ===========================================================================

class TestCalculateProjection:
    """Tests for goal projection calculation."""

    @pytest.mark.unit
    def test_returns_goal_projection(self, messi: Player):
        result = calculate_projection(messi)
        assert isinstance(result, GoalProjection)

    @pytest.mark.unit
    def test_projection_player_name(self, messi: Player):
        result = calculate_projection(messi)
        assert result.player_name == messi.name

    @pytest.mark.unit
    def test_projection_current_goals(self, messi: Player):
        result = calculate_projection(messi)
        assert result.current_goals == messi.total_goals

    @pytest.mark.unit
    def test_projection_avg_goals_positive(self, messi: Player):
        result = calculate_projection(messi)
        assert result.avg_goals_per_season > 0

    @pytest.mark.unit
    def test_projection_avg_goals_calculation(self, messi: Player):
        result = calculate_projection(messi)
        expected_avg = messi.total_goals / len(messi.career_seasons)
        assert result.avg_goals_per_season == pytest.approx(expected_avg, rel=1e-2)

    @pytest.mark.unit
    def test_projection_at_30(self, messi: Player):
        result = calculate_projection(messi)
        assert result.projected_goals_at_30 >= result.current_goals

    @pytest.mark.unit
    def test_projection_at_35_gte_30(self, messi: Player):
        result = calculate_projection(messi)
        assert result.projected_goals_at_35 >= result.projected_goals_at_30

    @pytest.mark.unit
    def test_projection_at_40_gte_35(self, messi: Player):
        result = calculate_projection(messi)
        assert result.projected_goals_at_40 >= result.projected_goals_at_35

    @pytest.mark.unit
    def test_projection_older_player(self, messi: Player):
        result = calculate_projection(messi)
        assert result.current_age == messi.age

    @pytest.mark.unit
    def test_projection_empty_seasons(self):
        player = Player(
            name="Newcomer",
            full_name="Test Player",
            date_of_birth="2000-01-01",
            nationality="Brazil",
            position="Midfielder",
            career_seasons=(),
        )
        result = calculate_projection(player)
        assert result.current_goals == 0
        assert result.avg_goals_per_season == 0.0
        assert result.projected_goals_at_30 == 0


class TestProjectGoalsAtAge:
    """Tests for specific-age goal projection."""

    @pytest.mark.unit
    def test_returns_int(self, messi: Player):
        result = project_goals_at_age(messi, target_age=30)
        assert isinstance(result, int)

    @pytest.mark.unit
    def test_project_past_age_returns_current(self, messi: Player):
        result = project_goals_at_age(messi, target_age=18)
        assert result >= 0

    @pytest.mark.unit
    def test_project_future_increases(self, messi: Player):
        result_30 = project_goals_at_age(messi, target_age=30)
        result_35 = project_goals_at_age(messi, target_age=35)
        assert result_35 >= result_30

    @pytest.mark.unit
    def test_project_no_seasons(self):
        player = Player(
            name="Rookie",
            full_name="Rookie Player",
            date_of_birth="2005-01-01",
            nationality="Portugal",
            position="Forward",
        )
        result = project_goals_at_age(player, target_age=25)
        assert result == 0


# ===========================================================================
# report tests
# ===========================================================================

class TestGenerateComparisonChart:
    """Tests for matplotlib chart generation."""

    @pytest.mark.unit
    def test_returns_string_path(self, messi: Player, ronaldo: Player, tmp_path):
        output = str(tmp_path / "chart.png")
        result = generate_comparison_chart(messi, ronaldo, output)
        assert isinstance(result, str)

    @pytest.mark.unit
    def test_chart_file_created(self, messi: Player, ronaldo: Player, tmp_path):
        output = str(tmp_path / "chart.png")
        result = generate_comparison_chart(messi, ronaldo, output)
        import os
        assert os.path.exists(result)

    @pytest.mark.unit
    def test_chart_file_is_png(self, messi: Player, ronaldo: Player, tmp_path):
        output = str(tmp_path / "chart.png")
        result = generate_comparison_chart(messi, ronaldo, output)
        assert result.endswith(".png")

    @pytest.mark.unit
    def test_chart_file_not_empty(self, messi: Player, ronaldo: Player, tmp_path):
        output = str(tmp_path / "chart.png")
        result = generate_comparison_chart(messi, ronaldo, output)
        import os
        assert os.path.getsize(result) > 0

    @pytest.mark.unit
    def test_chart_custom_filename(self, messi: Player, ronaldo: Player, tmp_path):
        output = str(tmp_path / "custom_chart.png")
        result = generate_comparison_chart(messi, ronaldo, output)
        assert result == output

    @pytest.mark.unit
    def test_chart_creates_parent_dirs(self, messi: Player, ronaldo: Player, tmp_path):
        output = str(tmp_path / "subdir" / "chart.png")
        result = generate_comparison_chart(messi, ronaldo, output)
        import os
        assert os.path.exists(result)


class TestGenerateReport:
    """Tests for text report generation."""

    @pytest.mark.unit
    def test_returns_string(self, messi_vs_ronaldo_comparison: PlayerComparison):
        result = generate_report(messi_vs_ronaldo_comparison)
        assert isinstance(result, str)

    @pytest.mark.unit
    def test_report_contains_both_names(self, messi_vs_ronaldo_comparison: PlayerComparison):
        result = generate_report(messi_vs_ronaldo_comparison)
        assert "Messi" in result
        assert "Ronaldo" in result

    @pytest.mark.unit
    def test_report_not_empty(self, messi_vs_ronaldo_comparison: PlayerComparison):
        result = generate_report(messi_vs_ronaldo_comparison)
        assert len(result) > 100

    @pytest.mark.unit
    def test_report_contains_goals_section(self, messi_vs_ronaldo_comparison: PlayerComparison):
        result = generate_report(messi_vs_ronaldo_comparison)
        lower = result.lower()
        assert "goal" in lower

    @pytest.mark.unit
    def test_report_contains_injury_section(self, messi_vs_ronaldo_comparison: PlayerComparison):
        result = generate_report(messi_vs_ronaldo_comparison)
        lower = result.lower()
        assert "injur" in lower

    @pytest.mark.unit
    def test_report_contains_playing_time(self, messi_vs_ronaldo_comparison: PlayerComparison):
        result = generate_report(messi_vs_ronaldo_comparison)
        lower = result.lower()
        assert "minute" in lower or "playing time" in lower or "start" in lower

    @pytest.mark.unit
    def test_report_with_minimal_comparison(self, messi: Player, ronaldo: Player):
        comp = PlayerComparison(player1=messi, player2=ronaldo)
        result = generate_report(comp)
        assert isinstance(result, str)
        assert len(result) > 0
