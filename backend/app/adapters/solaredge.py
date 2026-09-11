"""SolarEdge official Monitoring API (site-level API key).

Docs: https://knowledge-center.solaredge.com/sites/kc/files/se_monitoring_api.pdf
Limit: 300 requests/day per site key. One poll = 2 requests (overview + inverters list is cached).
At the default 15 min interval that is 192/day.

Probe:  python -m app.adapters.solaredge --site <id> --key <key>
"""
from __future__ import annotations

import asyncio
import sys
import time
from typing import Any

import httpx

from .base import Adapter

BASE = "https://monitoringapi.solaredge.com"


def parse_overview(body: dict[str, Any]) -> dict[str, Any]:
    ov = body["overview"]
    return {
        "power_w": float(ov["currentPower"]["power"]),
        "energy_today_wh": float(ov["lastDayData"]["energy"]),
        "energy_month_wh": float(ov["lastMonthData"]["energy"]),
        "energy_year_wh": float(ov["lastYearData"]["energy"]),
        "energy_lifetime_wh": float(ov["lifeTimeData"]["energy"]),
        "last_update": ov.get("lastUpdateTime"),
    }


def parse_details(body: dict[str, Any]) -> dict[str, Any]:
    d = body["details"]
    return {
        "site_name": d.get("name"),
        "peak_power_kwp": d.get("peakPower"),
        "site_status": d.get("status"),
        "inverter_status": "OK" if d.get("status") == "Active" else d.get("status"),
        "installed": d.get("installationDate"),
    }


class SolarEdgeAdapter(Adapter):
    system, title, icon = "solaredge", "SolarEdge PV", "sun"

    def __init__(self, site_id: str, api_key: str, poll_seconds: int = 900) -> None:
        super().__init__()
        self.site_id, self.api_key, self.poll_seconds = site_id, api_key, poll_seconds
        self._client = httpx.AsyncClient(base_url=BASE, timeout=20)
        self._details: dict[str, Any] | None = None
        self._details_at = 0.0

    async def _get(self, path: str) -> dict[str, Any]:
        r = await self._client.get(path, params={"api_key": self.api_key})
        if r.status_code == 429:
            raise RuntimeError("SolarEdge rate limit (300/day) hit; back off")
        r.raise_for_status()
        return r.json()

    async def _poll(self) -> dict[str, Any]:
        data = parse_overview(await self._get(f"/site/{self.site_id}/overview"))
        # site details change ~never: refresh once a day to save quota
        if self._details is None or time.time() - self._details_at > 86400:
            self._details = parse_details(await self._get(f"/site/{self.site_id}/details"))
            self._details_at = time.time()
        return {**self._details, **data}

    async def close(self) -> None:
        await self._client.aclose()


if __name__ == "__main__":  # pragma: no cover - manual probe
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--site", required=True)
    p.add_argument("--key", required=True)
    a = p.parse_args()

    async def main() -> None:
        ad = SolarEdgeAdapter(a.site, a.key)
        print((await ad.poll()).as_dict())
        await ad.close()

    asyncio.run(main())
    sys.exit(0)
