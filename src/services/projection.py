from __future__ import annotations

from src.models.player import Player
from src.models.comparison import GoalProjection


def calculate_projection(player: Player) -> GoalProjection:
    current_goals = player.total_goals
    num_seasons = len(player.career_seasons)
    avg = current_goals / num_seasons if num_seasons > 0 else 0.0

    current_age = player.age

    def _project_at(target: int) -> int:
        if target <= current_age or num_seasons == 0:
            return current_goals
        remaining = target - current_age
        return int(current_goals + avg * remaining)

    return GoalProjection(
        player_name=player.name,
        current_age=current_age,
        current_goals=current_goals,
        avg_goals_per_season=avg,
        projected_goals_at_30=_project_at(30),
        projected_goals_at_35=_project_at(35),
        projected_goals_at_40=_project_at(40),
    )


def project_goals_at_age(player: Player, target_age: int) -> int:
    current_age = player.age
    if target_age <= current_age or len(player.career_seasons) == 0:
        return player.total_goals
    avg = player.total_goals / len(player.career_seasons)
    return int(player.total_goals + avg * (target_age - current_age))
