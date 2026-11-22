"""What National Grid sends that isn't usable: numbers that aren't numbers, and errors carrying account details.

Run with plain Python (no Home Assistant needed):  python3 tests/test_bad_data.py

National Grid's replies are taken as they come, so a bill, a settled reading or a real-time read could hold NaN,
infinity, text or nothing where a number belongs. None of that may reach the statistics (one bad row spoils every
running total after it) or the sensors. And py-nationalgrid's error messages can include request addresses and
parts of the reply, so the log must name an error by its type and HTTP status only.

Exits with 1 if anything is wrong.
"""

import asyncio
from datetime import UTC, datetime, timedelta
import logging
import math
import sys
import types

import stubs

stubs.install()
from nationalgrid import coordinator as ng, sensor  # noqa: E402 - must come after the stand-ins are installed
from nationalgrid.const import STATISTICS  # noqa: E402

TZ, HOUR, QUARTER = stubs.TZ, timedelta(hours=1), timedelta(minutes=15)
now, PROBLEMS, STORE = stubs.now, stubs.PROBLEMS, stubs.STORE
SECRET = "ACCOUNT-8675309"  # stands for anything private in an error's message: it must never be logged
NAN, INF = float("nan"), float("inf")


def check(ok, message):
    """Print one result and remember failures."""
    print(("PASS " if ok else "FAIL ") + message)
    if not ok:
        PROBLEMS.append(message)


def local(*args):
    """Local wall-clock time -> UTC instant."""
    return datetime(*args, tzinfo=TZ).astimezone(UTC)


class LeakyError(stubs.NationalGridError):
    """Like py-nationalgrid's RestAPIError: an HTTP status, and a message with the request and reply in it."""

    status = 503

    def __str__(self):
        return f"REST request failed\nRequest: GET https://example.invalid/accounts/{SECRET}\nResponse: {SECRET}"


def bill(start, end, kwh, charges):
    return {
        "readFromDate": f"{start}T00:00:00",
        "readDate": f"{end}T00:00:00",
        "totalKwh": kwh,
        "totalCharges": charges,
    }


BILLS = [  # newest first, like National Grid; only the last two are usable
    bill("2026-10-01", "2026-10-30", "NaN", 50.0),
    bill("2026-09-01", "2026-10-01", 400, INF),
    bill("2026-08-01", "2026-09-01", 500, -20.0),
    bill("2026-07-01", "2026-08-01", None, 10.0),
    bill("2026-06-01", "2026-07-01", 0, 0.0),  # no usage: normal, and skipped too
    bill("2026-05-01", "2026-06-01", "500", "150.0"),  # numbers as text are fine
    bill("2026-04-01", "2026-05-01", 500, 100.0),
]
BLENDED = round(250.0 / 1000, 4)
BAD_VALUES = [NAN, INF, -INF, None, "abc", "nan"]


