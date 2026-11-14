"""All legacy integration tests use explicit isolated demo mode."""
import pytest


@pytest.fixture(autouse=True)
def demo_mode(monkeypatch):
    monkeypatch.setenv('NAGRIKOS_MODE', 'demo')
