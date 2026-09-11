"""Runtime configuration. Every secret comes from the environment / .env, never from code."""
from __future__ import annotations

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- app ---
    app_name: str = "Siófok Command Control"
    db_path: str = "data/scc.db"
    demo_mode: bool = Field(default=False, description="Use fake adapters with synthetic data")
    log_level: str = "INFO"
    dashboard_token: str | None = Field(
        default=None,
        description="Optional shared secret; if set, every request needs 'Authorization: Bearer <token>'",
    )

    # --- SolarEdge (official monitoring API) ---
    solaredge_site_id: str | None = None
    solaredge_api_key: str | None = None
    solaredge_poll_seconds: int = 900  # 300 req/day limit -> 15 min default

    # --- Panasonic Comfort Cloud (use a SECOND account with the units shared to it) ---
    panasonic_username: str | None = None
    panasonic_password: str | None = None
    panasonic_poll_seconds: int = 120

    # --- ZTE G5B router (local admin API) ---
    zte_host: str | None = None
    zte_password: str | None = None
    zte_poll_seconds: int = 60

    # --- Rain Bird LNK WiFi module (local) ---
    rainbird_host: str | None = None
    rainbird_password: str | None = None
    rainbird_zones: int = 8
    rainbird_poll_seconds: int = 90  # LNK handles one request at a time; keep this slow

    # --- Broadlink-based AC (AC Freedom app), local UDP ---
    broadlink_ac_host: str | None = None
    broadlink_ac_mac: str | None = None  # aa:bb:cc:dd:ee:ff
    broadlink_ac_name: str = "AC"
    broadlink_ac_devtype: int = 0x4E2A  # override if `--discover` reports a different type for the AC module
    broadlink_ac_poll_seconds: int = 60

    # --- Hikvision NVR (local ISAPI + RTSP) ---
    hik_nvr_host: str | None = None
    hik_nvr_username: str | None = None
    hik_nvr_password: str | None = None
    hik_nvr_poll_seconds: int = 60
    go2rtc_public_url: str = "/stream"  # browser-facing path proxied to go2rtc

    # --- Hik-Connect cloud (doorbell) ---
    hikconnect_username: str | None = None
    hikconnect_password: str | None = None
    hikconnect_poll_seconds: int = 120


    @field_validator("broadlink_ac_devtype", mode="before")
    @classmethod
    def _hex_ok(cls, v):  # allow 0x4E2A in .env
        return int(v, 0) if isinstance(v, str) else v


settings = Settings()


