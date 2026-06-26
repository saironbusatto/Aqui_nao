from datetime import datetime


def calculate_age(date_of_birth: str, reference_date: str | None = None) -> int:
    """Calculate age from date of birth string (YYYY-MM-DD)."""
    birth = datetime.strptime(date_of_birth, "%Y-%m-%d")
    ref = datetime.strptime(reference_date, "%Y-%m-%d") if reference_date else datetime.now()
    return ref.year - birth.year - ((ref.month, ref.day) < (birth.month, birth.day))


def season_to_year_range(season: str) -> tuple[int, int]:
    """Convert season string like '2023-2024' to (2023, 2024)."""
    parts = season.split("-")
    return int(parts[0]), int(parts[1])


def format_minutes(minutes: int) -> str:
    """Format minutes into hours and minutes string."""
    hours = minutes // 60
    mins = minutes % 60
    if hours == 0:
        return f"{mins}min"
    return f"{hours}h {mins}min"


def format_goals_per_game(goals: int, games: int) -> str:
    """Format goals per game ratio."""
    if games == 0:
        return "0.00"
    return f"{goals / games:.2f}"


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Safely divide two numbers, returning default if denominator is zero."""
    if denominator == 0:
        return default
    return numerator / denominator
