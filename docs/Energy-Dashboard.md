# Energy Dashboard

The Energy dashboard reads the integration's **long-term statistics**, not its sensors. National Grid's data arrives
late, and statistics let each hour land in the right place (and be corrected later), which a sensor can't do.

Open **Settings → Dashboards → Energy** and, in the **Electricity grid** section, fill in the grid entry for each
meter. `<service point>` below is the meter's service point number, which is also in its device name.

| Field | Pick |
|---|---|
| Grid consumption (energy imported) | **National Grid `<service point>` energy imported** |
| Its cost: use a statistic tracking the total cost | **National Grid `<service point>` cost** |
| Return to grid (energy exported) | **National Grid `<service point>` energy exported** |
| Its compensation: use a statistic tracking the total compensation | **National Grid `<service point>` export credit** |
| Grid power (measurement type **Standard**) | the **Grid power** sensor of that meter's device |

Notes:

- **Exported energy and export credit** are only non-zero if you send power back to the grid (solar, for example).
  It's fine to fill them in anyway.
- **Grid power** is positive while you take power from the grid and negative while you send it back, which is what
  the **Standard** measurement type expects. It's the average over the latest 15-minute interval, so it lags by
  however long National Grid takes to publish that interval.
- **Don't use the Energy imported today or Cost today sensors** here. They reset at midnight and only cover today;
  the statistics above cover everything.
- If you have more than one meter, add a grid entry for each.

## When the numbers show up

- **Hours arrive in whole steps.** An hour is added once all four of its 15-minute reads are in, so the latest hour
  shows up a little after it ends, depending on National Grid.
- **Recent hours can change slightly.** Real-time reads are National Grid's provisional figures. Once a day, the last
  four days are rewritten with the exact meter readings, so the dashboard may shift by small amounts for recent days.
- **Cost appears once bills are read.** Until the bill history has been fetched (shortly after setup), new hours have
  energy but no cost. Those hours are priced as soon as the rates are known.

[How It Works](How-It-Works.md) explains each of these in detail.

## Statistic IDs

If you build your own cards (a **Statistics graph**, for example) or automations, the IDs are:

| Statistic | ID |
|---|---|
| Energy imported (kWh) | `nationalgrid:<service point>_energy` |
| Energy exported (kWh) | `nationalgrid:<service point>_return` |
| Cost (your currency) | `nationalgrid:<service point>_cost` |
| Export credit (your currency) | `nationalgrid:<service point>_compensation` |

These IDs never change between versions, so your Energy dashboard setup keeps working after updates.
