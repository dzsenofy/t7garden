"""Unit tests: adapter contract, arg validation, parsers with recorded fixtures, demo adapters."""
from __future__ import annotations

import pytest

from app.adapters import demo
from app.adapters.base import Adapter, AdapterError, Command, validate_args
from app.adapters.hikvision_nvr import parse_channels, parse_device_info, parse_hdd
from app.adapters.solaredge import parse_details, parse_overview
from app.adapters.zte_g5b import parse_status, sha256_upper


# ---------------- base contract ----------------
class Flaky(Adapter):
    system = "flaky"
    calls = 0

    async def _poll(self):
        self.calls += 1
        if self.calls == 2:
            raise ConnectionError("device gone")
        return {"n": self.calls}


async def test_poll_keeps_last_data_on_error():
    a = Flaky()
    s1 = await a.poll()
    assert s1.online and s1.data == {"n": 1}
    s2 = await a.poll()
    assert not s2.online and s2.data == {"n": 1} and "device gone" in s2.error
    s3 = await a.poll()
    assert s3.online and s3.data == {"n": 3}


async def test_unknown_command_rejected():
    with pytest.raises(AdapterError):
        await Flaky().execute("nope", {})


def test_validate_args():
    cmd = Command("x", "x", {"zone": {"type": "int", "min": 1, "max": 8}, "minutes": {"type": "int", "default": 5},
                             "mode": {"type": "enum", "choices": ["a", "b"], "default": "a"}, "on": {"type": "bool", "default": False}})
    assert validate_args(cmd, {"zone": "3", "on": "true"}) == {"zone": 3, "minutes": 5, "mode": "a", "on": True}
    with pytest.raises(AdapterError):
        validate_args(cmd, {"zone": 9})
    with pytest.raises(AdapterError):
        validate_args(cmd, {"zone": 1, "mode": "z"})
    with pytest.raises(AdapterError):
        validate_args(cmd, {})


# ---------------- demo adapters (also exercises describe()) ----------------
async def test_demo_adapters_round_trip():
    for a in demo.demo_adapters():
        st = await a.poll()
        assert st.online, a.system
        d = a.describe()
        assert d["system"] == a.system and isinstance(d["commands"], list)


async def test_demo_commands_change_state():
    rb = demo.DemoRainBird()
    await rb.execute("run_zone", {"zone": 3, "minutes": 1})
    assert rb.state.data["active_zone"] == 3
    await rb.execute("stop", {})
    assert rb.state.data["active_zone"] is None

    ac = demo.DemoBroadlinkAc()
    await ac.execute("set_temperature", {"target_c": 25.5})
    assert ac.state.data["target_c"] == 25.5

    pc = demo.DemoPanasonic()
    await pc.execute("set_mode", {"unit": "bedroom", "mode": "cool"})
    assert pc.state.data["units"]["bedroom"]["mode"] == "cool"


# ---------------- SolarEdge parser ----------------
def test_solaredge_parsers():
    overview = {"overview": {"lastUpdateTime": "2026-09-11 12:00:00", "lifeTimeData": {"energy": 38211000.0},
                             "lastYearData": {"energy": 6100000.0}, "lastMonthData": {"energy": 412300.0},
                             "lastDayData": {"energy": 18420.0}, "currentPower": {"power": 5123.4}, "measuredBy": "INVERTER"}}
    d = parse_overview(overview)
    assert d["power_w"] == 5123.4 and d["energy_today_wh"] == 18420.0 and d["energy_lifetime_wh"] == 38211000.0
    details = {"details": {"id": 1, "name": "Siofok", "peakPower": 8.2, "status": "Active", "installationDate": "2021-05-01"}}
    assert parse_details(details)["inverter_status"] == "OK"


# ---------------- ZTE parser ----------------
def test_zte_parse_5g():
    raw = {"network_type": "ENDC", "network_provider": "Telekom HU", "nr5g_action_band": "n78", "lte_band": "B3",
           "nr5g_rsrp": "-88", "lte_rsrp": "-95", "Z5g_SINR": "18", "lte_snr": "12", "signalbar": "4",
           "wan_ipaddr": "10.1.2.3", "realtime_rx_bytes": "1000000", "realtime_tx_bytes": "500000",
           "monthly_rx_bytes": "80000000000", "monthly_tx_bytes": "4300000000", "realtime_time": "7200",
           "station_list": [{"mac": "a"}, {"mac": "b"}], "ppp_status": "ppp_connected", "sim_status": "OK",
           "wa_inner_version": "BD_HUNG5BV1.0.0B05"}
    d = parse_status(raw)
    assert d["band"] == "n78" and d["rsrp_dbm"] == -88.0 and d["sinr_db"] == 18.0
    assert d["clients"] == 2 and d["connected"] and d["uptime_h"] == 2.0 and d["data_month_gb"] == 84.3


def test_zte_parse_lte_fallback():
    d = parse_status({"network_type": "LTE", "lte_band": "B20", "lte_rsrp": "-101", "lte_snr": "5", "signalbar": "2"})
    assert d["band"] == "B20" and d["rsrp_dbm"] == -101.0 and d["clients"] == 0


def test_zte_hash():
    assert sha256_upper("abc") == "BA7816BF8F01CFEA414140DE5DAE2223B00361A396177A9CB410FF61F20015AD"


# ---------------- Hikvision ISAPI parsers ----------------
CHANNELS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<InputProxyChannelStatusList version="2.0" xmlns="http://www.hikvision.com/ver20/XMLSchema">
<InputProxyChannelStatus><id>1</id><sourceInputPortDescriptor><proxyProtocol>HIKVISION</proxyProtocol><ipAddress>192.168.1.64</ipAddress><name>Gate</name></sourceInputPortDescriptor><online>true</online></InputProxyChannelStatus>
<InputProxyChannelStatus><id>2</id><sourceInputPortDescriptor><name>Garden</name></sourceInputPortDescriptor><online>false</online></InputProxyChannelStatus>
</InputProxyChannelStatusList>"""

HDD_XML = """<?xml version="1.0" encoding="UTF-8"?>
<hddList version="2.0" xmlns="http://www.hikvision.com/ver20/XMLSchema">
<hdd><id>1</id><hddName>hde</hddName><hddType>local</hddType><status>ok</status><capacity>3815447</capacity><freeSpace>1411072</freeSpace></hdd>
</hddList>"""

INFO_XML = """<?xml version="1.0" encoding="UTF-8"?>
<DeviceInfo version="2.0" xmlns="http://www.hikvision.com/ver20/XMLSchema">
<deviceName>NVR</deviceName><model>DS-7608NI-K2</model><firmwareVersion>V4.61.010</firmwareVersion></DeviceInfo>"""


def test_hik_parsers():
    ch = parse_channels(CHANNELS_XML)
    assert ch == [{"id": 1, "name": "Gate", "online": True}, {"id": 2, "name": "Garden", "online": False}]
    hdd = parse_hdd(HDD_XML)
    assert hdd["hdd_status"] == "ok" and hdd["hdd_free_pct"] == 37
    assert parse_device_info(INFO_XML)["model"] == "DS-7608NI-K2"
