"""Broadlink-based split AC WiFi module (device type 0x4E2A, the one the AC Freedom app talks to).

Local UDP control, no cloud, using the `broadlink.climate.hvac` class shipped with python-broadlink
(supported: AUX, Tornado and other AC Freedom brands). The unit must have been paired to your WiFi
once via AC Freedom; after that the app is not needed. If the unit refuses local auth it is
"cloud-locked" -> re-pair it with AC Freedom and lock it to the LAN in the app.

Discovery:  python -m app.adapters.broadlink_ac --discover
Probe:      python -m app.adapters.broadlink_ac --host 192.168.x.x --mac aa:bb:cc:dd:ee:ff
"""
from __future__ import annotations

import asyncio
import sys
from typing import Any

from .base import Adapter, Command

MODES = ["auto", "cool", "dry", "heat", "fan"]
FANS = ["auto", "low", "mid", "high"]


def state_to_dict(raw: dict[str, Any]) -> dict[str, Any]:
    """Flatten the enum-valued dict from hvac.get_state() into JSON-friendly values."""
    return {
        "power": bool(raw["power"]),
        "mode": raw["mode"].name.lower(),
        "target_c": float(raw["target_temp"]),
        "fan": raw["speed"].name.lower(),
        "preset": raw["preset"].name.lower(),
        "swing_v": raw["swing_v"].name.lower(),
        "swing_h": raw["swing_h"].name.lower(),
        "sleep": bool(raw["sleep"]),
        "display": bool(raw["display"]),
        "health": bool(raw["health"]),
    }


class BroadlinkAcAdapter(Adapter):
    system, title, icon = "broadlink_ac", "AC (AC Freedom)", "wind"

    def __init__(self, host: str, mac: str, name: str = "AC", poll_seconds: int = 60, devtype: int = 0x4E2A) -> None:
        super().__init__()
        self.host, self.name, self.poll_seconds, self.devtype = host, name, poll_seconds, devtype
        self.mac = bytes.fromhex(mac.replace(":", "").replace("-", ""))
        self._dev = None

    def _ensure(self) -> None:
        if self._dev is not None:
            return
        from broadlink.climate import hvac  # type: ignore[import-not-found]

        dev = hvac((self.host, 80), self.mac, self.devtype, name=self.name)
        dev.timeout = 5
        if not dev.auth():
            raise RuntimeError("Broadlink auth failed (is the AC on the LAN and not cloud-locked?)")
        self._dev = dev

    def capabilities(self) -> list[Command]:
        return [
            Command("set_power", "Power", {"on": {"type": "bool"}}),
            Command("set_mode", "Mode", {"mode": {"type": "enum", "choices": MODES}}),
            Command("set_temperature", "Target °C", {"target_c": {"type": "float", "min": 16, "max": 32, "default": 23}}),
            Command("set_fan", "Fan", {"fan": {"type": "enum", "choices": FANS}}),
        ]

    async def _poll(self) -> dict[str, Any]:
        self._ensure()
        raw = await asyncio.to_thread(self._dev.get_state)
        return dict(state_to_dict(raw), name=self.name)

    async def _execute(self, command: str, args: dict[str, Any]) -> dict[str, Any] | None:
        self._ensure()
        dev = self._dev
        cur = await asyncio.to_thread(dev.get_state)  # set_state needs every field -> merge
        if command == "set_power":
            cur["power"] = args["on"]
        elif command == "set_mode":
            cur["mode"], cur["power"] = dev.Mode[args["mode"].upper()], True
        elif command == "set_temperature":
            cur["target_temp"] = args["target_c"]
        elif command == "set_fan":
            cur["speed"], cur["preset"] = dev.Speed[args["fan"].upper()], dev.Preset.NORMAL
        await asyncio.to_thread(dev.set_state, **cur)
        return None


if __name__ == "__main__":  # pragma: no cover - manual probe
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--discover", action="store_true")
    p.add_argument("--host")
    p.add_argument("--mac")
    a = p.parse_args()
    if a.discover:
        import broadlink  # type: ignore[import-not-found]

        for d in broadlink.discover(timeout=5):
            fw = "?"
            try:
                if d.auth():
                    fw = d.get_fwversion()  # compare with "Firmware Version" in AC Freedom's device info
            except Exception as exc:  # noqa: BLE001
                fw = f"auth failed: {exc}"
            print(f"{d.host[0]}  mac={d.mac.hex(':')}  type=0x{d.devtype:04X}  {d.type}  fw={fw}")
        sys.exit(0)

    async def main() -> None:
        ad = BroadlinkAcAdapter(a.host, a.mac)
        print((await ad.poll()).as_dict())

    asyncio.run(main())
    sys.exit(0)
