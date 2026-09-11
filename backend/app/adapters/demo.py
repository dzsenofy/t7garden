"""Synthetic adapters so the dashboard can be developed and demoed without any device.

Enabled with DEMO_MODE=true. Each mirrors the data shape of the real adapter it stands in for.
"""
from __future__ import annotations

import math
import random
import time
from typing import Any

from .base import Adapter, Command


class DemoSolarEdge(Adapter):
    system, title, icon, poll_seconds = "solaredge", "SolarEdge PV", "sun", 10

    async def _poll(self) -> dict[str, Any]:
        hour = time.localtime().tm_hour + time.localtime().tm_min / 60
        power = max(0.0, 6200 * math.sin((hour - 6) / 14 * math.pi)) if 6 < hour < 20 else 0.0
        return {
            "power_w": round(power + random.uniform(-100, 100), 0),
            "energy_today_wh": 18420,
            "energy_month_wh": 412300,
            "energy_lifetime_wh": 38_211_000,
            "peak_power_kwp": 8.2,
            "inverter_status": "OK",
            "last_update": time.strftime("%Y-%m-%d %H:%M"),
        }


class DemoPanasonic(Adapter):
    system, title, icon, poll_seconds = "panasonic", "Panasonic Comfort Cloud", "thermometer", 10

    def __init__(self) -> None:
        super().__init__()
        self.units = {
            "living": {"name": "Living room", "power": True, "mode": "cool", "target_c": 24.0, "inside_c": 25.4, "outside_c": 31.0, "fan": "auto"},
            "bedroom": {"name": "Bedroom", "power": False, "mode": "heat", "target_c": 21.0, "inside_c": 26.1, "outside_c": 31.0, "fan": "auto"},
        }

    def capabilities(self) -> list[Command]:
        ids = list(self.units)
        return [
            Command("set_power", "Power", {"unit": {"type": "enum", "choices": ids}, "on": {"type": "bool"}}),
            Command("set_mode", "Mode", {"unit": {"type": "enum", "choices": ids}, "mode": {"type": "enum", "choices": ["auto", "cool", "heat", "dry", "fan"]}}),
            Command("set_temperature", "Target °C", {"unit": {"type": "enum", "choices": ids}, "target_c": {"type": "float", "min": 16, "max": 30, "default": 22}}),
        ]

    async def _poll(self) -> dict[str, Any]:
        for u in self.units.values():
            u["inside_c"] = round(u["inside_c"] + random.uniform(-0.2, 0.2), 1)
        return {"units": self.units}

    async def _execute(self, command: str, args: dict[str, Any]) -> dict[str, Any] | None:
        u = self.units[args["unit"]]
        if command == "set_power":
            u["power"] = args["on"]
        elif command == "set_mode":
            u["mode"] = args["mode"]
        elif command == "set_temperature":
            u["target_c"] = args["target_c"]
        return None


class DemoZte(Adapter):
    system, title, icon, poll_seconds = "zte", "ZTE G5B 5G router", "wifi", 10

    async def _poll(self) -> dict[str, Any]:
        return {
            "network": "5G NSA", "operator": "Telekom HU", "band": "n78", "rsrp_dbm": random.randint(-95, -85),
            "sinr_db": random.randint(12, 22), "signal_bars": 4, "wan_ip": "10.x.x.x (CGNAT)",
            "data_today_mb": 3120, "data_month_gb": 84.3, "clients": 14, "uptime_h": 213,
            "sim_status": "OK", "firmware": "BD_HUNG5BV1.0.0B05",
        }

    def capabilities(self) -> list[Command]:
        return [Command("reboot", "Reboot router", confirm=True)]

    async def _execute(self, command: str, args: dict[str, Any]) -> dict[str, Any] | None:
        return {"ok": True, "note": "demo: reboot simulated"}


