"""Nine days of the integration against a fake National Grid, checked against the true usage.

Run with plain Python 3.13 (no Home Assistant needed):  python3 tests/test_integration.py

The integration polls every 15 minutes from Oct 28 to Nov 6, 2026, starting as a fresh install with history back
to Sept 1. Along the way it meets:
  * the end of daylight saving time (Nov 1: the 1:00 AM hour happens twice)
  * a 3-hour meter outage that never shows up in the real-time feed (settled data fills it in later)
  * a 6-hour outage of the settled-data service, and a 1-hour outage of everything
  * Home Assistant switched off for 36 hours, then started again from scratch
  * a new bill arriving mid-month (its period must be repriced)
  * solar export every midday

At the end every statistic must be continuous, its running totals must add up, settled hours must match the
truth exactly, and every cost must equal energy x that hour's rate. Exits with 1 if anything is wrong.
"""

import asyncio
from datetime import UTC, datetime, time, timedelta
import math
import sys
import types

import stubs

stubs.install()
from nationalgrid import coordinator as ng, sensor  # noqa: E402 - must come after the stand-ins are installed
from nationalgrid.const import STATISTICS  # noqa: E402

TZ, HOUR, QUARTER = stubs.TZ, timedelta(hours=1), timedelta(minutes=15)
now, PROBLEMS, STORE = stubs.now, stubs.PROBLEMS, stubs.STORE


def local(*args):
    """Local wall-clock time -> UTC instant."""
    return datetime(*args, tzinfo=TZ).astimezone(UTC)


# ---------- the scenario ----------
INSTALL, START, END = local(2026, 9, 1), local(2026, 10, 28), local(2026, 11, 6)
METER_OUTAGE = (local(2026, 10, 31, 9), local(2026, 10, 31, 12))  # missing from the real-time feed only
SETTLED_DOWN = (local(2026, 10, 30, 6), local(2026, 10, 30, 12))
ALL_DOWN = (local(2026, 11, 5, 14), local(2026, 11, 5, 15))
HA_OFF = (local(2026, 11, 2, 8), local(2026, 11, 3, 20))
NEW_BILL_AT = local(2026, 11, 4, 9)
SETTLED_LAG, REALTIME_LAG, REALTIME_ERROR = timedelta(hours=36), timedelta(minutes=45), 0.97
BILLS = [  # newest first, like National Grid
    {"readFromDate": "2026-09-30T00:00:00", "readDate": "2026-10-30T00:00:00", "totalKwh": 500, "totalCharges": 150.0},
    {"readFromDate": "2026-08-31T00:00:00", "readDate": "2026-09-30T00:00:00", "totalKwh": 500, "totalCharges": 125.0},
    {"readFromDate": "2026-07-31T00:00:00", "readDate": "2026-08-31T00:00:00", "totalKwh": 500, "totalCharges": 100.0},
]
NEW_BILL = {
    "readFromDate": "2026-10-30T00:00:00",
    "readDate": "2026-11-03T00:00:00",
    "totalKwh": 100,
    "totalCharges": 35.0,
}


