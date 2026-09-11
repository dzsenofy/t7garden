"""ZTE G5B (and other ZTE MC/MU/G-series CPEs) local admin JSON API.

The web UI talks to two endpoints on the router:
  GET  /goform/goform_get_cmd_process?multi_data=1&cmd=a,b,c      -> {"a":..,"b":..}
  POST /goform/goform_set_cmd_process  (goformId=LOGIN|REBOOT_DEVICE|...)

Login on current firmware: password = SHA256(SHA256(pw).upper() + LD).upper() where LD comes
from cmd=LD. Set-requests need AD = SHA256(SHA256(cr_version+wa_inner_version).upper() + RD).upper().
Older firmware accepts base64(pw) instead. Both are tried.

Probe:  python -m app.adapters.zte_g5b --host 192.168.0.1 --password <admin pw>
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import sys
from typing import Any

import httpx

from .base import Adapter, Command

STATUS_KEYS = [
    "network_type", "network_provider", "nr5g_action_band", "lte_band", "nr5g_rsrp", "lte_rsrp",
    "Z5g_SINR", "lte_snr", "signalbar", "wan_ipaddr", "realtime_rx_bytes", "realtime_tx_bytes",
    "monthly_rx_bytes", "monthly_tx_bytes", "realtime_time", "station_list", "simcard_roam",
    "sim_status", "modem_main_state", "wa_inner_version", "cr_version", "ppp_status", "loginfo",
]


def sha256_upper(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest().upper()


def parse_status(raw: dict[str, Any]) -> dict[str, Any]:
    def num(k: str, scale: float = 1.0) -> float | None:
        v = raw.get(k)
        try:
            return round(float(v) * scale, 1) if v not in (None, "") else None
        except ValueError:
            return None

    is5g = "5G" in str(raw.get("network_type", "")).upper() or bool(raw.get("nr5g_action_band"))
    stations = raw.get("station_list") or []
    return {
        "network": raw.get("network_type"),
        "operator": raw.get("network_provider"),
        "band": raw.get("nr5g_action_band") if is5g else raw.get("lte_band"),
        "rsrp_dbm": num("nr5g_rsrp") if is5g else num("lte_rsrp"),
        "sinr_db": num("Z5g_SINR") if is5g else num("lte_snr"),
        "signal_bars": int(raw.get("signalbar") or 0),
        "wan_ip": raw.get("wan_ipaddr"),
        "connected": raw.get("ppp_status") == "ppp_connected",
        "sim_status": raw.get("sim_status"),
        "modem_state": raw.get("modem_main_state"),
        "data_session_mb": round(((num("realtime_rx_bytes") or 0) + (num("realtime_tx_bytes") or 0)) / 1e6, 1),
        "data_month_gb": round(((num("monthly_rx_bytes") or 0) + (num("monthly_tx_bytes") or 0)) / 1e9, 2),
        "uptime_h": round((num("realtime_time") or 0) / 3600, 1),
        "clients": len(stations) if isinstance(stations, list) else stations,
        "firmware": raw.get("wa_inner_version"),
    }


class ZteG5bAdapter(Adapter):
    system, title, icon = "zte", "ZTE G5B 5G router", "wifi"

    def __init__(self, host: str, password: str, poll_seconds: int = 60) -> None:
        super().__init__()
        self.host, self.password, self.poll_seconds = host, password, poll_seconds
        self._client = httpx.AsyncClient(
            base_url=f"http://{host}", timeout=10,
            headers={"Referer": f"http://{host}/index.html", "X-Requested-With": "XMLHttpRequest"},
        )
        self._logged_in = False

    async def _get(self, *cmds: str) -> dict[str, Any]:
        r = await self._client.get("/goform/goform_get_cmd_process", params={"isTest": "false", "multi_data": "1", "cmd": ",".join(cmds)})
        r.raise_for_status()
        return r.json()

    async def _set(self, goform_id: str, **fields: str) -> dict[str, Any]:
        r = await self._client.post("/goform/goform_set_cmd_process", data={"isTest": "false", "goformId": goform_id, **fields})
        r.raise_for_status()
        return r.json()

    async def _login(self) -> None:
        ld = (await self._get("LD")).get("LD", "")
        candidates = [sha256_upper(sha256_upper(self.password) + ld)] if ld else []
        candidates.append(base64.b64encode(self.password.encode()).decode())
        for pw in candidates:
            res = await self._set("LOGIN", password=pw)
            if str(res.get("result")) in ("0", "success"):
                self._logged_in = True
                return
        raise RuntimeError(f"router login failed: {res}")

    async def _ad(self) -> str:
        info = await self._get("wa_inner_version", "cr_version", "RD")
        return sha256_upper(sha256_upper(info.get("cr_version", "") + info.get("wa_inner_version", "")) + info.get("RD", ""))

    async def _poll(self) -> dict[str, Any]:
        if not self._logged_in:
            await self._login()
        raw = await self._get(*STATUS_KEYS)
        if raw.get("loginfo") not in (None, "", "ok"):
            self._logged_in = False
            await self._login()
            raw = await self._get(*STATUS_KEYS)
        return parse_status(raw)

    def capabilities(self) -> list[Command]:
        return [Command("reboot", "Reboot router", confirm=True)]

    async def _execute(self, command: str, args: dict[str, Any]) -> dict[str, Any] | None:
        if not self._logged_in:
            await self._login()
        if command == "reboot":
            res = await self._set("REBOOT_DEVICE", AD=await self._ad())
            self._logged_in = False
            return {"router": res}
        return None

    async def close(self) -> None:
        await self._client.aclose()


if __name__ == "__main__":  # pragma: no cover - manual probe
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--host", default="192.168.0.1")
    p.add_argument("--password", required=True)
    a = p.parse_args()

    async def main() -> None:
        ad = ZteG5bAdapter(a.host, a.password)
        print((await ad.poll()).as_dict())
        await ad.close()

    asyncio.run(main())
    sys.exit(0)
