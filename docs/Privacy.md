# Privacy

## What leaves your Home Assistant

The integration talks **only to National Grid**, through the
[py-nationalgrid](https://github.com/virtitnerd/py-nationalgrid) library. There's no analytics, update check or
other service.

What it asks National Grid for:

| Request | How often |
|---|---|
| Sign-in with your email and password | when a session is needed |
| Your linked accounts and their meters | at each start |
| Real-time 15-minute reads | every 15 minutes |
| Settled meter readings | on the first start (everything), then once a day (the last few days) |
| Bill history (charges and kWh per bill) | every 12 hours |

## What's stored in Home Assistant

- **Your email and password**, in Home Assistant's own configuration storage, like any other integration's sign-in.
  They're sent only to National Grid.
- **Your hourly usage, cost and export history**, as long-term statistics in Home Assistant's database. They stay
  there if you remove the integration, so the Energy dashboard keeps its history.
- Your account, premise, service point and meter numbers, used to ask National Grid for the right meter. The service
  point number appears in device names and statistic IDs.

## Before you share a log or screenshot

Logs and screenshots can contain your email, account numbers and meter numbers. Remove them before posting them
anywhere.
