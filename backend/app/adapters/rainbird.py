"""Rain Bird LNK WiFi module, local LAN, via `pyrainbird` (the library behind the Home Assistant integration).

The LNK module serves one request at a time; the Rain Bird app and this dashboard compete for it,
so keep the poll interval slow (>= 60 s) and expect the odd timeout while the phone app is open.

Probe:  python -m app.adapters.rainbird --host 192.168.x.x --password <LNK password>
"""
from __future__ import annotations

import asyncio
import sys
from typing import Any

from .base import Adapter, Command


class RainBirdAdapter(Adapter):
    system, title, icon = "rainbird", "Rain Bird irrigation", "droplets"

    def __init__(self, host: str, password: str, zones: int = 8, poll_seconds: int = 90) -> None:
        super().__init__()
        self.host, self.password, self.zones, self.poll_seconds = host, password, zones, poll_seconds
        self._ctrl = None
        self._model: str | None = None

    async def _ensure(self) -> None:
        if self._ctrl is not None:
            return
        import aiohttp
        from pyrainbird import async_client  # type: ignore[import-not-found]

        self._session = aiohttp.ClientSession()
        self._ctrl = async_client.CreateController(self._session, self.host, self.password)
        info = await self._ctrl.get_model_and_version()
        self._model = f"{info.model_name} v{info.major}.{info.minor}"
        try:
            self.zones = len(await self._ctrl.get_available_stations()) or self.zones
        except Exception:  # noqa: BLE001 - not all firmware answers this
            pass

    def capabilities(self) -> list[Command]:
        return [
            Command("run_zone", "Run zone", {"zone": {"type": "int", "min": 1, "max": self.zones}, "minutes": {"type": "int", "min": 1, "max": 120, "default": 5}}),
            Command("stop", "Stop all"),
            Command("rain_delay", "Rain delay (days)", {"days": {"type": "int", "min": 0, "max": 14, "default": 1}}),
        ]

    async def _poll(self) -> dict[str, Any]:
        await self._ensure()
        states = await self._ctrl.get_zone_states()
        active = [z for z in range(1, self.zones + 1) if states.active(z)]
        rain = await self._ctrl.get_rain_sensor_state()
        delay = await self._ctrl.get_rain_delay()
        return {
            "model": self._model,
            "zones": {str(z): {"name": f"Zone {z}", "running": z in active} for z in range(1, self.zones + 1)},
            "active_zone": active[0] if active else None,
            "rain_sensor": bool(rain),
            "rain_delay_days": int(delay),
        }

    async def _execute(self, command: str, args: dict[str, Any]) -> dict[str, Any] | None:
        await self._ensure()
        if command == "run_zone":
            await self._ctrl.irrigate_zone(args["zone"], args["minutes"])
        elif command == "stop":
            await self._ctrl.stop_irrigation()
        elif command == "rain_delay":
            await self._ctrl.set_rain_delay(args["days"])
        return None

    async def close(self) -> None:
        if self._ctrl is not None:
            await self._session.close()


if __name__ == "__main__":  # pragma: no cover - manual probe
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--host", required=True)
    p.add_argument("--password", required=True)
    a = p.parse_args()

    async def main() -> None:
        ad = RainBirdAdapter(a.host, a.password)
        print((await ad.poll()).as_dict())
        await ad.close()

    asyncio.run(main())
    sys.exit(0)
