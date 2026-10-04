"""
Unit tests for SessionBroker and BrowserWorker helper functions.
"""
import pytest
from src.session_manager import SessionBroker
from src.browser_worker import map_user_agent_to_impersonate, BrowserWorker, PlaywrightWorker


def test_map_user_agent_to_impersonate():
    assert map_user_agent_to_impersonate("Mozilla/5.0 Chrome/133.0.0.0 Safari/537.36") == "chrome131"
    assert map_user_agent_to_impersonate("Mozilla/5.0 Chrome/124.0.0.0 Safari/537.36") == "chrome124"
    assert map_user_agent_to_impersonate("Mozilla/5.0 Chrome/120.0.0.0 Safari/537.36") == "chrome120"
    assert map_user_agent_to_impersonate("Mozilla/5.0 Chrome/116.0.0.0 Safari/537.36") == "chrome116"
    assert map_user_agent_to_impersonate("Mozilla/5.0 Chrome/110.0.0.0 Safari/537.36") == "chrome110"
    assert map_user_agent_to_impersonate("Mozilla/5.0 Chrome/104.0.0.0 Safari/537.36") == "chrome104"
    assert map_user_agent_to_impersonate("Mozilla/5.0 Chrome/90.0.0.0 Safari/537.36") == "chrome"
    assert map_user_agent_to_impersonate("Mozilla/5.0 Version/15.5 Safari/605.1.15") == "safari15_5"
    assert map_user_agent_to_impersonate("") == "chrome"


@pytest.mark.asyncio
async def test_session_broker_in_memory_crud():
    broker = SessionBroker()
    await broker.initialize()

    # Empty initially
    assert await broker.get_session("test_session") is None

    # Set session
    payload = {"cookies": "foo=bar", "user_agent": "TestUA"}
    await broker.set_session("test_session", payload=payload, ttl=300)

    # Get session
    retrieved = await broker.get_session("test_session")
    assert retrieved is not None
    assert retrieved["cookies"] == "foo=bar"
    assert retrieved["user_agent"] == "TestUA"
    assert "expires_at" in retrieved

    # Invalidate
    await broker.invalidate("test_session")
    assert await broker.get_session("test_session") is None


def test_browser_worker_alias():
    assert BrowserWorker is PlaywrightWorker
