"""Common adapter contract.

Each smart-home system is wrapped by one Adapter. The scheduler calls `poll()` on its own
interval and the API calls `execute()` for user commands. Adapters must never raise out of
`poll()` for transient errors: they keep the last known state, mark `online=False` and attach
the error message, so the dashboard keeps showing what it knows.
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger(__name__)


@dataclass
class Command:
    """A user-invokable action, described so the UI can render it generically."""

    name: str
    label: str
    args: dict[str, dict[str, Any]] = field(default_factory=dict)
    """arg name -> {"type": "int|float|str|enum|bool", "min", "max", "choices", "default"}"""
    confirm: bool = False
    """True for disruptive actions (router reboot, door unlock) -> UI asks before sending."""


@dataclass
class AdapterState:
    system: str
    online: bool
    data: dict[str, Any]
    updated_at: float
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "system": self.system,
            "online": self.online,
            "data": self.data,
            "updated_at": self.updated_at,
            "error": self.error,
        }


class AdapterError(Exception):
    """Raised by execute() for user-facing failures (bad args, device refused)."""


class Adapter:
    """Base class. Subclasses set `system`, `title`, `poll_seconds` and implement `_poll`/`_execute`."""

    system: str = "base"
    title: str = "Base"
    poll_seconds: int = 60
    icon: str = "box"

    def __init__(self) -> None:
        self._state = AdapterState(self.system, False, {}, 0.0, "not polled yet")
        self._lock = asyncio.Lock()

    # ---- public API used by scheduler / routes ----
    @property
    def state(self) -> AdapterState:
        return self._state

    def capabilities(self) -> list[Command]:
        return []

    def describe(self) -> dict[str, Any]:
        return {
            "system": self.system,
            "title": self.title,
            "icon": self.icon,
            "poll_seconds": self.poll_seconds,
            "commands": [
                {"name": c.name, "label": c.label, "args": c.args, "confirm": c.confirm}
                for c in self.capabilities()
            ],
        }

    async def poll(self) -> AdapterState:
        async with self._lock:
            try:
                data = await asyncio.wait_for(self._poll(), timeout=max(10, self.poll_seconds - 5))
                self._state = AdapterState(self.system, True, data, time.time())
            except Exception as exc:  # noqa: BLE001 - adapters degrade, never crash the loop
                log.warning("%s poll failed: %s", self.system, exc)
                self._state = AdapterState(
                    self.system, False, self._state.data, time.time(), f"{type(exc).__name__}: {exc}"
                )
            return self._state

    async def execute(self, command: str, args: dict[str, Any]) -> dict[str, Any]:
        cmd = next((c for c in self.capabilities() if c.name == command), None)
        if cmd is None:
            raise AdapterError(f"unknown command '{command}' for {self.system}")
        clean = validate_args(cmd, args)
        async with self._lock:
            result = await self._execute(command, clean)
        # refresh state right after a command so the UI reflects it
        await self.poll()
        return result or {"ok": True}

    async def close(self) -> None:  # optional cleanup hook
        return None

    # ---- to implement ----
    async def _poll(self) -> dict[str, Any]:
        raise NotImplementedError

    async def _execute(self, command: str, args: dict[str, Any]) -> dict[str, Any] | None:
        raise NotImplementedError


def validate_args(cmd: Command, args: dict[str, Any]) -> dict[str, Any]:
    clean: dict[str, Any] = {}
    for name, spec in cmd.args.items():
        if name not in args:
            if "default" in spec:
                clean[name] = spec["default"]
                continue
            raise AdapterError(f"missing argument '{name}'")
        value = args[name]
        t = spec.get("type", "str")
        try:
            if t == "int":
                value = int(value)
            elif t == "float":
                value = float(value)
            elif t == "bool":
                value = value if isinstance(value, bool) else str(value).lower() in ("1", "true", "on")
            elif t == "enum":
                if value not in spec["choices"]:
                    raise AdapterError(f"'{name}' must be one of {spec['choices']}")
            else:
                value = str(value)
        except (TypeError, ValueError) as exc:
            raise AdapterError(f"argument '{name}' is not a valid {t}") from exc
        if "min" in spec and value < spec["min"]:
            raise AdapterError(f"'{name}' must be >= {spec['min']}")
        if "max" in spec and value > spec["max"]:
            raise AdapterError(f"'{name}' must be <= {spec['max']}")
        clean[name] = value
    return clean
