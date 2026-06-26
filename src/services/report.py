from __future__ import annotations

import os
from io import BytesIO

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from src.models.player import Player
from src.models.comparison import PlayerComparison


def generate_comparison_chart(
    p1: Player, p2: Player, output_path: str
) -> str:

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    shared_ages = sorted(
        {s.age for s in p1.career_seasons} & {s.age for s in p2.career_seasons}
    )
    p1_goals = [p1.goals_at_age(a) for a in shared_ages]
    p2_goals = [p2.goals_at_age(a) for a in shared_ages]

    fig, ax = plt.subplots(figsize=(10, 5))
    x_pos = list(range(len(shared_ages)))
    width = 0.35

    ax.bar([x - width / 2 for x in x_pos], p1_goals, width, label=p1.name)
    ax.bar([x + width / 2 for x in x_pos], p2_goals, width, label=p2.name)
    ax.set_xlabel("Age")
    ax.set_ylabel("Goals")
    ax.set_title(f"{p1.name} vs {p2.name}")
    ax.set_xticks(x_pos)
    ax.set_xticklabels(shared_ages)
    ax.legend()

    fig.tight_layout()
    fig.savefig(output_path, dpi=100)
    plt.close(fig)

    return output_path


def generate_report(comparison: PlayerComparison) -> str:
    p1 = comparison.player1
    p2 = comparison.player2
    lines: list[str] = []

    lines.append(f"Player Comparison: {p1.name} vs {p2.name}")
    lines.append("=" * 50)
    lines.append("")

    lines.append(f"{p1.name}: {p1.nationality} | {p1.position} | Born {p1.date_of_birth}")
    lines.append(f"{p2.name}: {p2.nationality} | {p2.position} | Born {p2.date_of_birth}")
    lines.append("")

    lines.append("Career Goals")
    lines.append("-" * 30)
    lines.append(f"{p1.name}: {p1.total_goals} goals in {p1.total_appearances} appearances")
    lines.append(f"{p2.name}: {p2.total_goals} goals in {p2.total_appearances} appearances")
    lines.append("")

    lines.append("Assists")
    lines.append("-" * 30)
    lines.append(f"{p1.name}: {p1.total_assists}")
    lines.append(f"{p2.name}: {p2.total_assists}")
    lines.append("")

    lines.append("World Cup")
    lines.append("-" * 30)
    lines.append(
        f"{p1.name}: {p1.world_cup_goals} goals in {p1.world_cup_appearances} appearances"
    )
    lines.append(
        f"{p2.name}: {p2.world_cup_goals} goals in {p2.world_cup_appearances} appearances"
    )
    lines.append("")

    if comparison.age_comparisons:
        lines.append("Age-by-Age Comparison (shared ages)")
        lines.append("-" * 30)
        for ac in comparison.age_comparisons:
            lines.append(
                f"  Age {ac.age}: {p1.name} {ac.player1_goals}g / {ac.player1_appearances} apps | "
                f"{p2.name} {ac.player2_goals}g / {ac.player2_appearances} apps"
            )
        lines.append("")

    if comparison.team_comparisons:
        lines.append("Team Comparison (shared teams)")
        lines.append("-" * 30)
        for tc in comparison.team_comparisons:
            lines.append(
                f"  {tc.team}: {p1.name} {tc.player1_goals}g | {p2.name} {tc.player2_goals}g"
            )
        lines.append("")

    ic = comparison.injury_comparison
    lines.append("Injury History")
    lines.append("-" * 30)
    if ic:
        lines.append(f"{p1.name}: {ic.player1_total_injuries} injuries, {ic.player1_days_injured} days, {ic.player1_games_missed} games missed")
        lines.append(f"{p2.name}: {ic.player2_total_injuries} injuries, {ic.player2_days_injured} days, {ic.player2_games_missed} games missed")
    else:
        lines.append(f"{p1.name}: {p1.total_injuries} injuries, {p1.total_days_injured} days, {p1.total_games_injured} games missed")
        lines.append(f"{p2.name}: {p2.total_injuries} injuries, {p2.total_days_injured} days, {p2.total_games_injured} games missed")
    lines.append("")

    pt = comparison.playing_time_comparison
    lines.append("Playing Time")
    lines.append("-" * 30)
    if pt:
        lines.append(f"{p1.name}: {pt.player1_total_minutes} minutes, {pt.player1_starts} starts")
        lines.append(f"{p2.name}: {pt.player2_total_minutes} minutes, {pt.player2_starts} starts")
    else:
        p1_starts = sum(s.starts for s in p1.career_seasons)
        p2_starts = sum(s.starts for s in p2.career_seasons)
        lines.append(f"{p1.name}: {p1.total_minutes} minutes, {p1_starts} starts")
        lines.append(f"{p2.name}: {p2.total_minutes} minutes, {p2_starts} starts")
    lines.append("")

    if comparison.player1_projection and comparison.player2_projection:
        proj1 = comparison.player1_projection
        proj2 = comparison.player2_projection
        lines.append("Goal Projections")
        lines.append("-" * 30)
        lines.append(
            f"{proj1.player_name}: avg {proj1.avg_goals_per_season:.1f}/season | "
            f"projected at 30: {proj1.projected_goals_at_30} | "
            f"at 35: {proj1.projected_goals_at_35} | "
            f"at 40: {proj1.projected_goals_at_40}"
        )
        lines.append(
            f"{proj2.player_name}: avg {proj2.avg_goals_per_season:.1f}/season | "
            f"projected at 30: {proj2.projected_goals_at_30} | "
            f"at 35: {proj2.projected_goals_at_35} | "
            f"at 40: {proj2.projected_goals_at_40}"
        )
        lines.append("")

    return "\n".join(lines)
