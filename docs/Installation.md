# Installation

**Needs:** Home Assistant 2026.9 or newer, a [National Grid online account](https://www.nationalgridus.com/) (the
email and password you use on National Grid's website), and an **electric smart meter**. Gas meters, and electric
meters without smart meter data, are skipped.

## From the Marketplace

In Home Assistant 2026.11 and newer, open **Settings → Marketplace**, search for **National Grid** and install it, then
restart Home Assistant. Updates then show up under **Settings → Updates**.

If it isn't listed yet, add it from its link instead: this repository's address,
`https://github.com/soullink9/HA-Marketplace-National-Grid`. Adding from a link needs Home Assistant to be connected to GitHub.

To install by hand instead, follow the steps below.

## 1. Download

Copy the [`custom_components/nationalgrid`](../custom_components/nationalgrid) folder from this repository into
`/config/custom_components/` (so you end up with `/config/custom_components/nationalgrid/manifest.json`), then
restart Home Assistant.

Home Assistant installs the one library it needs, [py-nationalgrid](https://github.com/virtitnerd/py-nationalgrid),
by itself on the first start.

## 2. Sign in

Go to **Settings → Devices & services → Add integration → National Grid**, and enter the email and password you use
on National Grid's website.

One entry covers every account linked to that login, and every electric smart meter on those accounts. Each meter
becomes a device named **National Grid** followed by its service point number. Adding the same login twice is refused.

## 3. The first start

The first start imports **all the history National Grid still has** for each meter, hour by hour, so it can take a
few minutes. Home Assistant shows the integration as loading until it's done. After that, it only fetches what's new.

If National Grid's settled data service is down at that moment, the integration starts with the last week of
real-time data and tries the full import again a few hours later.

Then set up the Energy dashboard: the [Energy Dashboard](Energy-Dashboard.md) page shows what to pick for each field.

## Coming from Opower

The Opower integration's National Grid support stopped working when National Grid changed its systems in early 2026.
To switch:

1. Remove the Opower entry (**Settings → Devices & services → Opower → ⋮ → Delete**). Its old statistics stay in
   the database.
2. Add National Grid as above.
3. In the Energy dashboard settings, **replace** the Opower statistics with this integration's. Don't list both, or
   the overlapping hours count twice.

Because this integration imports your full history, you don't lose past data by switching.

## Changing your password

When National Grid stops accepting the saved password, Home Assistant shows a **Reconfiguration required** notice.
Open it and enter the new password. The integration doesn't keep retrying a rejected password.

## Updating

Replace the `nationalgrid` folder with the new version from this repository and restart. The
[changelog](../CHANGELOG.md) lists what changed. Your statistics and entities carry over. If a release changes how
past hours are stored, it re-imports your history once by itself after the update.

## Removing

1. **Settings → Devices & services → National Grid → ⋮ → Delete**.
2. Delete the `/config/custom_components/nationalgrid` folder and restart.

The long-term statistics stay in Home Assistant's database, so the Energy dashboard keeps the history it already
showed. Remove them from the Energy dashboard settings if you no longer want them.
