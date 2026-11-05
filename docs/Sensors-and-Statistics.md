# Sensors and Statistics

Every electric smart meter becomes a device named **National Grid `<service point>`**, where `<service point>` is
the meter's service point number from National Grid.

## Sensors

The sensors are for dashboards and automations. The Energy dashboard uses the statistics below instead.

| Sensor | Entity ID | What it shows |
|---|---|---|
| **Grid power** | `sensor.national_grid_<service point>_grid_power` | Average power over the latest 15-minute interval, in kW. Positive when taking power from the grid, negative when sending it back. The `interval_end` attribute says when that interval ended, so you can tell how fresh it is. |
| **Energy imported today** | `sensor.national_grid_<service point>_energy_imported_today` | kWh taken from the grid since midnight, from real-time reads. Resets at midnight. |
| **Cost today** | `sensor.national_grid_<service point>_cost_today` | Today's imported energy times the effective rate, in your Home Assistant currency. Unknown until bills are read. |
| **Effective rate** | `sensor.national_grid_<service point>_effective_rate` | Your all-in cost per kWh, blended over the last three bills (total charges ÷ kWh). Unknown until bills are read. |

They update every 15 minutes. "Today" follows real-time reads, so it lags by however long National Grid takes to
publish them, and it uses provisional figures (the statistics are corrected later; these sensors aren't).

If you renamed the device or entities, the entity IDs will differ; the unique IDs behind them don't change.

## Long-term statistics

Each meter gets four hourly statistics. They hold the whole history, and are what the Energy dashboard reads (see
[Energy Dashboard](Energy-Dashboard.md)).

| Statistic | ID | Unit |
|---|---|---|
| National Grid `<service point>` energy imported | `nationalgrid:<service point>_energy` | kWh |
| National Grid `<service point>` energy exported | `nationalgrid:<service point>_return` | kWh |
| National Grid `<service point>` cost | `nationalgrid:<service point>_cost` | your currency |
| National Grid `<service point>` export credit | `nationalgrid:<service point>_compensation` | your currency |

They aren't entities, so they don't appear in the entity list. Find them in **Developer tools → Statistics**, or
pick them in the Energy dashboard or a **Statistics graph** card.

The statistic IDs never change between versions. Removing the integration leaves them in the database.