def truth(start):
    """True net kWh for the 15 minutes starting at `start`: solar export from 10:00 to 15:00, import otherwise."""
    k = int(start.timestamp() // 900)
    if 10 <= start.astimezone(TZ).hour < 15:
        return round(-0.4 - 0.05 * (k % 2), 4)
    return round(0.2 + 0.1 * (k % 3), 4)


def library_read(start, value):
    """Shape a read exactly like py_nationalgrid's get_interval_reads (including its daylight saving quirk).

    The library takes the end time (with its UTC offset) from the API, then builds the start from the API's
    clock time on the same date and offset, so the read spanning the clock change comes out mis-dated.
    """
    end = datetime.fromisoformat((start + QUARTER).astimezone(TZ).isoformat())  # fixed offset, as parsed
    begin = datetime.combine(end.date(), time.fromisoformat(start.astimezone(TZ).strftime("%H:%M")), end.tzinfo)
    if begin > end:
        begin -= timedelta(days=1)
    return {"startTime": begin.isoformat(), "endTime": end.isoformat(), "value": value}


class FakeNationalGrid:
    """Answers like py_nationalgrid's client, from `truth`, with National Grid's delays and the outages above."""

    async def get_linked_accounts(self):
        return [{"billingAccountId": "A1"}]

    async def get_billing_account(self, account_id):
        return {
            "premiseNumber": 999,
            "customerNumber": 55,
            "meter": {
                "nodes": [
                    {
                        "hasAmiSmartMeter": True,
                        "fuelType": "Electric",
                        "servicePointNumber": 123,
                        "meterNumber": "M1",
                        "meterPointNumber": 1,
                    },
                    {"hasAmiSmartMeter": True, "fuelType": "Gas", "servicePointNumber": 456},  # must be skipped
                ]
            },
        }

    async def get_electric_bill_history(self, account, customer):
        return ([NEW_BILL] if now() >= NEW_BILL_AT else []) + BILLS

    async def get_ami_energy_usages(self, meter, premise, sp, meter_point, date_from, date_to, fuel_type=None):
        if SETTLED_DOWN[0] <= now() < SETTLED_DOWN[1] or ALL_DOWN[0] <= now() < ALL_DOWN[1]:
            raise stubs.NationalGridError("504 Gateway Timeout")
        t = max(INSTALL, local(date_from.year, date_from.month, date_from.day))
        stop = min(now() - SETTLED_LAG, local(date_to.year, date_to.month, date_to.day) + timedelta(days=1))
        records = []
        while t + QUARTER <= stop:  # exact 15-minute records in UTC, as National Grid sends them
            records.append({"date": t.strftime("%Y-%m-%dT%H:%M:%S.000Z"), "fuelType": "ELECTRIC", "quantity": truth(t)})
            t += QUARTER
        return records

    async def get_interval_reads(self, premise, sp, start_local_naive):
        if ALL_DOWN[0] <= now() < ALL_DOWN[1]:
            raise stubs.NationalGridError("connection reset")
        t = max(start_local_naive.replace(tzinfo=TZ).astimezone(UTC), now() - timedelta(days=7))
        t = datetime.fromtimestamp(t.timestamp() // 900 * 900, UTC)
        reads = []
        while t + QUARTER <= now() - REALTIME_LAG:  # provisional values, a little low
            if not METER_OUTAGE[0] <= t < METER_OUTAGE[1]:
                reads.append(library_read(t, round(truth(t) * REALTIME_ERROR, 5)))
            t += QUARTER
        return reads


# ---------- run it ----------
hass = types.SimpleNamespace(config=types.SimpleNamespace(currency="USD"))
hass.config_entries = types.SimpleNamespace(async_update_entry=lambda entry, data: setattr(entry, "data", data))
entry = types.SimpleNamespace(data={"username": "user@example.com", "password": "secret"})


def start_home_assistant():
    """A fresh coordinator, as after a restart: in-memory state is gone, statistics and entry data remain."""
    coordinator = ng.NationalGridCoordinator(hass, entry)
    coordinator.api = FakeNationalGrid()
    return coordinator


async def simulate():
    """Poll every 15 minutes through the scenario, checking the sensors after each update."""
    coordinator, failures, today_seen = start_home_assistant(), [], {}
    stubs.CLOCK["now"] = START
    while now() < END:
        if HA_OFF[0] <= now() < HA_OFF[1]:
            stubs.CLOCK["now"] += QUARTER
            if now() >= HA_OFF[1]:
                coordinator = start_home_assistant()
            continue
        try:
            coordinator.data = await coordinator._async_update_data()
        except stubs.UpdateFailed as err:
            failures.append(f"{now().astimezone(TZ):%m-%d %H:%M} {err}")
        else:
            power = sensor.GridPowerSensor(coordinator, "123").native_value
            today = sensor.EnergyTodaySensor(coordinator, "123").native_value
            day = now().astimezone(TZ).date()
            if today_seen.get(day, -1) > today + 1e-9:  # a drop would be counted twice by Home Assistant
                PROBLEMS.append(f"'Energy imported today' went down at {now()}")
            today_seen[day] = today
            if power is None:
                PROBLEMS.append(f"'Grid power' had no value at {now()}")
        stubs.CLOCK["now"] += QUARTER
    return coordinator, failures


def check(coordinator):
    """Compare every stored hour with the truth; return a one-line summary."""
    ids = {key: f"nationalgrid:123_{key}" for key in STATISTICS}
    series = {key: STORE[statistic_id] for key, statistic_id in ids.items()}
    energy, export, cost = series["energy"], series["return"], series["cost"]
    if any(statistic_id.startswith("nationalgrid:456") for statistic_id in STORE):
        PROBLEMS.append("the gas meter got statistics")
    hours = sorted(energy)
    # Hours whose settled data existed at the last daily correction (Nov 5, midnight) must be exact by now.
    settled_until = (local(2026, 11, 5) - SETTLED_LAG).timestamp()
    exact = 0
    for i, ts in enumerate(hours):
        hour = datetime.fromtimestamp(ts, UTC)
        if i and ts - hours[i - 1] != 3600:
            PROBLEMS.append(f"gap or duplicate before {hour}")
        for key, rows in series.items():
            if ts not in rows:
                PROBLEMS.append(f"{key} has no row for {hour}")
                continue
            previous = rows[hours[i - 1]]["sum"] if i else 0.0
            if not math.isclose(rows[ts]["sum"], previous + rows[ts]["state"], abs_tol=1e-6):
                PROBLEMS.append(f"{key} running total jumps at {hour}")
        rate = coordinator.rate("123", hour)
        if not math.isclose(cost[ts]["state"], energy[ts]["state"] * rate, abs_tol=1e-6):
            PROBLEMS.append(f"cost at {hour} isn't energy x {rate}")
        if ts + 3600 <= settled_until:
            net = sum(truth(hour + k * QUARTER) for k in range(4))
            imported, exported = (net, 0.0) if net >= 0 else (0.0, -net)
            if math.isclose(energy[ts]["state"], imported, abs_tol=1e-6) and math.isclose(
                export[ts]["state"], exported, abs_tol=1e-6
            ):
                exact += 1
            else:
                PROBLEMS.append(f"settled hour {hour.astimezone(TZ)} isn't exact")
    night = [
        f"{datetime.fromtimestamp(ts, UTC).astimezone(TZ):%H:%M %Z}"
        for ts in hours
        if local(2026, 11, 1, 0) <= datetime.fromtimestamp(ts, UTC) < local(2026, 11, 1, 3)
    ]
    if len(night) != 4:
        PROBLEMS.append(f"the night the clocks changed has {len(night)} hours, not 4: {night}")
    if entry.data.get("history") != ng.HISTORY_VERSION:
        PROBLEMS.append("the full history import never finished")
    first = datetime.fromtimestamp(hours[0], UTC).astimezone(TZ)
    return (
        f"{len(hours)} hours from {first:%Y-%m-%d}, {exact} settled hours exact, clock-change night: {', '.join(night)}"
    )


if __name__ == "__main__":
    coordinator, failures = asyncio.run(simulate())
    print(check(coordinator))
    print(f"update failures (expected during the outage): {len(failures)}")
    for problem in PROBLEMS[:25]:
        print("PROBLEM:", problem)
    print(f"{len(PROBLEMS)} problems" if PROBLEMS else "all checks passed")
    sys.exit(1 if PROBLEMS else 0)
