# Troubleshooting

Start with the log: **Settings → System → Logs**, search for `nationalgrid` (and `py_nationalgrid` for the library).

## Setup says "Invalid email or password"

Use the email and password you sign in with on National Grid's website. Check you can sign in there first; if
National Grid asks you to reset your password or accept new terms, do that on the website, then try again.

## Setup says "Could not reach National Grid"

Home Assistant couldn't get through to National Grid: a network problem, or National Grid's site is down. Try again
later. Check Home Assistant can reach the internet.

## "This account is already configured"

That login is already added. One entry covers every account and meter linked to it.

## No devices after setup

The login has no electric smart meter with 15-minute data. Gas meters and meters without smart meter (AMI) data are
skipped. Check National Grid's website shows interval (15-minute or hourly) usage for your meter.

## "Reconfiguration required"

National Grid stopped accepting the saved password (you changed it, for example). Open the notice and enter the
current password. Updates stop until you do, so the account isn't locked by repeated failed sign-ins.

## The statistics aren't in the Energy dashboard's list

- On a new install, wait for the history import to finish (a few minutes).
- Look for names starting with **National Grid** and the meter's service point number.
- **Developer tools → Statistics** lists them; search for `nationalgrid`.

## The newest hours are missing

Normal. An hour is only added once National Grid has published all four 15-minute reads for it, and National Grid
publishes them with a delay. If nothing new has appeared for many hours, check the log for warnings, and check
National Grid's website shows recent usage.

## Recent days changed a little

Also normal. Once a day the last four days are swapped from National Grid's provisional real-time figures to its
exact meter readings. See [How It Works](How-It-Works.md).

## Cost is missing or zero

- Cost needs your bill history. Right after setup there's a short wait until it's read; earlier hours are priced
  then.
- A warning **Could not fetch National Grid bill history** in the log means the billing service was down. Usage is
  still recorded, and cost is filled in once bills come back.
- A brand-new account without a bill with usage yet has no rate to use.

## "National Grid settled usage unavailable, using real-time data"

National Grid's settled data service didn't answer. The integration keeps going on real-time reads and tries again
an hour later. If it lasts days, recent hours keep their provisional figures until it's back; nothing is lost.

## The numbers don't match my bill exactly

Hours inside a past bill period are priced at that bill's own rate, so whole bill periods should match closely.
Hours since your last bill use the blended rate of your last three bills, so they're an estimate until the next bill
arrives and reprices them.

## Debug logging

On the integration's page choose **Enable debug logging**, wait for a couple of polls (15 minutes each), then choose
**Disable debug logging** to download the log. It can contain your email, account and meter numbers: remove them
before posting.

## Still stuck

[Open an issue](https://github.com/soullink9/HA-Marketplace-National-Grid/issues/new/choose) with the National Grid
form, your versions and the log.
