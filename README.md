# Siófok Command Control

One dashboard, desktop and phone, for the six smart-home systems at the Siófok house:

| Tile | System | How it is reached | Control |
|---|---|---|---|
| Cameras | Hikvision NVR via Hik-Connect | **Local** ISAPI + RTSP → go2rtc | snapshots, live view |
| Doorbell | Hik-Connect cloud | `hikconnect` library | call status, unlock |
| Panasonic Comfort Cloud | Panasonic cloud | `aio-panasonic-comfort-cloud` | power, mode, temp, fan |
| AC (AC Freedom) | Broadlink AC WiFi module | **Local** UDP, `broadlink.climate.hvac` | power, mode, temp, fan |
| Rain Bird irrigation | LNK WiFi module | **Local**, `pyrainbird` | run zone, stop, rain delay |
| SolarEdge PV | Official monitoring API | site API key | read-only |
| ZTE G5B 5G router | Router admin API | **Local** JSON API | reboot |

No phone device-ID is needed for any of them. Four are talked to directly on the LAN; SolarEdge has an
official key; Panasonic and Hik-Connect use normal account logins (Panasonic through a **second** account
so the phone app stays logged in).

## Layout

```
backend/    FastAPI + one adapter per system (app/adapters/*.py), SQLite event history, WebSocket push
frontend/   Vite + React + Tailwind PWA (installable on the phone home screen)
deploy/     docker-compose.yml, Caddyfile, go2rtc.yaml, Tailscale serve config
.env.example  every setting, documented
```

Architecture: browser → Tailscale (HTTPS, no open ports) → Caddy → FastAPI → adapters → devices/clouds.
Each adapter polls on its own interval; state changes are stored in SQLite and pushed over `/ws`.
Adapters never crash the loop: a device that stops answering shows as *offline* with the last known data.

## Run it locally (demo mode, no devices)

```bash
cd backend && python -m venv .venv && .venv/Scripts/pip install -e ".[dev]"
DEMO_MODE=true .venv/Scripts/python -m uvicorn app.main:app --port 8000
```
```bash
cd frontend && npm install && npm run dev      # http://localhost:5173, proxies /api and /ws to :8000
```
Tests: `cd backend && .venv/Scripts/python -m pytest`.

## Deploy on the Pi at the house

1. Install Docker on the Pi / mini PC. Clone this repo.
2. `cp .env.example .env` and fill in the credentials (see below). Set `DASHBOARD_TOKEN` to a random secret.
3. Build the PWA once on any machine: `cd frontend && npm install && npm run build` (or build on the Pi).
4. Edit `deploy/go2rtc.yaml` with the NVR RTSP URLs (the NVR probe prints them).
5. `cd deploy && docker compose up -d --build`
6. Install Tailscale on your phone and laptop, log in to the same tailnet, open
   `https://siofok.<your-tailnet>.ts.net`, enter the dashboard token, "Add to Home Screen".

The backend and go2rtc run with `network_mode: host` because Broadlink discovery is UDP broadcast and
the devices are on the LAN. Caddy runs inside the Tailscale container's network namespace so only the
tailnet can reach it. Nothing is exposed to the internet and nothing needs port forwarding on the 5G
router (which is behind carrier-grade NAT anyway).

## Getting each credential

Every adapter has a probe you can run on the Pi (or any machine on the LAN) before touching `.env`:

| System | Where to get it | Probe |
|---|---|---|
| SolarEdge | monitoring.solaredge.com → Admin → Site Access → API Access → New key. Site ID is in the URL. If the site is installer-owned, ask the installer to enable "site owner API access". | `python -m app.adapters.solaredge --site ID --key KEY` |
| Panasonic | In the Comfort Cloud app create a **second** account (different e-mail), enable 2FA by **SMS** on it, then from your main account share each unit to it (Device → Share). Use the second account here. | `python -m app.adapters.panasonic_cc --user E --password P` |
| ZTE G5B | Router admin password (the one for 192.168.0.1). | `python -m app.adapters.zte_g5b --host 192.168.0.1 --password P` |
| Rain Bird | Controller IP from your router's client list; password = the one you set in the Rain Bird app when you added the controller. | `python -m app.adapters.rainbird --host IP --password P` |
| AC Freedom | Run discovery on the LAN; it prints IP + MAC of every Broadlink device. Use the one with type `0x4E2A`. If auth fails the module is cloud-locked: in AC Freedom re-add it and it will accept LAN control. | `python -m app.adapters.broadlink_ac --discover` |
| Hikvision NVR | NVR IP; create a user on the NVR (Configuration → System → User Management) with live view, playback and remote parameter read. Enable ISAPI (it is on by default). | `python -m app.adapters.hikvision_nvr --host IP --user U --password P` |
| Hik-Connect | Your Hik-Connect e-mail + password (only used for the doorbell). | `python -m app.adapters.hikconnect_doorbell --user E --password P` |

Run the probes from `backend/` with the venv active. Each prints the state dict the dashboard will show.

## What still has to be confirmed on-site

- **AC Freedom module** answers local UDP (some newer AUX firmware is cloud-only). If not, the fallback is the
  AUX cloud API; open an issue in this repo with the discovery output.
- **Rain Bird** has the LNK (WiFi) module, not the newer LNK2 cloud-only one. `pyrainbird` handles both but cloud support is limited.
- **ZTE** login on the G5B firmware: two password hashing schemes are tried automatically; the probe tells you which worked.
- **Hik-Connect** doorbell call status and unlock depend on the exact device type; `locks` in the probe output shows which channel has a lock.
- **Panasonic** account sharing was done, otherwise the phone app gets logged out when the dashboard logs in.

## Security notes

- Credentials live only in `.env` on the Pi (git-ignored) and in the container environment.
- The dashboard is reachable only over Tailscale; the shared `DASHBOARD_TOKEN` is a second layer.
- Disruptive actions (router reboot, door unlock) ask for confirmation in the UI. Every command is logged
  to the SQLite event store and visible in the Timeline panel.
- SolarEdge: rotate the API key every 6 months as SolarEdge recommends; the 300/day quota is respected by the 15 min poll.
