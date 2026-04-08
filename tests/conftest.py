"""Shared pytest configuration."""

import pytest


# Use asyncio mode for all async tests
def pytest_configure(config):
    config.addinivalue_line(
        "markers", "integration: mark test as requiring a live database"
    )
