"""Hikvision NVR over local ISAPI (HTTP digest auth) + RTSP URLs handed to go2rtc for browser playback.

Create a dedicated NVR user (Configuration -> User Management) with Live View + Remote Playback
permissions instead of using admin.

Probe:  python -m app.adapters.hikvision_nvr --host 192.168.x.x --user <u> --password <p>
"""
from __future__ import annotations

import asyncio
import re
import sys
import xml.etree.ElementTree as ET
from typing import Any

import httpx

from .base import Adapter

NS = {"h": "http://www.hikvision.com/ver20/XMLSchema"}


def _txt(el: ET.Element | None, path: str) -> str | None:
    if el is None:
        return None
    node = el.find(path, NS)
    return node.text.strip() if node is not None and node.text else None


def parse_channels(xml: str) -> list[dict[str, Any]]:
    root = ET.fromstring(xml)
    out = []
    for ch in root.findall("h:InputProxyChannelStatus", NS) or root.findall("h:InputProxyChannel", NS):
        cid = int(_txt(ch, "h:id") or 0)
        name = _txt(ch, "h:sourceInputPortDescriptor/h:name") or _txt(ch, "h:name") or f"Camera {cid}"
        online = (_txt(ch, "h:online") or "true").lower() == "true"
        out.append({"id": cid, "name": name, "online": online})
    return out


def parse_hdd(xml: str) -> dict[str, Any]:
    root = ET.fromstring(xml)
    total = free = 0.0
    statuses = []
    for hdd in root.findall("h:hdd", NS):
        total += float(_txt(hdd, "h:capacity") or 0)
        free += float(_txt(hdd, "h:freeSpace") or 0)
        statuses.append(_txt(hdd, "h:status") or "?")
    return {
        "hdd_status": ",".join(statuses) or "none",
        "hdd_free_pct": round(free / total * 100) if total else None,
        "hdd_total_gb": round(total / 1024) if total else None,
    }


def parse_device_info(xml: str) -> dict[str, Any]:
    root = ET.fromstring(xml)
    return {"model": _txt(root, "h:model"), "firmware": _txt(root, "h:firmwareVersion"), "device_name": _txt(root, "h:deviceName")}


class HikvisionNvrAdapter(Adapter):
    system, title, icon = "hik_nvr", "Cameras (Hikvision NVR)", "video"

    def __init__(self, host: str, username: str, password: str, poll_seconds: int = 60) -> None:
        super().__init__()
        self.host, self.username, self.password, self.poll_seconds = host, username, password, poll_seconds
        self._client = httpx.AsyncClient(base_url=f"http://{host}", auth=httpx.DigestAuth(username, password), timeout=15)
        self._info: dict[str, Any] | None = None

    async def _get(self, path: str) -> str:
        r = await self._client.get(path)
        r.raise_for_status()
        return r.text

    def rtsp_url(self, channel: int, sub: bool = True) -> str:
        """RTSP URL for go2rtc. Channel N main stream = N01, sub stream = N02."""
        stream = f"{channel}{'02' if sub else '01'}"
        return f"rtsp://{self.username}:{self.password}@{self.host}:554/Streaming/Channels/{stream}"

    async def snapshot(self, channel: int) -> bytes:
        r = await self._client.get(f"/ISAPI/Streaming/channels/{channel}01/picture")
        r.raise_for_status()
        return r.content

    async def _poll(self) -> dict[str, Any]:
        if self._info is None:
            self._info = parse_device_info(await self._get("/ISAPI/System/deviceInfo"))
        channels = parse_channels(await self._get("/ISAPI/ContentMgmt/InputProxy/channels/status"))
        for c in channels:
            c["snapshot"] = f"/api/hik_nvr/snapshot/{c['id']}"
            c["stream"] = f"cam{c['id']}"
        try:
            hdd = parse_hdd(await self._get("/ISAPI/ContentMgmt/Storage/hdd"))
        except Exception:  # noqa: BLE001
            hdd = {"hdd_status": "unknown"}
        return {**self._info, **hdd, "channels": channels, "recording": True}

    async def close(self) -> None:
        await self._client.aclose()


def go2rtc_streams(host: str, username: str, password: str, channel_ids: list[int]) -> str:
    """Render the go2rtc.yaml `streams:` block for these channels (used by deploy/gen_go2rtc.py)."""
    lines = ["streams:"]
    for cid in channel_ids:
        lines.append(f"  cam{cid}: rtsp://{username}:{password}@{host}:554/Streaming/Channels/{cid}02")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":  # pragma: no cover - manual probe
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--host", required=True)
    p.add_argument("--user", required=True)
    p.add_argument("--password", required=True)
    a = p.parse_args()

    async def main() -> None:
        ad = HikvisionNvrAdapter(a.host, a.user, a.password)
        st = await ad.poll()
        print(st.as_dict())
        if st.online:
            ids = [c["id"] for c in st.data["channels"]]
            print("\n# go2rtc.yaml snippet:\n" + re.sub(r":[^:@]+@", ":***@", go2rtc_streams(a.host, a.user, a.password, ids)))
        await ad.close()

    asyncio.run(main())
    sys.exit(0)
