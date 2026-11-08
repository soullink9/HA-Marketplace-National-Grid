# Changelog

## Unreleased

### Repository

- Gitea is the main copy: its runner checks every push and publishes releases (`.gitea/workflows/`), with nothing
  downloaded from GitHub, so it keeps working when GitHub can't be reached. Gitea push-mirrors to GitHub, and a
  version tag arriving there publishes the same release on GitHub, where the Marketplace installs from.
- The release helpers live in `scripts/` and are used by both: the version check and notes, building the zip, and
  publishing on Gitea. Every release's notes now start with how to install it.
- The release's zip is now always `nationalgrid.zip` (it had the version in its name), so
  `.../releases/latest/download/nationalgrid.zip` always gets the newest. Each zip is checked before it's published.

## 1.2.0 (2026-11-04)

- Moved to its own repository, [HA-Marketplace-National-Grid](https://github.com/soullink9/HA-Marketplace-National-Grid), so it can be installed and updated
  from the Home Assistant Marketplace (Home Assistant 2026.11 and newer). Installing by hand works as before.
- Lists its categories, so it shows up in the right place when browsing the Marketplace. No other changes to how
  the integration works.

## 1.1.1 (2026-11-02)

- No changes to the integration.

## 1.1.0 (2026-11-01)

- No changes to the integration.

## 1.0.2 (2026-11-01)

- A new icon: original artwork of an electricity meter, in place of National Grid's artwork.

## 1.0.0 (2026-11-01)

Initial release.

- Near-real-time electric usage from National Grid (US) smart meters, in 15-minute steps, polled every 15 minutes.
- Everything the Energy dashboard's grid entry asks for: energy imported, energy exported, cost, export credit
  and a grid power sensor.
- Imports all the history National Grid still has for your meter on the first run.
- Real-time estimates are replaced with National Grid's settled meter data once a day, so past hours end up exact.
- Cost from your own bills (total charges ÷ kWh for each bill period), repriced when a new bill arrives.
- Handles the daylight saving time changes, National Grid outages and Home Assistant restarts without gaps
  or double counting.
- Setup in the UI, with re-authentication when your password changes.
