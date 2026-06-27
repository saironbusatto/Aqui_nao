"""Tests for utility modules: helpers and cache."""

import json
import time
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# helpers.py
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCalculateAge:
    def test_basic_age(self):
        from src.utils.helpers import calculate_age
        assert calculate_age("1987-06-24", "2024-01-01") == 36

    def test_birthday_not_yet_this_year(self):
        from src.utils.helpers import calculate_age
        assert calculate_age("1987-06-24", "2024-06-23") == 36

    def test_birthday_today(self):
        from src.utils.helpers import calculate_age
        assert calculate_age("1987-06-24", "2024-06-24") == 37

    def test_no_reference_date_returns_int(self):
        from src.utils.helpers import calculate_age
        result = calculate_age("1987-06-24")
        assert isinstance(result, int)


@pytest.mark.unit
class TestSeasonToYearRange:
    def test_basic_conversion(self):
        from src.utils.helpers import season_to_year_range
        assert season_to_year_range("2023-2024") == (2023, 2024)

    def test_earlier_seasons(self):
        from src.utils.helpers import season_to_year_range
        assert season_to_year_range("1998-1999") == (1998, 1999)


@pytest.mark.unit
class TestFormatMinutes:
    def test_less_than_hour(self):
        from src.utils.helpers import format_minutes
        assert format_minutes(45) == "45min"

    def test_exactly_one_hour(self):
        from src.utils.helpers import format_minutes
        assert format_minutes(60) == "1h 0min"

    def test_hours_and_minutes(self):
        from src.utils.helpers import format_minutes
        assert format_minutes(90) == "1h 30min"

    def test_zero_minutes(self):
        from src.utils.helpers import format_minutes
        assert format_minutes(0) == "0min"


@pytest.mark.unit
class TestFormatGoalsPerGame:
    def test_basic_ratio(self):
        from src.utils.helpers import format_goals_per_game
        assert format_goals_per_game(30, 60) == "0.50"

    def test_zero_games(self):
        from src.utils.helpers import format_goals_per_game
        assert format_goals_per_game(10, 0) == "0.00"

    def test_zero_goals(self):
        from src.utils.helpers import format_goals_per_game
        assert format_goals_per_game(0, 50) == "0.00"


@pytest.mark.unit
class TestSafeDivide:
    def test_basic_division(self):
        from src.utils.helpers import safe_divide
        assert safe_divide(10.0, 2.0) == 5.0

    def test_zero_denominator_returns_default(self):
        from src.utils.helpers import safe_divide
        assert safe_divide(10.0, 0.0) == 0.0

    def test_custom_default(self):
        from src.utils.helpers import safe_divide
        assert safe_divide(10.0, 0.0, default=-1.0) == -1.0


# ---------------------------------------------------------------------------
# cache.py
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCache:
    def test_set_and_get(self, tmp_path, monkeypatch):
        from src.utils import cache as cache_mod
        monkeypatch.setattr(cache_mod, "CACHE_DIR", tmp_path / "cache")

        cache_mod.set_cached("ns", "key1", {"data": 42})
        result = cache_mod.get_cached("ns", "key1")
        assert result == {"data": 42}

    def test_get_returns_none_when_missing(self, tmp_path, monkeypatch):
        from src.utils import cache as cache_mod
        monkeypatch.setattr(cache_mod, "CACHE_DIR", tmp_path / "cache")

        result = cache_mod.get_cached("ns", "nonexistent")
        assert result is None

    def test_expired_cache_returns_none(self, tmp_path, monkeypatch):
        from src.utils import cache as cache_mod
        monkeypatch.setattr(cache_mod, "CACHE_DIR", tmp_path / "cache")
        monkeypatch.setattr(cache_mod, "CACHE_TTL_SECONDS", 0)

        cache_mod.set_cached("ns", "key2", "value")
        time.sleep(0.01)
        result = cache_mod.get_cached("ns", "key2")
        assert result is None

    def test_clear_cache_removes_files(self, tmp_path, monkeypatch):
        from src.utils import cache as cache_mod
        monkeypatch.setattr(cache_mod, "CACHE_DIR", tmp_path / "cache")

        cache_mod.set_cached("ns", "a", 1)
        cache_mod.set_cached("ns", "b", 2)
        count = cache_mod.clear_cache()
        assert count == 2
        assert cache_mod.get_cached("ns", "a") is None

    def test_different_namespaces_dont_collide(self, tmp_path, monkeypatch):
        from src.utils import cache as cache_mod
        monkeypatch.setattr(cache_mod, "CACHE_DIR", tmp_path / "cache")

        cache_mod.set_cached("ns1", "key", "value1")
        cache_mod.set_cached("ns2", "key", "value2")
        assert cache_mod.get_cached("ns1", "key") == "value1"
        assert cache_mod.get_cached("ns2", "key") == "value2"
