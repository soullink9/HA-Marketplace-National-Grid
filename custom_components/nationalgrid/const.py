"""Constants shared by the National Grid integration."""

from datetime import UTC, datetime, timedelta

DOMAIN = "nationalgrid"

# Bump this to make every installation re-import its full history once (for example after a change to how
# hours are stored). The current value is kept in the config entry's data under "history".
HISTORY_VERSION = 3

# The four long-term statistics each meter gets, keyed by the suffix of their statistic ID
# ("nationalgrid:<service point>_<key>"). These IDs are what users pick in the Energy dashboard: never rename them.
STATISTICS = {
    "energy": "energy imported",
    "return": "energy exported",
    "cost": "cost",
    "compensation": "export credit",
}

EPOCH = datetime(1970, 1, 1, tzinfo=UTC)  # "the beginning": asks National Grid for everything it has
HOUR = timedelta(hours=1)
QUARTER = timedelta(minutes=15)  # National Grid's real-time interval, and how often we poll

# Once a day, hours this far back are rewritten so settled meter data replaces the real-time estimates.
SETTLE = timedelta(days=4)
# National Grid's real-time feed only goes back about a week.
REALTIME_DAYS = timedelta(days=7)
# Bill history (and so the cost rates) is checked this often.
RATES_EVERY = timedelta(hours=12)
# After the settled-data request fails, wait this long before asking again (longer when nothing came back at all).
RETRY_AFTER_ERROR = timedelta(hours=1)
RETRY_AFTER_EMPTY = timedelta(hours=6)
# A recent hour still missing intervals is left for later until this long after the newest reading.
FILL_GRACE = timedelta(hours=3)
