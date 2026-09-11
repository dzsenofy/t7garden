"""Builds the adapter list from settings. Only systems with credentials configured are enabled."""
from __future__ import annotations

import logging

from .adapters.base import Adapter
from .config import Settings

log = logging.getLogger(__name__)


def build_adapters(s: Settings) -> list[Adapter]:
    if s.demo_mode:
        from .adapters.demo import demo_adapters

        log.warning("DEMO_MODE is on: using synthetic adapters")
        return demo_adapters()

    adapters: list[Adapter] = []

    if s.solaredge_site_id and s.solaredge_api_key:
        from .adapters.solaredge import SolarEdgeAdapter

        adapters.append(SolarEdgeAdapter(s.solaredge_site_id, s.solaredge_api_key, s.solaredge_poll_seconds))

    if s.panasonic_username and s.panasonic_password:
        from .adapters.panasonic_cc import PanasonicAdapter

        adapters.append(PanasonicAdapter(s.panasonic_username, s.panasonic_password, s.panasonic_poll_seconds))

    if s.zte_host and s.zte_password:
        from .adapters.zte_g5b import ZteG5bAdapter

        adapters.append(ZteG5bAdapter(s.zte_host, s.zte_password, s.zte_poll_seconds))

    if s.rainbird_host and s.rainbird_password:
        from .adapters.rainbird import RainBirdAdapter

        adapters.append(RainBirdAdapter(s.rainbird_host, s.rainbird_password, s.rainbird_zones, s.rainbird_poll_seconds))

    if s.broadlink_ac_host and s.broadlink_ac_mac:
        from .adapters.broadlink_ac import BroadlinkAcAdapter

        adapters.append(BroadlinkAcAdapter(s.broadlink_ac_host, s.broadlink_ac_mac, s.broadlink_ac_name, s.broadlink_ac_poll_seconds, s.broadlink_ac_devtype))

    if s.hik_nvr_host and s.hik_nvr_username and s.hik_nvr_password:
        from .adapters.hikvision_nvr import HikvisionNvrAdapter

        adapters.append(HikvisionNvrAdapter(s.hik_nvr_host, s.hik_nvr_username, s.hik_nvr_password, s.hik_nvr_poll_seconds))

    if s.hikconnect_username and s.hikconnect_password:
        from .adapters.hikconnect_doorbell import HikConnectDoorbellAdapter

        adapters.append(HikConnectDoorbellAdapter(s.hikconnect_username, s.hikconnect_password, s.hikconnect_poll_seconds))

    if not adapters:
        log.warning("No system configured. Fill .env or set DEMO_MODE=true")
    else:
        log.info("Enabled systems: %s", ", ".join(a.system for a in adapters))
    return adapters
