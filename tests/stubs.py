"""Stand-ins for Home Assistant, the recorder and py-nationalgrid, so the integration runs with plain Python.

Importing this module registers fake modules under the real names (homeassistant.*, py_nationalgrid, aiohttp).
The fake recorder keeps statistics in memory and records anything Home Assistant would reject (or that would
corrupt the Energy dashboard) in PROBLEMS. The clock is CLOCK["now"], a UTC datetime the test moves forward.
"""

from collections import defaultdict
from datetime import UTC, datetime, time, timedelta
from pathlib import Path
import sys
import types
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/New_York")  # Home Assistant's configured time zone in the tests
CLOCK = {"now": None}
STORE = defaultdict(dict)  # statistic_id -> {start timestamp: {"state", "sum"}}
PROBLEMS = []


def now():
    """The simulated current time (UTC)."""
    return CLOCK["now"]


class NationalGridError(Exception):
    """Stands in for py_nationalgrid's NationalGridError and CannotConnectError."""


class InvalidAuthError(Exception):
    """Stands in for py_nationalgrid's InvalidAuthError and Home Assistant's ConfigEntryAuthFailed."""


class UpdateFailed(Exception):
    """Stands in for Home Assistant's UpdateFailed."""


def _module(name, **attributes):
    module = types.ModuleType(name)
    module.__dict__.update(attributes)
    sys.modules[name] = module
    return module


# ---------- the recorder ----------
def async_add_external_statistics(hass, metadata, statistics):
    """Store rows like the recorder does (same start replaces), checking what Home Assistant checks."""
    for row in statistics:
        start = row["start"]
        if start.tzinfo is None or start.minute or start.second or start.microsecond:
            PROBLEMS.append(f"invalid timestamp {start}")  # Home Assistant raises on these
        if start + timedelta(hours=1) > now():
            PROBLEMS.append(f"unfinished or future hour {start} written at {now()}")
        STORE[metadata["statistic_id"]][start.timestamp()] = {"state": row["state"], "sum": row["sum"]}


def get_last_statistics(hass, number, statistic_id, convert_units, types_):
    """Return the newest row of a statistic, as the recorder does."""
    rows = STORE.get(statistic_id)
    if not rows:
        return {}
    newest = max(rows)
    return {statistic_id: [{"start": newest, **rows[newest]}]}


def statistics_during_period(hass, start, end, statistic_ids, period, units, types_):
    """Return rows from `start` onwards, oldest first (only what the integration asks for: hourly, no end)."""
    return {
        statistic_id: [
            {"start": ts, **STORE[statistic_id][ts]} for ts in sorted(STORE[statistic_id]) if ts >= start.timestamp()
        ]
        for statistic_id in statistic_ids
        if STORE.get(statistic_id)
    }


class _Recorder:
    async def async_add_executor_job(self, func, *args):
        return func(*args)


# ---------- Home Assistant ----------
class DataUpdateCoordinator:
    """Only what the integration uses: hass and config_entry. Tests call _async_update_data() themselves."""

    def __init__(self, hass, logger, config_entry=None, **kwargs):
        self.hass, self.config_entry, self.data = hass, config_entry, None


class CoordinatorEntity:
    """Only what the sensors use."""

    def __init__(self, coordinator):
        self.coordinator = coordinator


def _start_of_local_day():
    return datetime.combine(now().astimezone(TZ).date(), time(), TZ)


def install():
    """Register every stand-in module and make the integration importable as `nationalgrid`."""
    _module("aiohttp", ClientError=OSError)
    _module(
        "py_nationalgrid",
        CannotConnectError=NationalGridError,
        InvalidAuthError=InvalidAuthError,
        NationalGridError=NationalGridError,
        NationalGridClient=lambda *args, **kwargs: None,  # tests replace coordinator.api with a fake
        NationalGridConfig=lambda **kwargs: kwargs,
        create_cookie_jar=lambda: None,
    )
    _module("homeassistant")
    _module("homeassistant.components")
    _module("homeassistant.components.recorder", get_instance=lambda hass: _Recorder())
    _module(
        "homeassistant.components.recorder.models",
        StatisticData=dict,
        StatisticMetaData=dict,
        StatisticMeanType=types.SimpleNamespace(NONE=0),
    )
    _module(
        "homeassistant.components.recorder.statistics",
        async_add_external_statistics=async_add_external_statistics,
        get_last_statistics=get_last_statistics,
        statistics_during_period=statistics_during_period,
    )
    _module(
        "homeassistant.components.sensor",
        SensorEntity=object,
        SensorDeviceClass=types.SimpleNamespace(POWER="power", ENERGY="energy", MONETARY="monetary"),
        SensorStateClass=types.SimpleNamespace(MEASUREMENT="measurement", TOTAL_INCREASING="total_increasing"),
    )
    _module("homeassistant.config_entries", ConfigEntry=object)
    _module(
        "homeassistant.const",
        CONF_PASSWORD="password",
        CONF_USERNAME="username",
        Platform=types.SimpleNamespace(SENSOR="sensor"),
        UnitOfEnergy=types.SimpleNamespace(KILO_WATT_HOUR="kWh"),
        UnitOfPower=types.SimpleNamespace(KILO_WATT="kW"),
    )
    _module("homeassistant.core", HomeAssistant=object)
    _module("homeassistant.exceptions", ConfigEntryAuthFailed=InvalidAuthError)
    _module("homeassistant.helpers")
    _module("homeassistant.helpers.aiohttp_client", async_create_clientsession=lambda *args, **kwargs: None)
    _module(
        "homeassistant.helpers.update_coordinator",
        DataUpdateCoordinator=DataUpdateCoordinator,
        UpdateFailed=UpdateFailed,
        CoordinatorEntity=CoordinatorEntity,
    )
    dt = _module(
        "homeassistant.util.dt",
        UTC=UTC,
        get_default_time_zone=lambda: TZ,
        utcnow=now,
        now=lambda: now().astimezone(TZ),
        as_local=lambda value: value.astimezone(TZ),
        utc_from_timestamp=lambda ts: datetime.fromtimestamp(ts, UTC),
        start_of_local_day=_start_of_local_day,
    )
    _module("homeassistant.util", dt=dt, slugify=lambda text: str(text).lower())
    _module("homeassistant.util.unit_conversion", EnergyConverter=types.SimpleNamespace(UNIT_CLASS="energy"))
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "custom_components"))
