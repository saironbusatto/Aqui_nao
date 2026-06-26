import sys
from unittest.mock import MagicMock

import pytest

if "soccerdata" not in sys.modules:
    sys.modules["soccerdata"] = MagicMock()


def pytest_configure(config):
    config.addinivalue_line("markers", "unit: mark test as unit test")
    config.addinivalue_line("markers", "integration: mark test as integration test")
