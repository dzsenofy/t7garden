"""Polls every adapter on its own interval and fans state out to WebSocket subscribers."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from .adapters.base import Adapter
from .store import Store

log = logging.getLogger(__name__)


class Hub:
    """Tracks connected WebSocket clients and broadcasts JSON messages."""

    def __init__(self) -> None:
        self._queues: set[asyncio.Queue] = set()

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._queues.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._queues.discard(q)

    def publish(self, message: dict[str, Any]) -> None:
        for q in list(self._queues):
            try:
                q.put_nowait(message)
            except asyncio.QueueFull:
                self._queues.discard(q)  # slow client; it will reconnect and resync


class Poller:
    def __init__(self, adapters: list[Adapter], store: Store, hub: Hub) -> None:
        self.adapters = {a.system: a for a in adapters}
        self.store = store
        self.hub = hub
        self._sched = AsyncIOScheduler()

    async def start(self) -> None:
        for adapter in self.adapters.values():
            self._sched.add_job(
                self.poll_one,
                "interval",
                seconds=adapter.poll_seconds,
                args=[adapter.system],
                id=adapter.system,
                max_instances=1,
                coalesce=True,
            )
        self._sched.start()
        # first pass immediately, in parallel, so the dashboard is populated on startup
        await asyncio.gather(*(self.poll_one(s) for s in self.adapters), return_exceptions=True)

    async def stop(self) -> None:
        self._sched.shutdown(wait=False)
        await asyncio.gather(*(a.close() for a in self.adapters.values()), return_exceptions=True)

    async def poll_one(self, system: str) -> None:
        adapter = self.adapters[system]
        state = await adapter.poll()
        changed = await self.store.record_state(system, state.online, state.data, state.error)
        if changed:
            self.hub.publish({"type": "state", **state.as_dict()})
