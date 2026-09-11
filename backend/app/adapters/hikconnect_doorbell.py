"""Hik-Connect cloud (video doorbell / intercom) via the unofficial `hikconnect` library.

Only the doorbell goes through the cloud; the NVR and cameras are local (see hikvision_nvr.py).
The library logs in with your Hik-Connect email/password; it does not affect the phone app session.

Probe:  python -m app.adapters.hikconnect_doorbell --user <email> --password <pw>
"""
from __future__ import annotations

import asyncio
import sys
from typing import Any

from .base import Adapter, AdapterError, Command


class HikConnectDoorbellAdapter(Adapter):
    system, title, icon = "doorbell", "Doorbell (Hik-Connect)", "bell"

    def __init__(self, username: str, password: str, poll_seconds: int = 120) -> None:
        super().__init__()
        self.username, self.password, self.poll_seconds = username, password, poll_seconds
        self._api = None
        self._devices: list[dict[str, Any]] = []

    async def _ensure(self) -> None:
        if self._api is not None:
            return
        from hikconnect.api import HikConnect  # type: ignore[import-not-found]

        self._api = HikConnect()
        await self._api.__aenter__()
        await self._api.login(self.username, self.password)

    async def _poll(self) -> dict[str, Any]:
        await self._ensure()
        if self._api.is_refresh_login_needed():
            await self._api.refresh_login()
        devices = []
        async for d in self._api.get_devices():
            cams = [c async for c in self._api.get_cameras(d["serial"])]
            try:
                call = await self._api.get_call_status(d["serial"])
            except Exception:  # noqa: BLE001 - not every device type answers this
                call = None
            devices.append({
                "serial": d["serial"], "name": d.get("name"), "type": d.get("type"), "version": d.get("version"),
                "online": bool(d.get("is_online", True)), "local_ip": d.get("local_ip"), "wifi_signal": d.get("wifi_signal"),
                "locks": d.get("locks", {}),
                "cameras": [{"id": c.get("id"), "name": c.get("name"), "channel": c.get("channel_number"), "online": c.get("signal_status")} for c in cams],
                "call_status": call,
            })
        self._devices = devices
        first = devices[0] if devices else {}
        return {"devices": devices, "name": first.get("name"), "online": first.get("online"), "call_status": first.get("call_status")}

    def capabilities(self) -> list[Command]:
        return [Command("unlock", "Unlock door", {"device_index": {"type": "int", "min": 0, "max": 9, "default": 0},
                                                  "channel": {"type": "int", "min": 1, "max": 8, "default": 1},
                                                  "lock_index": {"type": "int", "min": 0, "max": 3, "default": 0}}, confirm=True)]

    async def _execute(self, command: str, args: dict[str, Any]) -> dict[str, Any] | None:
        await self._ensure()
        if not self._devices:
            await self._poll()
        try:
            dev = self._devices[args["device_index"]]
        except IndexError as exc:
            raise AdapterError("no such device") from exc
        if command == "unlock":
            await self._api.unlock(dev["serial"], args["channel"], args["lock_index"])
        return None

    async def close(self) -> None:
        if self._api is not None:
            await self._api.__aexit__(None, None, None)


if __name__ == "__main__":  # pragma: no cover - manual probe
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--user", required=True)
    p.add_argument("--password", required=True)
    a = p.parse_args()

    async def main() -> None:
        ad = HikConnectDoorbellAdapter(a.user, a.password)
        print((await ad.poll()).as_dict())
        await ad.close()

    asyncio.run(main())
    sys.exit(0)
