"""FastAPI entry point: REST + WebSocket for the dashboard."""
from __future__ import annotations

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
from pydantic import BaseModel

from .adapters.base import AdapterError
from .config import settings
from .registry import build_adapters
from .scheduler import Hub, Poller
from .store import Store

logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("scc")


@asynccontextmanager
async def lifespan(app: FastAPI):
    store = Store(settings.db_path)
    await store.open()
    hub = Hub()
    poller = Poller(build_adapters(settings), store, hub)
    app.state.store, app.state.hub, app.state.poller = store, hub, poller
    await poller.start()
    yield
    await poller.stop()
    await store.close()


app = FastAPI(title=settings.app_name, lifespan=lifespan)


# ---------- auth (optional shared token, also accepted as ?token= for <img> snapshot URLs) ----------
def require_token(request: Request) -> None:
    if not settings.dashboard_token:
        return
    header = request.headers.get("authorization", "")
    token = header.removeprefix("Bearer ").strip() or request.query_params.get("token", "")
    if token != settings.dashboard_token:
        raise HTTPException(401, "invalid token")


auth = [Depends(require_token)]


# ---------- REST ----------
@app.get("/api/health")
async def health() -> dict[str, Any]:
    return {"ok": True, "app": settings.app_name, "demo": settings.demo_mode, "ts": time.time()}


@app.get("/api/systems", dependencies=auth)
async def systems(request: Request) -> list[dict[str, Any]]:
    poller: Poller = request.app.state.poller
    return [a.describe() for a in poller.adapters.values()]


@app.get("/api/state", dependencies=auth)
async def state(request: Request) -> dict[str, Any]:
    poller: Poller = request.app.state.poller
    return {s: a.state.as_dict() for s, a in poller.adapters.items()}


@app.post("/api/{system}/refresh", dependencies=auth)
async def refresh(system: str, request: Request) -> dict[str, Any]:
    poller: Poller = request.app.state.poller
    if system not in poller.adapters:
        raise HTTPException(404, f"unknown system {system}")
    await poller.poll_one(system)
    return poller.adapters[system].state.as_dict()


class CommandIn(BaseModel):
    command: str
    args: dict[str, Any] = {}


@app.post("/api/{system}/command", dependencies=auth)
async def command(system: str, body: CommandIn, request: Request) -> dict[str, Any]:
    poller: Poller = request.app.state.poller
    store: Store = request.app.state.store
    hub: Hub = request.app.state.hub
    adapter = poller.adapters.get(system)
    if adapter is None:
        raise HTTPException(404, f"unknown system {system}")
    try:
        result = await adapter.execute(body.command, body.args)
    except AdapterError as exc:
        await store.record_command(system, body.command, body.args, str(exc), False)
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        log.exception("command %s/%s failed", system, body.command)
        await store.record_command(system, body.command, body.args, f"{type(exc).__name__}: {exc}", False)
        raise HTTPException(502, f"{system}: {exc}") from exc
    await store.record_command(system, body.command, body.args, result, True)
    st = adapter.state.as_dict()
    hub.publish({"type": "state", **st})
    hub.publish({"type": "command", "system": system, "command": body.command, "args": body.args, "result": result, "ts": time.time()})
    return {"result": result, "state": st}


@app.get("/api/events", dependencies=auth)
async def events(request: Request, limit: int = 100, system: str | None = None) -> list[dict[str, Any]]:
    store: Store = request.app.state.store
    return await store.recent(min(limit, 500), system)


@app.get("/api/{system}/series/{key}", dependencies=auth)
async def series(system: str, key: str, request: Request, hours: float = 24) -> list[list[Any]]:
    store: Store = request.app.state.store
    return [[ts, v] for ts, v in await store.series(system, key, time.time() - hours * 3600)]


@app.get("/api/hik_nvr/snapshot/{channel}", dependencies=auth)
async def snapshot(channel: int, request: Request) -> Response:
    poller: Poller = request.app.state.poller
    adapter = poller.adapters.get("hik_nvr")
    if adapter is None:
        raise HTTPException(404, "NVR not configured")
    if not hasattr(adapter, "snapshot"):  # demo adapter: placeholder frame
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 180"><rect width="320" height="180" fill="#1e293b"/>'
               f'<text x="160" y="96" text-anchor="middle" fill="#64748b" font-family="sans-serif" font-size="18">demo · channel {channel}</text></svg>')
        return Response(svg, media_type="image/svg+xml", headers={"Cache-Control": "no-store"})
    try:
        jpeg = await adapter.snapshot(channel)  # type: ignore[attr-defined]
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, f"snapshot failed: {exc}") from exc
    return Response(jpeg, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


# ---------- WebSocket ----------
@app.websocket("/ws")
async def ws(websocket: WebSocket) -> None:
    if settings.dashboard_token and websocket.query_params.get("token") != settings.dashboard_token:
        await websocket.close(code=4401)
        return
    await websocket.accept()
    hub: Hub = websocket.app.state.hub
    poller: Poller = websocket.app.state.poller
    q = hub.subscribe()
    try:
        await websocket.send_json({"type": "snapshot", "systems": [a.describe() for a in poller.adapters.values()],
                                   "state": {s: a.state.as_dict() for s, a in poller.adapters.items()}})
        while True:
            try:
                msg = await asyncio.wait_for(q.get(), timeout=25)
            except asyncio.TimeoutError:
                msg = {"type": "ping", "ts": time.time()}
            await websocket.send_json(msg)
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        hub.unsubscribe(q)
