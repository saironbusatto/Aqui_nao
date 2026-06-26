from __future__ import annotations

from src.models.player import Player
from src.models.comparison import (
    AgeComparison,
    GoalProjection,
    InjuryComparison,
    PlayerComparison,
    PlayingTimeComparison,
    TeamComparison,
)
from src.services.projection import calculate_projection


def _build_age_comparison(p1: Player, p2: Player, age: int) -> AgeComparison:
    s1 = p1.seasons_at_age(age)
    s2 = p2.seasons_at_age(age)
    return AgeComparison(
        age=age,
        player1_goals=sum(s.goals for s in s1),
        player2_goals=sum(s.goals for s in s2),
        player1_appearances=sum(s.appearances for s in s1),
        player2_appearances=sum(s.appearances for s in s2),
        player1_minutes=sum(s.minutes_played for s in s1),
        player2_minutes=sum(s.minutes_played for s in s2),
    )


def _build_team_comparison(p1: Player, p2: Player, team: str) -> TeamComparison:
    return TeamComparison(
        team=team,
        player1_goals=p1.goals_by_team(team),
        player2_goals=p2.goals_by_team(team),
    )


def _build_injury_comparison(p1: Player, p2: Player) -> InjuryComparison:
    return InjuryComparison(
        player1_total_injuries=p1.total_injuries,
        player2_total_injuries=p2.total_injuries,
        player1_days_injured=p1.total_days_injured,
        player2_days_injured=p2.total_days_injured,
        player1_games_missed=p1.total_games_injured,
        player2_games_missed=p2.total_games_injured,
    )


def _build_playing_time_comparison(p1: Player, p2: Player) -> PlayingTimeComparison:
    p1_starts = sum(s.starts for s in p1.career_seasons)
    p2_starts = sum(s.starts for s in p2.career_seasons)
    return PlayingTimeComparison(
        player1_total_minutes=p1.total_minutes,
        player2_total_minutes=p2.total_minutes,
        player1_starts=p1_starts,
        player2_starts=p2_starts,
        player1_bench_appearances=p1.total_appearances - p1_starts,
        player2_bench_appearances=p2.total_appearances - p2_starts,
    )


def compare_players(p1: Player, p2: Player) -> PlayerComparison:
    p1_ages = {s.age for s in p1.career_seasons}
    p2_ages = {s.age for s in p2.career_seasons}
    shared_ages = sorted(p1_ages & p2_ages)
    age_comparisons = tuple(_build_age_comparison(p1, p2, a) for a in shared_ages)

    p1_teams = set(p1.teams_played)
    p2_teams = set(p2.teams_played)
    shared_teams = sorted(p1_teams & p2_teams)
    team_comparisons = tuple(_build_team_comparison(p1, p2, t) for t in shared_teams)

    return PlayerComparison(
        player1=p1,
        player2=p2,
        age_comparisons=age_comparisons,
        team_comparisons=team_comparisons,
        player1_projection=calculate_projection(p1),
        player2_projection=calculate_projection(p2),
        injury_comparison=_build_injury_comparison(p1, p2),
        playing_time_comparison=_build_playing_time_comparison(p1, p2),
    )


def compare_at_age(p1: Player, p2: Player, age: int) -> AgeComparison:
    return _build_age_comparison(p1, p2, age)


def compare_by_team(p1: Player, p2: Player, team: str) -> TeamComparison:
    return _build_team_comparison(p1, p2, team)