class DemoRainBird(Adapter):
    system, title, icon, poll_seconds = "rainbird", "Rain Bird irrigation", "droplets", 10

    def __init__(self) -> None:
        super().__init__()
        self.active: int | None = None
        self.until = 0.0

    def capabilities(self) -> list[Command]:
        return [
            Command("run_zone", "Run zone", {"zone": {"type": "int", "min": 1, "max": 8}, "minutes": {"type": "int", "min": 1, "max": 60, "default": 5}}),
            Command("stop", "Stop all"),
            Command("rain_delay", "Rain delay (days)", {"days": {"type": "int", "min": 0, "max": 14, "default": 1}}),
        ]

    async def _poll(self) -> dict[str, Any]:
        if self.active and time.time() > self.until:
            self.active = None
        zones = {str(i): {"name": f"Zone {i}", "running": self.active == i} for i in range(1, 9)}
        return {"zones": zones, "active_zone": self.active, "rain_sensor": False, "rain_delay_days": 0, "model": "ESP-TM2 (demo)"}

    async def _execute(self, command: str, args: dict[str, Any]) -> dict[str, Any] | None:
        if command == "run_zone":
            self.active, self.until = args["zone"], time.time() + args["minutes"] * 60
        elif command == "stop":
            self.active = None
        return None


class DemoBroadlinkAc(Adapter):
    system, title, icon, poll_seconds = "broadlink_ac", "AC (AC Freedom)", "wind", 10

    def __init__(self) -> None:
        super().__init__()
        self.s = {"power": True, "mode": "cool", "target_c": 23.0, "ambient_c": 24.8, "fan": "auto", "swing": "off"}

    def capabilities(self) -> list[Command]:
        return [
            Command("set_power", "Power", {"on": {"type": "bool"}}),
            Command("set_mode", "Mode", {"mode": {"type": "enum", "choices": ["auto", "cool", "heat", "dry", "fan"]}}),
            Command("set_temperature", "Target °C", {"target_c": {"type": "float", "min": 16, "max": 32, "default": 23}}),
            Command("set_fan", "Fan", {"fan": {"type": "enum", "choices": ["auto", "low", "mid", "high"]}}),
        ]

    async def _poll(self) -> dict[str, Any]:
        self.s["ambient_c"] = round(self.s["ambient_c"] + random.uniform(-0.1, 0.1), 1)
        return dict(self.s, name="Guest room AC")

    async def _execute(self, command: str, args: dict[str, Any]) -> dict[str, Any] | None:
        if command == "set_power":
            self.s["power"] = args["on"]
        elif command == "set_mode":
            self.s["mode"] = args["mode"]
        elif command == "set_temperature":
            self.s["target_c"] = args["target_c"]
        elif command == "set_fan":
            self.s["fan"] = args["fan"]
        return None


class DemoHikNvr(Adapter):
    system, title, icon, poll_seconds = "hik_nvr", "Cameras (Hikvision NVR)", "video", 10

    async def _poll(self) -> dict[str, Any]:
        return {
            "model": "DS-7608NI (demo)", "hdd_status": "OK", "hdd_free_pct": 37, "recording": True,
            "channels": [
                {"id": 1, "name": "Gate", "online": True, "snapshot": "/api/hik_nvr/snapshot/1", "stream": "cam1"},
                {"id": 2, "name": "Garden", "online": True, "snapshot": "/api/hik_nvr/snapshot/2", "stream": "cam2"},
                {"id": 3, "name": "Terrace", "online": False, "snapshot": "/api/hik_nvr/snapshot/3", "stream": "cam3"},
                {"id": 4, "name": "Driveway", "online": True, "snapshot": "/api/hik_nvr/snapshot/4", "stream": "cam4"},
            ],
            "last_motion": {"channel": 2, "at": time.strftime("%H:%M")},
        }


class DemoDoorbell(Adapter):
    system, title, icon, poll_seconds = "doorbell", "Doorbell (Hik-Connect)", "bell", 10

    async def _poll(self) -> dict[str, Any]:
        return {"name": "Front door", "online": True, "call_status": "idle", "last_call": "yesterday 18:42", "locks": ["Gate lock"]}

    def capabilities(self) -> list[Command]:
        return [Command("unlock", "Unlock gate", {"lock_index": {"type": "int", "min": 0, "max": 3, "default": 0}}, confirm=True)]

    async def _execute(self, command: str, args: dict[str, Any]) -> dict[str, Any] | None:
        return {"ok": True, "note": "demo: unlock simulated"}


def demo_adapters() -> list[Adapter]:
    return [DemoSolarEdge(), DemoPanasonic(), DemoZte(), DemoRainBird(), DemoBroadlinkAc(), DemoHikNvr(), DemoDoorbell()]
