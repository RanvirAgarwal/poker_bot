"""
opponents/serve_opponent.py - HTTP server for any baseline opponent.

Usage:
    PORT=5009 OPPONENT_BOT=action_conditioned_range python opponents/serve_opponent.py

Changelog (F3 fix):
- /new-half now calls bot.new_half(config, MEMORY) if the method exists.
- /act now delivers batched hand_results before calling choose_action (same semantics as agent.py).
- /hand-end now calls bot.on_hand_end(result, MEMORY) for each result if the method exists.
"""

from __future__ import annotations

import os
import sys
import traceback
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT_DIR, "starter"))
sys.path.insert(0, ROOT_DIR)

from evaluator import warmup
from game import Action, AgentConfig, HandResult, Observation
from opponents.baselines import BASELINE_REGISTRY
from opponents.adversarial import ADVERSARIAL_REGISTRY

warmup()

ALL_OPPONENTS = {**BASELINE_REGISTRY, **ADVERSARIAL_REGISTRY}

bot_name = os.environ.get("OPPONENT_BOT", "calling_station")
bot_cls = ALL_OPPONENTS.get(bot_name)
if bot_cls is None:
    raise ValueError(f"Unknown bot: {bot_name}. Available: {list(ALL_OPPONENTS.keys())}")

bot = bot_cls()
PARTICIPANT = "BaselineSuite"
AGENT_NAME = f"Bot_{bot_name}"

app = FastAPI()
MEMORY: dict = {}
STATUS = {"started": False}
TOKEN = os.environ.get("AGENT_TOKEN") or None


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


def _deliver_results(raw_results) -> list:
    """Deliver batched hand results to the bot (same pattern as agent.py)."""
    errors = []
    for raw in raw_results or []:
        try:
            result = HandResult.from_dict(raw)
            if hasattr(bot, "on_hand_end"):
                bot.on_hand_end(result, MEMORY)
        except Exception as exc:
            errors.append({"error": f"{type(exc).__name__}: {exc}"})
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
    # F3 fix: call bot.new_half if it exists
    if hasattr(bot, "new_half"):
        try:
            config = AgentConfig.from_dict(body.get("config", {}))
            bot.new_half(config, MEMORY)
        except Exception as exc:
            return JSONResponse(
                {"error": f"bot.new_half failed: {type(exc).__name__}: {exc}"},
                status_code=500,
            )
    return {"ok": True}


@app.post("/act")
async def route_act(request: Request):
    body, refused = await _read_request(request, "/act")
    if refused:
        return refused
    # F3 fix: deliver hand_results BEFORE calling choose_action
    hand_end_errors = _deliver_results(body.get("hand_results"))
    try:
        obs = Observation.from_dict(body["observation"])
        action = bot.choose_action(obs, MEMORY)
        if action not in obs.legal_actions:
            action = Action.CHECK_CALL if obs.to_call == 0 else Action.FOLD
    except Exception as exc:
        return JSONResponse(
            {"error": f"{type(exc).__name__}: {exc}", "hand_end_errors": hand_end_errors},
            status_code=500,
        )
    return {"action": action.name, "hand_end_errors": hand_end_errors}


@app.post("/hand-end")
async def route_hand_end(request: Request):
    body, refused = await _read_request(request, "/hand-end")
    if refused:
        return refused
    # F3 fix: deliver results via on_hand_end if it exists
    hand_end_errors = _deliver_results(body.get("results"))
    return {"ok": True, "hand_end_errors": hand_end_errors}


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5009"))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")
