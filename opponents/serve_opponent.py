"""
opponents/serve_opponent.py - HTTP server for any baseline opponent.

Usage:
    PORT=5009 OPPONENT_BOT=action_conditioned_range python opponents/serve_opponent.py
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

warmup()

bot_name = os.environ.get("OPPONENT_BOT", "calling_station")
bot_cls = BASELINE_REGISTRY.get(bot_name)
if bot_cls is None:
    raise ValueError(f"Unknown bot: {bot_name}. Available: {list(BASELINE_REGISTRY.keys())}")

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
    return {"ok": True}


@app.post("/act")
async def route_act(request: Request):
    body, refused = await _read_request(request, "/act")
    if refused:
        return refused
    obs = Observation.from_dict(body["observation"])
    action = bot.choose_action(obs, MEMORY)
    if action not in obs.legal_actions:
        action = Action.CHECK_CALL if obs.to_call == 0 else Action.FOLD
    return {"action": action.name, "hand_end_errors": []}


@app.post("/hand-end")
async def route_hand_end(request: Request):
    body, refused = await _read_request(request, "/hand-end")
    if refused:
        return refused
    return {"ok": True, "hand_end_errors": []}


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5009"))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")
