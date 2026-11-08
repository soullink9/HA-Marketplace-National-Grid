# Development

For anyone changing the code. [CONTRIBUTING.md](../CONTRIBUTING.md) has the rules the code keeps, how to check a change
and how to release.

## Files

```
custom_components/nationalgrid/
  __init__.py        sets up and unloads a login (a config entry); statistics stay when it's removed
  const.py           the domain, the statistic keys, and every timing (poll, settle window, retries)
  coordinator.py     everything that talks to National Grid and writes the statistics
  sensor.py          the four sensors per meter
  config_flow.py     the sign-in form, also used for re-authentication
  manifest.json      metadata, version and the pinned py-nationalgrid
  translations/en.json   form text
  brand/             icon.png, icon@2x.png
tests/
  README.md          what each test checks
  stubs.py           stand-ins for the parts of Home Assistant the integration uses
  test_integration.py  nine days against a fake National Grid
  test_release.py    the release scripts, publishing against a fake Gitea
scripts/             the release helpers both release workflows use (see Tests and releases below)
.gitea/workflows/    tests and releases on Gitea, the main copy (no GitHub needed)
.github/workflows/   GitHub's checks (hassfest, the Marketplace's) and its copy of each release
docs/   these pages
```

## How data flows

`NationalGridCoordinator._async_update_data` runs every 15 minutes:

1. On the first poll it finds the meters (`_find_meters`): every electric smart meter on every linked account.
2. Every 12 hours it reads bill history and works out each bill period's rate and the blended rate
   (`_update_rates`). A new bill schedules its period to be rewritten.
3. On the first poll of each day it schedules the last four days to be rewritten (`SETTLE` in `const.py`).
4. For each meter, `_update_meter` runs seven steps in order, each its own method:

   | Step | Method | What it does |
   |---|---|---|
   | 1 | `_last_stored` | Finds where each statistic ends: its last hour and running total. |
   | 2 | `_first_hour_to_write` | Picks the first hour to write, and whether a full history import is due. |
   | 3 | `_stored_hours` | When rewriting, loads the stored hours and the running totals just before the first hour. |
   | 4 | `_fetch_settled` | Fetches settled (exact) readings for anything more than a day old. |
   | 5 | `_fetch_realtime` | Fetches the real-time 15-minute reads and adds them up per hour (`RealtimeHour`). |
   | 6 | `_build_rows` | Walks the hours in order, choosing the best data for each, with running totals. |
   | 7 | `_save` | Writes the rows to Home Assistant's statistics. |

The coordinator's `data` is each meter's recent real-time reads, which the sensors read. The Energy dashboard reads
the statistics, written with `async_add_external_statistics`.

**Choosing data for an hour:** settled data wins; then a complete real-time hour; a recent incomplete hour stops the
walk until the next poll; an older incomplete hour uses what there is (or what was stored) until settled data
replaces it.

**Re-importing everyone's history:** bump `HISTORY_VERSION` in `const.py`. The version that's been imported is kept in
the config entry's data under `history`.

## Tests

```sh
python3 tests/test_integration.py
python3 tests/test_release.py
python3 scripts/build_package.py
```

The simulation is plain Python 3.13, nothing to install. It polls every 15 minutes from a fresh install through nine days that include
the end of daylight saving time, a meter outage only settled data knows about, outages of the settled service and of
everything, Home Assistant off for 36 hours and restarted from scratch, a new bill mid-month, and solar export. At the
end every statistic must be continuous, running totals must add up, settled hours must match the truth exactly, and
every cost must equal energy × that hour's rate. It prints `all checks passed` when all is well.

The stand-ins can't prove the integration works with real Home Assistant or real National Grid data; try changes
on a real installation too. Gitea's runner and GitHub also run `ruff`, the release tests and the zip build; GitHub adds
Home Assistant's `hassfest` and the Marketplace's checks.

## Tests and releases: the files

Gitea is the main copy of this repository; it push-mirrors to GitHub, the public copy people install from.

| File | What it does |
|---|---|
| `.gitea/workflows/test.yml` | Runs every check on each push to Gitea (lint, the tests and building the zip, on Python 3.14), with no actions downloaded from GitHub |
| `.gitea/workflows/release.yml` | Publishes a release on Gitea (Run workflow button, or a pushed version tag); its tag then reaches GitHub through the push mirror |
| `.github/workflows/release.yml` | Publishes the same release on GitHub when a version tag arrives there (or from its own Run workflow button): the copy the Marketplace installs from |
| `.github/workflows/ci.yml` | GitHub's checks on every push: lint, the tests and Home Assistant's `hassfest` (which comes from GitHub, so it runs only there) |
| `.github/workflows/validate.yml` | The Marketplace's own checks (the HACS action), which its catalog requires; GitHub only, for the same reason |
| `scripts/release_notes.py` | Shared by both release workflows: checks the version, gives the release's title, writes the notes (install steps with the zip's address on GitHub, then the changelog section) |
| `scripts/build_package.py` | Builds `dist/nationalgrid.zip`, the same bytes every time, and checks it with `check_package.py` |
| `scripts/check_package.py` | Checks the zip the way it gets installed: one `nationalgrid/` folder, a manifest for that domain at the repository's version, the icon, exactly the integration's files |
| `scripts/publish_gitea_release.py` | Creates or updates the Gitea release and uploads its files, through Gitea's API (standard library only) |
| `tests/test_release.py` | Tests all four scripts, publishing against a fake Gitea server |
