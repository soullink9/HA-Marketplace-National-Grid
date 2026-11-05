# How It Works

## Two kinds of data

National Grid offers two kinds of usage data for a smart meter, and the integration uses both:

| | Real-time reads | Settled data |
|---|---|---|
| What it is | 15-minute intervals, published soon after each one | The exact meter readings |
| When it arrives | Shortly after the interval (how soon is up to National Grid) | A day or two later |
| How exact | Provisional: can be a little off | Exact |
| How far back | About a week | The life of the meter |

Every 15 minutes the integration fetches the newest real-time reads and turns them into **hourly** statistics, the
format the Energy dashboard reads. Settled data replaces those hours later.

## The poll, every 15 minutes

1. **New hours are added** from real-time reads. An hour is only added once all four 15-minute reads are in, so a
   half-reported hour never shows a low number.
2. If a recent hour is still missing reads, it waits for the next poll. After about three hours it stops waiting:
   an older hour with gaps (a meter outage, for example) is stored with what there is, and settled data fixes it later.

Each stored hour carries a running total. Whenever past hours are rewritten, every hour after them is rewritten
too, so the totals always add up and nothing is counted twice or lost.

## Daily corrections

On the first poll of each day, the **last four days** are rewritten from settled data. That swaps the provisional
real-time figures for the exact meter readings, and fills in any hours the real-time feed missed. After that,
past hours don't change again (unless a new bill reprices them, below).

If the settled data service is down, the integration keeps adding new hours from real-time reads, leaves the
correction pending, and tries again an hour later.

## The history import

A new installation imports **everything National Grid still has** for each meter from settled data. If nothing
comes back (the service is down), it carries on with the last week of real-time data and retries the import six
hours later. Once the import has finished, it's remembered, so restarts don't repeat it.

## Cost

Cost comes from **your own bills**, which the integration reads every 12 hours:

- **Each bill's rate** is its total charges divided by its kWh. That way supply, delivery, taxes and fixed fees are
  all included, so the total matches what you actually pay.
- **Each hour is priced at the rate of the bill period it falls in.**
- **Hours not covered by a bill yet** (everything since your last bill) use the **blended rate** of your last three
  bills: their total charges divided by their total kWh. That's also the **Effective rate** sensor.
- **When a new bill arrives**, its whole period is repriced at that bill's own rate, so past months end up matching
  your bills.
- **Export credit** uses the same rate as cost, as with net metering.

Bills with no usage are skipped. If the bill history can't be fetched, usage tracking carries on, and those hours
are priced once rates are known.

## Clock changes, outages and restarts

- **Daylight saving time:** hours are counted in UTC, so the repeated hour in November and the skipped hour in March
  are each handled exactly once.
- **National Grid outages:** a failed poll is retried at the next one, and the Energy dashboard just shows the hours
  a little later.
- **Home Assistant restarts or long downtime:** the integration carries on from the last stored hour and backfills
  the gap from settled data.

## Which meters are included

Every **electric** meter with smart meter (AMI) data on every account linked to your login. Gas meters and meters
without smart meter data have no 15-minute reads, so they're skipped.
