"""Panasonic Comfort Cloud via `aio-panasonic-comfort-cloud` (same library Home Assistant uses).

IMPORTANT: use a SECOND Comfort Cloud account and share the units to it from the phone app,
otherwise logging in here can log the phone out. 2FA must be set to SMS on that account.
The library caches its token in ~/.panasonic-settings (mounted as a volume in Docker).

Probe:  python -m app.adapters.panasonic_cc --user <email> --password <pw>
"""
from __future__ import annotations

import asyncio
import sys
from typing import Any

import aiohttp

from .base import Adapter, AdapterError, Command

MODES = ["auto", "cool", "heat", "dry", "fan"]
FANS = ["auto", "low", "lowmid", "mid", "highmid", "high"]
_MODE_ENUM = {"auto": "Auto", "cool": "Cool", "heat": "Heat", "dry": "Dry", "fan": "Fan"}
_FAN_ENUM = {"auto": "Auto", "low": "Low", "lowmid": "LowMid", "mid": "Mid", "highmid": "HighMid", "high": "High"}


def _enum_name(v: Any) -> str | None:
    return v.name.lower() if v is not None and hasattr(v, "name") else None


class PanasonicAdapter(Adapter):
    system, title, icon = "panasonic", "Panasonic Comfort Cloud", "thermometer"

    def __init__(self, username: str, password: str, poll_seconds: int = 120) -> None:
        super().__init__()
        self.username, self.password, self.poll_seconds = username, password, poll_seconds
        self._session: aiohttp.ClientSession | None = None
        self._client = None
        self._devices: dict[str, Any] = {}  # id -> PanasonicDevice

    async def _ensure(self) -> None:
        if self._client is not None:
            return
        from aio_panasonic_comfort_cloud import ApiClient  # type: ignore[import-not-found]

        self._session = aiohttp.ClientSession()
        client = ApiClient(self.username, self.password, self._session)
        await client.start_session()
        for info in client.get_devices():
            self._devices[info.id] = await client.get_device(info)
        self._client = client

    def capabilities(self) -> list[Command]:
        unit = {"type": "enum", "choices": list(self._devices) or ["<not loaded>"]}
        return [
            Command("set_power", "Power", {"unit": unit, "on": {"type": "bool"}}),
            Command("set_mode", "Mode", {"unit": unit, "mode": {"type": "enum", "choices": MODES}}),
            Command("set_temperature", "Target °C", {"unit": unit, "target_c": {"type": "float", "min": 16, "max": 30, "default": 22}}),
            Command("set_fan", "Fan", {"unit": unit, "fan": {"type": "enum", "choices": FANS}}),
        ]

    @staticmethod
    def snapshot(dev: Any) -> dict[str, Any]:
        p = dev.parameters
        return {
            "name": dev.info.name,
            "model": dev.info.model,
            "power": _enum_name(p.power) == "on",
            "mode": _enum_name(p.mode),
            "target_c": p.target_temperature,
            "inside_c": p.inside_temperature if dev.has_inside_temperature else None,
            "outside_c": p.outside_temperature if dev.has_outside_temperature else None,
            "fan": _enum_name(p.fan_speed),
            "eco": _enum_name(p.eco_mode),
            "nanoe": _enum_name(p.nanoe_mode) if dev.has_nanoe else None,
            "last_update": dev.last_update.isoformat() if dev.last_update else None,
        }

    async def _poll(self) -> dict[str, Any]:
        await self._ensure()
        for dev in self._devices.values():
            await self._client.try_update_device(dev)
        return {"units": {i: self.snapshot(d) for i, d in self._devices.items()}}

    async def _execute(self, command: str, args: dict[str, Any]) -> dict[str, Any] | None:
        await self._ensure()
        dev = self._devices.get(args["unit"])
        if dev is None:
            raise AdapterError(f"unknown unit {args['unit']}")
        req = self._client.new_change_request(dev)
        if command == "set_power":
            req.set_power_mode("On" if args["on"] else "Off")
        elif command == "set_mode":
            req.set_hvac_mode(_MODE_ENUM[args["mode"]])
        elif command == "set_temperature":
            req.set_target_temperature(args["target_c"])
        elif command == "set_fan":
            req.set_fan_speed(_FAN_ENUM[args["fan"]])
        if req.has_changes():
            await self._client.set_device_raw(dev, req.build())
        return None

    async def close(self) -> None:
        if self._client is not None:
            try:
                await self._client.stop_session()
            except Exception:  # noqa: BLE001
                pass
        if self._session is not None:
            await self._session.close()


if __name__ == "__main__":  # pragma: no cover - manual probe
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--user", required=True)
    p.add_argument("--password", required=True)
    a = p.parse_args()

    async def main() -> None:
        ad = PanasonicAdapter(a.user, a.password)
        print((await ad.poll()).as_dict())
        await ad.close()

    asyncio.run(main())
    sys.exit(0)
