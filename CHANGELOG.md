# Changelog

## 1.3.1 (2026-11-22)

Hardening from a security review. Nothing to change in your setup.

- Numbers from National Grid are checked before they're used. A bill, settled reading or real-time read that holds
  something other than a finite number (missing, text, NaN or infinity) is skipped, instead of ending up in the
  Energy dashboard's statistics, where it would spoil every running total after it. Bills with negative charges are
  skipped too. Negative readings are still counted as export.
- Errors from National Grid are logged by their type and HTTP status only. The library's messages can include
  request addresses and parts of National Grid's reply, such as account numbers.
- Each release now includes **SHA256SUMS**, the checksum of `nationalgrid.zip`. To check a download, run
  `sha256sum -c SHA256SUMS` in the folder that holds both.

### Repository

- The Marketplace's HACS action and Home Assistant's hassfest are pinned to reviewed commits instead of following a
  branch. Every check job runs with a read-only token that its checkout doesn't keep.
- GitHub's release workflow runs the checks in a read-only job. A separate job, the only one that can write,
  installs nothing, rebuilds the files from the tag and publishes them only if they match what the checks built.
- The Gitea publisher sends its token only to an `https://` address (or plain `http://` to a local
  `GITEA_INTERNAL_URL`, such as a container name), follows no redirects, uploads only `nationalgrid.zip` and
  `SHA256SUMS`, and no longer prints Gitea's replies.

## 1.3.0 (2026-11-15)

**Needs Home Assistant 2026.11 or newer.** On an older version the Marketplace keeps offering 1.2.1.

- When National Grid stops accepting the saved password, the sign-in form now asks only for the new password, for
  the same email. A different login can no longer replace the entry by mistake.
- Adding a login that's already set up stops straight away, without signing in to National Grid first.
- Meters are found once when the integration starts, before the first update. If National Grid can't be reached
  then, Home Assistant retries the setup on its own.
- Sensor names now come from the translations, as Home Assistant expects. Entity IDs, unique IDs and statistic IDs
  are unchanged, so the Energy dashboard keeps its history.

### Repository

- Targets only the latest Home Assistant (2026.11): `hacs.json`, the README and the workflows say so, and code kept
  only for older versions is gone. The setup form uses Probatio, Home Assistant's validation library since 2026.9,
  instead of the `voluptuous` name that only remains as a compatibility alias. The "re-authentication successful"
  text is no longer shipped, because Home Assistant now translates it itself.
- Typed config entry, coordinator and sensor setup, the typed `DeviceInfo`, and `PARALLEL_UPDATES` for the sensors.

## 1.2.1 (2026-11-15)

- Updated py-nationalgrid to 0.6.8. When National Grid stops accepting the saved password (say, after it was
  changed on their website), Home Assistant now asks for it again, instead of logging a failed update at every poll.

### Repository

- Gitea is the main copy: its runner checks every push and publishes releases (`.gitea/workflows/`), with nothing
  downloaded from GitHub, so it keeps working when GitHub can't be reached. Gitea push-mirrors to GitHub, and every
  push from it publishes on GitHub the releases GitHub doesn't have yet, with the same files and notes, where the
  Marketplace installs from.
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
