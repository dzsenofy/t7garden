"""SQLite event store: state deltas and executed commands, for the timeline view."""
from __future__ import annotations

import json
import os
import time
from typing import Any

import aiosqlite

_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    system TEXT NOT NULL,
    kind TEXT NOT NULL,          -- 'state' | 'command' | 'error'
    payload TEXT NOT NULL        -- JSON
);
CREATE INDEX IF NOT EXISTS events_ts ON events(ts);
CREATE INDEX IF NOT EXISTS events_system_ts ON events(system, ts);
"""


class Store:
    def __init__(self, path: str) -> None:
        self.path = path
        self._db: aiosqlite.Connection | None = None
        self._last_state: dict[str, str] = {}

    async def open(self) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        self._db = await aiosqlite.connect(self.path)
        self._db.row_factory = aiosqlite.Row
        await self._db.executescript(_SCHEMA)
        await self._db.commit()

    async def close(self) -> None:
        if self._db:
            await self._db.close()
            self._db = None

    async def record_state(self, system: str, online: bool, data: dict[str, Any], error: str | None) -> bool:
        """Store only when something changed. Returns True if an event was written."""
        fingerprint = json.dumps({"online": online, "data": data, "error": error}, sort_keys=True, default=str)
        if self._last_state.get(system) == fingerprint:
            return False
        self._last_state[system] = fingerprint
        await self._insert(system, "error" if error else "state", {"online": online, "data": data, "error": error})
        return True

    async def record_command(self, system: str, command: str, args: dict[str, Any], result: Any, ok: bool) -> None:
        await self._insert(system, "command", {"command": command, "args": args, "result": result, "ok": ok})

    async def recent(self, limit: int = 100, system: str | None = None) -> list[dict[str, Any]]:
        assert self._db
        if system:
            cur = await self._db.execute(
                "SELECT id, ts, system, kind, payload FROM events WHERE system=? ORDER BY ts DESC LIMIT ?",
                (system, limit),
            )
        else:
            cur = await self._db.execute(
                "SELECT id, ts, system, kind, payload FROM events ORDER BY ts DESC LIMIT ?", (limit,)
            )
        rows = await cur.fetchall()
        return [
            {"id": r["id"], "ts": r["ts"], "system": r["system"], "kind": r["kind"], "payload": json.loads(r["payload"])}
            for r in rows
        ]

    async def series(self, system: str, key: str, since: float) -> list[tuple[float, Any]]:
        """Numeric history for one top-level data key (used for the PV power sparkline)."""
        assert self._db
        cur = await self._db.execute(
            "SELECT ts, payload FROM events WHERE system=? AND kind='state' AND ts>=? ORDER BY ts",
            (system, since),
        )
        out = []
        async for r in cur:
            data = json.loads(r["payload"]).get("data", {})
            if key in data:
                out.append((r["ts"], data[key]))
        return out

    async def _insert(self, system: str, kind: str, payload: dict[str, Any]) -> None:
        assert self._db
        await self._db.execute(
            "INSERT INTO events(ts, system, kind, payload) VALUES (?,?,?,?)",
            (time.time(), system, kind, json.dumps(payload, default=str)),
        )
        await self._db.commit()
