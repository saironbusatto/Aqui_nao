from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class Injury:
    """Represents a single injury in a player's career."""
    season: str
    injury_type: str
    date_from: str
    date_until: str
    days_missed: int
    games_missed: int


@dataclass(frozen=True)
class SeasonStats:
    """Stats for a single season."""
    season: str
    team: str
    age: int
    appearances: int
    starts: int
    minutes_played: int
    goals: int
    assists: int
    yellow_cards: int
    red_cards: int


@dataclass(frozen=True)
class Player:
    """Complete player profile with career data."""
    name: str
    full_name: str
    date_of_birth: str
    nationality: str
    position: str
    height_cm: Optional[float] = None
    current_team: Optional[str] = None
    market_value: Optional[str] = None
    sponsors: tuple[str, ...] = field(default_factory=tuple)
    career_seasons: tuple[SeasonStats, ...] = field(default_factory=tuple)
    injuries: tuple[Injury, ...] = field(default_factory=tuple)
    world_cup_goals: int = 0
    world_cup_appearances: int = 0

    @property
    def age(self) -> int:
        """Calculate current age from date of birth."""
        birth = datetime.strptime(self.date_of_birth, "%Y-%m-%d")
        today = datetime.now()
        return today.year - birth.year - (
            (today.month, today.day) < (birth.month, birth.day)
        )

    @property
    def total_goals(self) -> int:
        """Total career goals across all seasons."""
        return sum(s.goals for s in self.career_seasons)

    @property
    def total_assists(self) -> int:
        """Total career assists across all seasons."""
        return sum(s.assists for s in self.career_seasons)

    @property
    def total_appearances(self) -> int:
        """Total career appearances across all seasons."""
        return sum(s.appearances for s in self.career_seasons)

    @property
    def total_minutes(self) -> int:
        """Total minutes played across all seasons."""
        return sum(s.minutes_played for s in self.career_seasons)

    @property
    def total_injuries(self) -> int:
        """Total number of injuries."""
        return len(self.injuries)

    @property
    def total_days_injured(self) -> int:
        """Total days missed due to injuries."""
        return sum(i.days_missed for i in self.injuries)

    @property
    def total_games_injured(self) -> int:
        """Total games missed due to injuries."""
        return sum(i.games_missed for i in self.injuries)

    @property
    def teams_played(self) -> tuple[str, ...]:
        """Unique teams the player has played for."""
        return tuple(dict.fromkeys(s.team for s in self.career_seasons))

    def goals_at_age(self, target_age: int) -> int:
        """Total goals scored at a specific age."""
        return sum(s.goals for s in self.career_seasons if s.age == target_age)

    def goals_by_team(self, team_name: str) -> int:
        """Total goals scored for a specific team."""
        return sum(s.goals for s in self.career_seasons if s.team == team_name)

    def seasons_at_age(self, target_age: int) -> tuple[SeasonStats, ...]:
        """All seasons played at a specific age."""
        return tuple(s for s in self.career_seasons if s.age == target_age)