def value_for(start):
    """The value National Grid sends for a 15-minute slot: import at night, export (negative) at midday, and a
    bad value in one slot an hour from 3 AM to 6 AM local."""
    local_start = start.astimezone(TZ)
    if 3 <= local_start.hour < 6 and local_start.minute == 30:
        return BAD_VALUES[int(start.timestamp() // 3600) % len(BAD_VALUES)]
    return -0.3 if 10 <= local_start.hour < 15 else 0.25


class FakeNationalGrid:
    """National Grid with bad numbers mixed in, and (when `failing`) errors that carry an account number."""

    failing = False

    async def get_linked_accounts(self):
        return [{"billingAccountId": "A1"}]

    async def get_billing_account(self, account_id):
        meter = {
            "hasAmiSmartMeter": True,
            "fuelType": "Electric",
            "servicePointNumber": 123,
            "meterNumber": "M1",
            "meterPointNumber": 1,
        }
        return {"premiseNumber": 999, "customerNumber": 55, "meter": {"nodes": [meter]}}

    async def get_electric_bill_history(self, account, customer):
        if self.failing:
            raise LeakyError()
        return [dict(b) for b in BILLS]

    async def get_ami_energy_usages(self, meter, premise, sp, meter_point, date_from, date_to, fuel_type=None):
        if self.failing:
            raise LeakyError()
        t, stop, records = local(2026, 11, 1), now() - timedelta(hours=36), []
        while t + QUARTER <= stop:
            records.append({"date": t.strftime("%Y-%m-%dT%H:%M:%S.000Z"), "quantity": value_for(t)})
            t += QUARTER
        return records

    async def get_interval_reads(self, premise, sp, start_local_naive):
        if self.failing:
            raise LeakyError()
        t = max(start_local_naive.replace(tzinfo=TZ).astimezone(UTC), now() - timedelta(days=7))
        reads = []
        while t + QUARTER <= now() - timedelta(minutes=45):
            reads.append(
                {
                    "startTime": t.astimezone(TZ).isoformat(),
                    "endTime": (t + QUARTER).astimezone(TZ).isoformat(),
                    "value": value_for(t),
                }
            )
            t += QUARTER
        return reads


class Captured(logging.Handler):
    """Keeps every log line the integration writes."""

    lines = []

    def emit(self, record):
        Captured.lines.append(record.getMessage())


def new_coordinator():
    hass = types.SimpleNamespace(config=types.SimpleNamespace(currency="USD"))
    hass.config_entries = types.SimpleNamespace(async_update_entry=lambda entry, data: setattr(entry, "data", data))
    entry = types.SimpleNamespace(data={"username": "user@example.com", "password": "secret"})
    coordinator = ng.NationalGridCoordinator(hass, entry)
    coordinator.api = FakeNationalGrid()
    return coordinator


async def test_numbers():
    """Bad numbers are skipped everywhere; good ones (negative export included) are kept."""
    check(
        [ng._finite(v) for v in (1, "2.5", -3.0, NAN, INF, -INF, None, "abc", "nan", [])]
        == [1.0, 2.5, -3.0, None, None, None, None, None, None, None],
        "_finite: numbers and numeric text kept (negative too), NaN/infinity/None/text refused",
    )

    stubs.CLOCK["now"] = local(2026, 11, 5, 12)
    coordinator = new_coordinator()
    await coordinator._async_setup()
    await coordinator._update_rates()
    periods, blended = coordinator.rates.get("A1", ([], None))
    check(blended == BLENDED, f"bills: blended rate from the usable bills only ({blended}, expected {BLENDED})")
    check(
        [round(rate, 4) for _, _, rate in periods] == [0.3, 0.2],
        f"bills: only the usable bills get a period rate ({[rate for _, _, rate in periods]})",
    )
    check(
        coordinator.rate("123", local(2026, 10, 15)) == BLENDED,
        "an hour in a bill with unusable totals gets the blended rate",
    )

    since = local(2026, 11, 1)
    settled, failed, _ = await coordinator._fetch_settled("123", coordinator.meters["123"], since, now(), False)
    bad_hours = {ng._hour(t) for t in (local(2026, 11, d, h, 30) for d in range(1, 4) for h in (3, 4, 5))}
    check(not failed and settled, "settled: the readings are used")
    check(not bad_hours & set(settled), "settled: an hour with any reading that isn't a number is left out whole")
    check(
        all(math.isfinite(i) and math.isfinite(e) and i >= 0 and e >= 0 for i, e in settled.values()),
        "settled: every hour kept is finite, split into import and export",
    )
    noon = ng._hour(local(2026, 11, 2, 12))
    check(
        math.isclose(settled.get(noon, (0, 0))[1], 1.2), f"settled: negative readings are export ({settled.get(noon)})"
    )

    reads, realtime, _ = await coordinator._fetch_realtime("123", coordinator.meters["123"], since, now())
    check(
        reads and all(isinstance(r["value"], float) and math.isfinite(r["value"]) for r in reads),
        f"real-time: only reads with a finite value are kept ({len(reads)} reads)",
    )
    check(any(r["value"] < 0 for r in reads), "real-time: negative reads (export) are kept")
    bad_hour = ng._hour(local(2026, 11, 4, 3))
    check(
        bad_hour in realtime and not realtime[bad_hour].complete,
        "real-time: an hour with a dropped read counts as incomplete",
    )


async def test_polling():
    """A few days of polling with bad numbers mixed in: every stored row and sensor value is a finite number."""
    STORE.clear()
    problems_before = len(PROBLEMS)
    stubs.CLOCK["now"] = local(2026, 11, 3, 0, 15)
    coordinator = new_coordinator()
    await coordinator._async_setup()
    while now() < local(2026, 11, 6):
        coordinator.data = await coordinator._async_update_data()
        values = [
            sensor.GridPowerSensor(coordinator, "123").native_value,
            sensor.EnergyTodaySensor(coordinator, "123").native_value,
        ]
        if not all(v is None or math.isfinite(v) for v in values):
            PROBLEMS.append(f"a sensor isn't a finite number at {now()}: {values}")
        stubs.CLOCK["now"] += QUARTER
    ids = [f"nationalgrid:123_{key}" for key in STATISTICS]
    rows = [row for statistic_id in ids for row in STORE[statistic_id].values()]
    check(
        rows and len(PROBLEMS) == problems_before,
        f"three days of polls: {len(rows)} rows stored, all finite and none negative",
    )
    for statistic_id in ids:
        series = STORE[statistic_id]
        total = 0.0
        for ts in sorted(series):
            total += series[ts]["state"]
            if not math.isclose(series[ts]["sum"], total, abs_tol=1e-6):
                PROBLEMS.append(f"{statistic_id} running total jumps at {ts}")
                break
    check(len(PROBLEMS) == problems_before, "…and every running total adds up")


async def test_errors():
    """Errors are logged by type and status, never by their message."""
    check(ng._describe(LeakyError()) == "LeakyError (HTTP 503)", "_describe: type and HTTP status")
    check(ng._describe(TimeoutError("x")) == "TimeoutError", "_describe: type alone when there's no status")

    stubs.CLOCK["now"] = local(2026, 11, 5, 12)
    coordinator = new_coordinator()
    await coordinator._async_setup()
    coordinator.api.failing = True
    Captured.lines.clear()
    await coordinator._update_rates()
    since = local(2026, 11, 1)
    _, failed, _ = await coordinator._fetch_settled("123", coordinator.meters["123"], since, now(), False)
    try:
        await coordinator._async_update_data()
        update_error = ""
    except stubs.UpdateFailed as err:
        update_error = str(err)
    logged = "\n".join(Captured.lines)
    check(failed and "LeakyError (HTTP 503)" in logged, f"bill and settled errors are logged ({logged!r})")
    check(SECRET not in logged, "…without the error's message")
    check(
        "LeakyError (HTTP 503)" in update_error and SECRET not in update_error,
        f"a failed update reports the type and status only ({update_error!r})",
    )


if __name__ == "__main__":
    logger = logging.getLogger("nationalgrid")
    logger.addHandler(Captured())
    logger.setLevel(logging.DEBUG)
    asyncio.run(test_numbers())
    asyncio.run(test_polling())
    asyncio.run(test_errors())
    for problem in PROBLEMS[:25]:
        print("PROBLEM:", problem)
    print(f"{len(PROBLEMS)} problems" if PROBLEMS else "all checks passed")
    sys.exit(1 if PROBLEMS else 0)
