from dataclasses import dataclass, field

from src.models.player import Player


@dataclass(frozen=True)
class AgeComparison:
    """Comparison of two players at the same age."""
    age: int
    player1_goals: int
    player2_goals: int
    player1_appearances: int
    player2_appearances: int
    player1_minutes: int
    player2_minutes: int


@dataclass(frozen=True)
class TeamComparison:
    """Comparison of goals scored by two players for specific teams."""
    team: str
    player1_goals: int
    player2_goals: int


@dataclass(frozen=True)
class GoalProjection:
    """Goal projection based on current pace."""
    player_name: str
    current_age: int
    current_goals: int
    avg_goals_per_season: float
    projected_goals_at_30: int
    projected_goals_at_35: int
    projected_goals_at_40: int


@dataclass(frozen=True)
class InjuryComparison:
    """Comparison of injury history between two players."""
    player1_total_injuries: int
    player2_total_injuries: int
    player1_days_injured: int
    player2_days_injured: int
    player1_games_missed: int
    player2_games_missed: int


@dataclass(frozen=True)
class PlayingTimeComparison:
    """Comparison of playing time between two players."""
    player1_total_minutes: int
    player2_total_minutes: int
    player1_starts: int
    player2_starts: int
    player1_bench_appearances: int
    player2_bench_appearances: int


@dataclass(frozen=True)
class PlayerComparison:
    """Full comparison between two players."""
    player1: Player
    player2: Player
    age_comparisons: tuple[AgeComparison, ...] = field(default_factory=tuple)
    team_comparisons: tuple[TeamComparison, ...] = field(default_factory=tuple)
    player1_projection: GoalProjection | None = None
    player2_projection: GoalProjection | None = None
    injury_comparison: InjuryComparison | None = None
    playing_time_comparison: PlayingTimeComparison | None = None

    @property
    def summary(self) -> dict:
        """Generate a summary dict of the comparison."""
        return {
            "player1": {
                "name": self.player1.name,
                "age": self.player1.age,
                "total_goals": self.player1.total_goals,
                "total_assists": self.player1.total_assists,
                "total_appearances": self.player1.total_appearances,
                "teams": self.player1.teams_played,
                "world_cup_goals": self.player1.world_cup_goals,
                "total_injuries": self.player1.total_injuries,
                "days_injured": self.player1.total_days_injured,
            },
            "player2": {
                "name": self.player2.name,
                "age": self.player2.age,
                "total_goals": self.player2.total_goals,
                "total_assists": self.player2.total_assists,
                "total_appearances": self.player2.total_appearances,
                "teams": self.player2.teams_played,
                "world_cup_goals": self.player2.world_cup_goals,
                "total_injuries": self.player2.total_injuries,
                "days_injured": self.player2.total_days_injured,
            },
        }
