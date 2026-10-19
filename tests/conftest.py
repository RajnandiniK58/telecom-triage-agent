import pytest

from app import agent


@pytest.fixture(autouse=True)
def no_retry_sleep(monkeypatch):
    """Keep retry tests instant."""
    monkeypatch.setattr(agent, "RETRY_BACKOFF_SECONDS", 0.0)
    monkeypatch.setattr(agent, "RATE_LIMIT_BACKOFF_SECONDS", 0.0)
