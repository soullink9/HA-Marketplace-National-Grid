"""Fetches usage from National Grid and keeps the Energy dashboard statistics up to date.

National Grid offers two kinds of usage data, both through the py-nationalgrid library:

* Real-time reads: 15-minute intervals, available soon after each interval (how soon is up to National Grid),
  but provisional (they can be a little off) and only kept for about a week.
* Settled data: the exact meter readings, published a day or two later and kept for the life of the meter.

Every 15 minutes the coordinator turns these into four hourly long-term statistics per meter (energy imported,
energy exported, cost and export credit), which is the format the Energy dashboard reads. New hours are appended
from real-time reads, and hours are rewritten with settled data once it exists: the whole history on a new
install, the last few days once a day, and a bill period whenever a new bill arrives (so it gets the bill's rate).

Each statistic row carries a running total ("sum"). Whenever hours are rewritten, every row after them is
rewritten too, so the running totals always add up.
"""

from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
import logging

from aiohttp import ClientError
from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.models import StatisticData, StatisticMeanType, StatisticMetaData
from homeassistant.components.recorder.statistics import (
    async_add_external_statistics,
    get_last_statistics,
    statistics_during_period,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, UnitOfEnergy
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util, slugify
from homeassistant.util.unit_conversion import EnergyConverter
from py_nationalgrid import (
    CannotConnectError,
    InvalidAuthError,
    NationalGridClient,
    NationalGridConfig,
    NationalGridError,
    create_cookie_jar,
)

from .const import (
    AUTH_FAILURES_BEFORE_REAUTH,
    DOMAIN,
    EPOCH,
    FILL_GRACE,
    HISTORY_VERSION,
    HOUR,
    QUARTER,
    RATES_EVERY,
    REALTIME_DAYS,
    RETRY_AFTER_EMPTY,
    RETRY_AFTER_ERROR,
    SETTLE,
    STATISTICS,
)

_LOGGER = logging.getLogger(__name__)

# Errors that mean "National Grid couldn't be reached or answered badly": the update is retried next poll.
NET_ERRORS = (CannotConnectError, NationalGridError, ClientError, TimeoutError)


def _local(value):
    """Parse an ISO timestamp (or take a datetime), treating one without an offset as Home Assistant's local time."""
    value = datetime.fromisoformat(value) if isinstance(value, str) else value
    return value.replace(tzinfo=dt_util.get_default_time_zone()) if value.tzinfo is None else value


def _hour(value):
    """Return the start of the hour containing `value`, in UTC.

    Hour math is done in UTC on purpose: in local time, adding an hour at the end of daylight saving time skips
    the repeated 1:00 AM hour.
    """
    return _local(value).astimezone(UTC).replace(minute=0, second=0, microsecond=0)


def _split(net_kwh):
    """Split a net reading (positive = taken from the grid, negative = sent to it) into (imported, exported)."""
    return (net_kwh, 0.0) if net_kwh >= 0 else (0.0, -net_kwh)


class RealtimeHour:
    """The real-time reads that fall in one hour, added up: kWh imported, kWh exported, and how much of the hour
    the reads cover (an hour is only used as-is once its four 15-minute reads are in)."""

    def __init__(self):
        """Start with nothing counted."""
        self.imported = 0.0
        self.exported = 0.0
        self.covered = timedelta()

    def add(self, value, duration):
        """Add one read. National Grid reports export as a negative value."""
        if value >= 0:
            self.imported += value
        else:
            self.exported += -value
        self.covered += duration

    @property
    def complete(self):
        """True once the reads cover the whole hour."""
        return self.covered >= HOUR


class NationalGridCoordinator(DataUpdateCoordinator):
    """One per National Grid login. Polls every 15 minutes; `data` maps each meter to its recent real-time reads."""

    def __init__(self, hass, entry):
        """Set up the National Grid client. Meters are discovered on the first update."""
        super().__init__(hass, _LOGGER, config_entry=entry, name=DOMAIN, update_interval=QUARTER)
        config = NationalGridConfig(username=entry.data[CONF_USERNAME], password=entry.data[CONF_PASSWORD])
        # National Grid's sign-in needs cookies stored unquoted, which create_cookie_jar() sets up.
        # Home Assistant detaches this session itself when the entry is unloaded or Home Assistant stops.
        self.session = async_create_clientsession(hass, cookie_jar=create_cookie_jar())
        self.api = NationalGridClient(config, session=self.session)
        self.meters: dict[str, dict] = {}  # service point -> meter details plus premise, account and customer numbers
        self.rates: dict[str, tuple[list, float]] = {}  # account -> ([(period start, end, $/kWh)], blended $/kWh)
        self._rewrite: dict[str, datetime] = {}  # service point -> rewrite its statistics from this hour onwards
        self._history_done: set[str] = set()  # meters whose full history import has finished
        self._today = None  # local date of the last update, to spot the first update of each day
        # "Long ago", so the first poll fetches bill history and is allowed to ask for settled data.
        self._rates_checked = datetime.min.replace(tzinfo=UTC)
        self._settled_retry = datetime.min.replace(tzinfo=UTC)  # don't ask for settled data again before this
        self._auth_failures = 0  # polls in a row whose sign-in failed

    async def _async_update_data(self):
        """Run one poll: find meters, refresh rates when due, then update every meter's statistics."""
        entry = self.config_entry
        try:
            if not self.meters:
                await self._find_meters()
            if dt_util.utcnow() - self._rates_checked > RATES_EVERY:
                await self._update_rates()
            today = dt_util.now().date()
            if self._today != today:
                # First update of the day: swap the last few days of real-time estimates for settled data.
                self._today = today
                for service_point in self.meters:
                    self._rewrite_from(service_point, dt_util.start_of_local_day() - SETTLE)
            data = {}
            for service_point, meter in self.meters.items():
                data[service_point] = await self._update_meter(service_point, meter)
        except InvalidAuthError as err:
            # The library reports National Grid's server errors as a wrong password too, so a single failure is
            # retried at the next poll. Only repeated failures make Home Assistant ask for the password again.
            self._auth_failures += 1
            if self._auth_failures >= AUTH_FAILURES_BEFORE_REAUTH:
                self._auth_failures = 0
                raise ConfigEntryAuthFailed(err) from err
            raise UpdateFailed(
                f"National Grid sign-in failed ({self._auth_failures} of {AUTH_FAILURES_BEFORE_REAUTH} tries before "
                f"asking for the password again): {err}"
            ) from err
        except NET_ERRORS as err:
            raise UpdateFailed(err) from err  # logged, and tried again at the next poll
        self._auth_failures = 0
        # Remember that the full history is in, so restarts don't import it again.
        if entry.data.get("history") != HISTORY_VERSION and self._history_done >= set(self.meters):
            self.hass.config_entries.async_update_entry(entry, data={**entry.data, "history": HISTORY_VERSION})
        return data

    async def _find_meters(self):
        """Collect every electric smart meter on every account linked to this login.

        Gas meters and meters without AMI (smart meter) data are skipped: they have no real-time reads.
        """
        for link in await self.api.get_linked_accounts():
            account_id = link["billingAccountId"]
            account = await self.api.get_billing_account(account_id)
            for meter in account["meter"]["nodes"]:
                if meter.get("hasAmiSmartMeter") and "gas" not in str(meter.get("fuelType")).lower():
                    self.meters[str(meter["servicePointNumber"])] = {
                        **meter,
                        "premise": str(account["premiseNumber"]),
                        "account": account_id,
                        "customer": str(account.get("customerNumber")),
                    }

    def _rewrite_from(self, service_point, since):
        """Schedule a meter's statistics to be rewritten from `since` onwards at its next update.

        If a rewrite is already scheduled, the earlier of the two start hours wins, so nothing scheduled is skipped.
        """
        since = _hour(since)
        self._rewrite[service_point] = min(self._rewrite.get(service_point, since), since)

    async def _update_rates(self):
        """Work out each account's cost per kWh from its bill history.

        Each bill's rate is its total charges divided by its kWh, so supply, delivery, taxes and fixed fees are
        all included. Hours not covered by a bill yet use the blended rate of the last three bills.
        """
        accounts = {(meter["account"], meter["customer"]) for meter in self.meters.values()}
        for account, customer in accounts:
            try:
                bills = await self.api.get_electric_bill_history(account, customer)
            except Exception as err:  # noqa: BLE001 - billing being down must never stop usage tracking
                _LOGGER.warning("Could not fetch National Grid bill history: %s", err)
                continue
            bills = [bill for bill in bills if (bill.get("totalKwh") or 0) > 0]  # skip bills with no usage (avoids / 0)
            if not bills:
                continue
            # Bills come newest first, so periods[0] is the newest bill period.
            periods = []
            for bill in bills:
                period_rate = bill["totalCharges"] / bill["totalKwh"]
                periods.append((_local(bill["readFromDate"]), _local(bill["readDate"]), period_rate))
            known_periods = self.rates.get(account, ([], 0))[0]
            if not known_periods or periods[0] != known_periods[0]:
                # A new bill (or the first look after a restart): reprice the newest bill period.
                for service_point, meter in self.meters.items():
                    if meter["account"] == account:
                        self._rewrite_from(service_point, periods[0][0])
            recent = bills[:3]
            recent_charges = sum(bill["totalCharges"] for bill in recent)
            recent_kwh = sum(bill["totalKwh"] for bill in recent)
            self.rates[account] = (periods, round(recent_charges / recent_kwh, 4))
        self._rates_checked = dt_util.utcnow()

    def rate(self, service_point, hour=None):
        """Return the $/kWh for an hour: its bill period's rate, or the blended rate (also when `hour` is None).

        Returns None until bill history has been fetched once.
        """
        periods, blended = self.rates.get(self.meters[service_point]["account"], ([], None))
        if hour:
            for start, end, period_rate in periods:
                if start <= hour < end:
                    return period_rate
        return blended

    async def _recorder(self, func, *args):
        """Run a recorder database query in the recorder's own thread, as Home Assistant requires."""
        return await get_instance(self.hass).async_add_executor_job(func, self.hass, *args)

    # --- one meter's update ------------------------------------------------------------------------------------
    # _update_meter runs the steps below in order. Each step is its own method so it can be read on its own.

    async def _update_meter(self, service_point, meter):
        """Bring one meter's four statistics up to date and return its recent real-time reads (for the sensors)."""
        ids = {key: f"{DOMAIN}:{slugify(service_point)}_{key}" for key in STATISTICS}
        now = dt_util.utcnow()

        # 1. Where each statistic ends now.
        last = await self._last_stored(ids)
        next_new = last["energy"][0] + HOUR  # first hour not stored yet
        latest_totals = {key: total for key, (_, total) in last.items()}

        # 2. The first hour to write (earlier than next_new when stored hours are being rewritten).
        full, since = self._first_hour_to_write(service_point, meter, last, next_new, now)

        # 3. When rewriting, the hours already stored and the running totals just before `since`.
        stored, base = {}, latest_totals
        if since < next_new:
            stored, base = await self._stored_hours(ids, last, since)

        # 4. Settled data (exact) for anything older than about a day.
        settled, settled_failed, full = await self._fetch_settled(service_point, meter, since, now, full)
        if settled_failed and not full:
            # Without settled data a rewrite would only repeat what's stored, so just add new hours this time.
            # The scheduled rewrite stays in place and runs once settled data is back.
            since, stored, base = next_new, {}, latest_totals

        # 5. Real-time 15-minute reads.
        reads, realtime, newest = await self._fetch_realtime(service_point, meter, since, now)

        # 6. The rows to write, hour by hour, with running totals.
        rows = self._build_rows(service_point, since, settled, realtime, stored, base, newest)
        if rows is None:
            return reads  # nothing at all to write yet

        # 7. Save, then clear what this update has done.
        self._save(service_point, ids, rows)
        if not settled_failed:
            self._rewrite.pop(service_point, None)
            if full:
                self._history_done.add(service_point)
        return reads

    async def _last_stored(self, ids):
        """Step 1: for each statistic, (start of its last hour, running total), or (EPOCH, 0) when it's empty."""
        last = {}
        for key, statistic_id in ids.items():
            rows = (await self._recorder(get_last_statistics, 1, statistic_id, True, {"sum"})).get(statistic_id)
            if rows:
                last[key] = (dt_util.utc_from_timestamp(rows[0]["start"]), rows[0]["sum"])
            else:
                last[key] = (EPOCH, 0.0)
        return last

    def _first_hour_to_write(self, service_point, meter, last, next_new, now):
        """Step 2: decide whether a full history import is due, and the first hour to write. Returns (full, since).

        Normally that's the next new hour. It's earlier when a full history import is due (everything), when a
        rewrite was scheduled (a new day or a new bill), or when hours were stored before any rate was known
        (they have energy but no cost yet).
        """
        full = self.config_entry.data.get("history") != HISTORY_VERSION and now >= self._settled_retry
        since = EPOCH if full else min(next_new, self._rewrite.get(service_point, now))

        last_priced_hour = last["cost"][0]
        has_unpriced_hours = last_priced_hour < last["energy"][0]
        if self.rates.get(meter["account"]) and has_unpriced_hours:
            first_unpriced = last_priced_hour + HOUR if last_priced_hour > EPOCH else EPOCH
            since = min(since, first_unpriced)
        return full, since

    async def _stored_hours(self, ids, last, since):
        """Step 3: load the stored hours from `since` on, and each statistic's running total just before `since`.

        Returns (stored, base). `stored` maps an hour's timestamp to (imported, exported) kWh; those hours are kept
        unless better data arrives. `base` holds the totals the rewritten rows carry on from. Loading starts 60
        days before `since` so there's an earlier row to take each total from.
        """
        rows = await self._recorder(
            statistics_during_period,
            max(since - timedelta(days=60), EPOCH),
            None,
            set(ids.values()),
            "hour",
            None,
            {"state", "sum"},
        )
        stored = {}
        for row in rows.get(ids["energy"], []):
            stored[row["start"]] = (row["state"], 0.0)
        for row in rows.get(ids["return"], []):
            imported = stored.get(row["start"], (0.0, 0.0))[0]
            stored[row["start"]] = (imported, row["state"])

        base = {}
        for key, statistic_id in ids.items():
            last_start, last_total = last[key]
            # A statistic that ends before `since` carries on from its final total; otherwise it starts from zero
            # unless an earlier row is found just below.
            base[key] = last_total if last_start < since else 0.0
            totals_before = [row["sum"] for row in rows.get(statistic_id, []) if row["start"] < since.timestamp()]
            if totals_before:
                base[key] = totals_before[-1]
        return stored, base

    async def _fetch_settled(self, service_point, meter, since, now, full):
        """Step 4: fetch National Grid's settled (exact) readings from `since`, when that's more than a day ago.

        Returns (settled, failed, full). `settled` maps each hour to (imported, exported) kWh. `full` comes back
        False when a history import got nothing, so the poll carries on with real-time data instead.
        """
        settled, failed = {}, False
        if since >= now - timedelta(days=1) or now < self._settled_retry:
            return settled, failed, full  # nothing old enough to need it, or waiting before asking again
        try:
            usages = await self.api.get_ami_energy_usages(
                str(meter["meterNumber"]),
                meter["premise"],
                service_point,
                meter["meterPointNumber"],
                max(dt_util.as_local(since).date(), date(1970, 1, 1)),
                dt_util.now().date(),
                fuel_type=meter.get("fuelType"),
            )
            # Records can be hourly or 15-minute, and an hour can be partly import and partly export, so add each
            # hour up as net kWh first and split it into imported and exported at the end.
            net_by_hour = defaultdict(float)
            for usage in usages:
                if "T" not in str(usage["date"]):
                    continue  # a whole-day total (date only) can't be placed in an hour, so it's not used
                hour = _hour(usage["date"])
                if hour >= since:
                    net_by_hour[hour] += float(usage["quantity"])
            settled = {hour: _split(net) for hour, net in net_by_hour.items()}
        except NET_ERRORS as err:
            _LOGGER.warning("National Grid settled usage unavailable, using real-time data: %s", err)
            failed = True
            self._settled_retry = now + RETRY_AFTER_ERROR
        if full and not settled:
            # Nothing settled came back: keep going on real-time data, and retry the import later.
            full = False
            self._settled_retry = max(self._settled_retry, now + RETRY_AFTER_EMPTY)
        return settled, failed, full

    async def _fetch_realtime(self, service_point, meter, since, now):
        """Step 5: fetch the real-time 15-minute reads and add them up per hour.

        Returns (reads, realtime, newest): the reads oldest first (the sensors use them), a dict of hour ->
        RealtimeHour, and when the newest read ended. Reads always start from yesterday's midnight at the latest,
        so the "today" sensors are complete, and never earlier than National Grid keeps them.
        """
        yesterday = dt_util.start_of_local_day() - timedelta(days=1)
        start = max(min(since, yesterday), now - REALTIME_DAYS)
        reads = await self.api.get_interval_reads(
            meter["premise"],
            service_point,
            dt_util.as_local(start).replace(tzinfo=None),  # the API wants local time
        )
        realtime = defaultdict(RealtimeHour)
        for read in reads:
            read["start"], read["end"] = _local(read["startTime"]), _local(read["endTime"])
            if not timedelta(0) < read["end"] - read["start"] <= HOUR:
                # The library mis-dates the read that spans a daylight saving change; every read is 15 minutes.
                read["start"] = read["end"] - QUARTER
            realtime[_hour(read["start"])].add(read["value"], read["end"] - read["start"])
        reads.sort(key=lambda read: read["start"])
        newest = reads[-1]["end"] if reads else now
        return reads, realtime, newest

    def _build_rows(self, service_point, since, settled, realtime, stored, base, newest):
        """Step 6: walk the hours in order, choose the best data for each, and build the rows with running totals.

        Returns {statistic key: [StatisticData]}, or None when there's no data at all. For each hour, settled data
        wins; then a complete real-time hour; a recent hour still filling in ends the walk until the next poll;
        and an older hour with missing reads (a meter outage, say) uses what there is, or what was stored before,
        until the daily rewrite replaces it with settled data.
        """
        candidates = [hour.timestamp() for hour in settled]
        candidates += [hour.timestamp() for hour in realtime]
        candidates += list(stored)
        if not candidates:
            return None
        hour = max(since, dt_util.utc_from_timestamp(min(candidates)))
        last_hour = dt_util.utc_from_timestamp(max(candidates))
        rows, totals = defaultdict(list), dict(base)
        while hour <= last_hour:
            ts = hour.timestamp()
            still_filling = hour + HOUR + FILL_GRACE > newest
            if hour in settled:
                imported, exported = settled[hour]
            elif hour in realtime and realtime[hour].complete:
                imported, exported = realtime[hour].imported, realtime[hour].exported
            elif still_filling and (hour in realtime or ts not in stored):
                break  # a recent hour still filling in: stop here and try again next poll
            elif hour in realtime:
                imported, exported = realtime[hour].imported, realtime[hour].exported
            else:
                imported, exported = stored.get(ts, (0.0, 0.0))
            values = {"energy": imported, "return": exported}
            hour_rate = self.rate(service_point, hour)
            if hour_rate is not None:
                values["cost"] = imported * hour_rate
                values["compensation"] = exported * hour_rate  # export is credited at the same rate (net metering)
            for key, value in values.items():
                totals[key] += value
                rows[key].append(StatisticData(start=hour, state=value, sum=totals[key]))
            hour += HOUR
        return rows

    def _save(self, service_point, ids, rows):
        """Step 7: save the rows. Rows for hours already stored are replaced; the recorder writes in the background."""
        for key, statistic_rows in rows.items():
            money = key in ("cost", "compensation")
            metadata = StatisticMetaData(
                mean_type=StatisticMeanType.NONE,
                has_sum=True,
                source=DOMAIN,
                statistic_id=ids[key],
                name=f"National Grid {service_point} {STATISTICS[key]}",
                unit_class=None if money else EnergyConverter.UNIT_CLASS,
                unit_of_measurement=self.hass.config.currency if money else UnitOfEnergy.KILO_WATT_HOUR,
            )
            async_add_external_statistics(self.hass, metadata, statistic_rows)
