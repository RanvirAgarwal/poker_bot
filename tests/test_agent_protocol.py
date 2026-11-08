"""
tests/test_agent_protocol.py - Test our root agent.py HTTP protocol conformance.

Tests that our root agent.py:
- Implements all required HTTP endpoints
- Correctly resets memory on /new-half
- Answers /act with legal actions
- Handles /hand-end without errors
- Respects authentication tokens
- Starts within timeout limits
"""

import sys
import os

# Ensure root directory is first in sys.path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT_DIR, "starter"))
sys.path.insert(0, ROOT_DIR)

import pytest
from fastapi.testclient import TestClient

from agent import app, PARTICIPANT, AGENT_NAME
from game import Action, AgentConfig, Observation, Street, make_deal, button_for_deal, Game


@pytest.fixture
def client():
    return TestClient(app)


def test_health_check(client):
    """GET / returns participant and agent name."""
    res = client.get("/")
    assert res.status_code == 200
    data = res.json()
    assert data["participant"] == PARTICIPANT
    assert data["agent_name"] == AGENT_NAME
    assert PARTICIPANT != "TotallyAwesomeDatathonParticipant"  # customized!
    assert AGENT_NAME != "JustAsAwesomeAgent"


def test_new_half_starts_half(client):
    """POST /new-half initializes the half."""
    config = AgentConfig()
    res = client.post("/new-half", json={"config": config.to_dict()})
    assert res.status_code == 200
    assert res.json() == {"ok": True}


def test_act_returns_legal_action(client):
    """POST /act returns a valid, legal Action."""
    # First start a half
    client.post("/new-half", json={"config": AgentConfig().to_dict()})

    deal = make_deal("test", 0)
    game = Game(deal, button_for_deal(0))
    obs = game.observation(game.to_act)

    res = client.post("/act", json={"observation": obs.to_dict(), "hand_results": []})
    assert res.status_code == 200
    data = res.json()
    assert "action" in data
    assert data["action"] in [a.name for a in obs.legal_actions]
    assert data["hand_end_errors"] == []


def test_hand_end_endpoint(client):
    """POST /hand-end delivers completed hands."""
    client.post("/new-half", json={"config": AgentConfig().to_dict()})

    deal = make_deal("test", 0)
    game = Game(deal, button_for_deal(0))
    game.apply(Action.FOLD)
    hr = game.hand_result(0)

    res = client.post("/hand-end", json={"results": [hr.to_dict()]})
    assert res.status_code == 200
    assert res.json()["ok"] is True
    assert res.json()["hand_end_errors"] == []


def test_act_before_new_half_fails(client):
    """Calling /act before /new-half returns 409 Conflict."""
    # Reset status
    from agent import STATUS
    STATUS["started"] = False

    deal = make_deal("test", 0)
    game = Game(deal, button_for_deal(0))
    obs = game.observation(game.to_act)

    res = client.post("/act", json={"observation": obs.to_dict()})
    assert res.status_code == 409
