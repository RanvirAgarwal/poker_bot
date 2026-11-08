"""
agent_range_aware.py - Tournament server entry point for RangeAware_v2 candidate.

Matches the official agent.py server protocol exactly.
"""

from __future__ import annotations

import os
import sys
import traceback

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT_DIR, "starter"))
sys.path.insert(0, ROOT_DIR)

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from evaluator import warmup
from game import Action, AgentConfig, HandResult, Observation
from runtime.range_aware_policy import RangeAwarePolicy

warmup()

PARTICIPANT = "TeamAntigravity"
AGENT_NAME = "RangeAware_v2"

_POLICY = RangeAwarePolicy(aggression=1.0, seed=42)

app = FastAPI()
MEMORY: dict = {}
STATUS = {"started": False}
TOKEN = os.environ.get("AGENT_TOKEN") or None


def new_half(config: AgentConfig, memory: dict) -> None:
    memory["hands_played"] = 0
    memory["config"] = {
        "starting_stack": config.starting_stack,
        "big_blind": config.big_blind,
        "small_blind": config.small_blind,
        "num_hands": config.num_hands,
        "raise_cap": config.raise_cap,
    }
    memory["my_net_total"] = 0
    memory["errors"] = 0


def choose_action(obs: Observation, memory: dict) -> Action:
    try:
        action = _POLICY.choose_action(obs, memory)
        if action not in obs.legal_actions:
            return Action.CHECK_CALL if obs.to_call == 0 else Action.FOLD
        return action
    except Exception:
        memory["errors"] = memory.get("errors", 0) + 1
        return Action.CHECK_CALL if obs.to_call == 0 else Action.FOLD


def on_hand_end(result: HandResult, memory: dict) -> None:
    memory["hands_played"] = memory.get("hands_played", 0) + 1
    memory["my_net_total"] = memory.get("my_net_total", 0) + result.my_net


async def _read_request(request: Request, path: str) -> tuple[dict, JSONResponse | None]:
    if TOKEN and request.headers.get("x-agent-token") != TOKEN:
        return {}, JSONResponse({"error": "bad or missing X-Agent-Token"}, status_code=401)
    if not STATUS["started"] and path != "/new-half":
        return {}, JSONResponse({"error": "call /new-half first"}, status_code=409)
    try:
        body = await request.json()
    except ValueError:
        body = None
    if not isinstance(body, dict):
        return {}, JSONResponse({"error": "the request body must be a JSON object"}, status_code=400)
    return body, None


def _error_info(exc: Exception) -> dict:
    return {"error": f"{type(exc).__name__}: {exc}", "traceback": traceback.format_exc()}


def _crash(exc: Exception, hand_end_errors: list | None = None) -> JSONResponse:
    return JSONResponse({**_error_info(exc), "hand_end_errors": hand_end_errors or []},
                        status_code=500)


def _deliver_results(raw_results) -> list:
    errors = []
    for raw in raw_results or []:
        try:
            on_hand_end(HandResult.from_dict(raw), MEMORY)
        except Exception as exc:
            errors.append(_error_info(exc))
    return errors


@app.get("/")
async def info():
    return {"participant": PARTICIPANT, "agent_name": AGENT_NAME}


@app.post("/new-half")
async def route_new_half(request: Request):
    body, refused = await _read_request(request, "/new-half")
    if refused:
        return refused
    MEMORY.clear()
    STATUS["started"] = True
    try:
        new_half(AgentConfig.from_dict(body.get("config", {})), MEMORY)
    except Exception as exc:
        return _crash(exc)
    return {"ok": True}


@app.post("/act")
async def route_act(request: Request):
    body, refused = await _read_request(request, "/act")
    if refused:
        return refused
    hand_end_errors = _deliver_results(body.get("hand_results"))
    try:
        obs = Observation.from_dict(body["observation"])
        action = choose_action(obs, MEMORY)
    except Exception as exc:
        return _crash(exc, hand_end_errors)
    if isinstance(action, Action):
        answer = action.name
    elif action is None or isinstance(action, (str, int, float, bool)):
        answer = action
    else:
        answer = repr(action)
    return {"action": answer, "hand_end_errors": hand_end_errors}


@app.post("/hand-end")
async def route_hand_end(request: Request):
    body, refused = await _read_request(request, "/hand-end")
    if refused:
        return refused
    return {"ok": True, "hand_end_errors": _deliver_results(body.get("results"))}


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5008"))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")
