# Disclosure

This project was primarily created for personal use and for my family. While I may provide updates, they are not guaranteed. However, if you've stumbled upon this and find it interesting, feel free to download and use it. I had a great time building this and hope you enjoy it.

Note: Built with the assistance of Claude.ai. I’m putting it here now so you don't have to hunt for it below.

<p align="center">
  <img src="docs/images/logo.png" alt="soullink9 logo" width="200">
</p>

# National Grid for Home Assistant

Your National Grid (US) smart meter's electric usage and cost in Home Assistant, in 15-minute steps instead of
days behind. It takes over from the Opower integration's National Grid support, which stopped working when
National Grid changed its systems in early 2026.

[![Open your Home Assistant instance and open this repository in the Marketplace.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=soullink9&repository=HA-Marketplace-National-Grid&category=integration)

[![Open your Home Assistant instance and start setting up National Grid.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=nationalgrid)

- near-real-time usage from National Grid's 15-minute reads, checked every 15 minutes
- everything the Energy dashboard's grid entry asks for: energy imported, energy exported, cost, export credit
  and grid power
- all the history National Grid still has for your meter, imported on the first run
- estimates swapped for National Grid's exact meter readings once they're published, so past hours end up exact
- cost from your own bills (total charges ÷ kWh, so supply, delivery, taxes and fees are all in)
- no gaps or double counting through clock changes, outages and restarts

Setup is all in the UI: no YAML, no helpers to create.

Not affiliated with or endorsed by National Grid, whose name is its trademark. The icon is original artwork made for this project.

## Install

**Needs:** Home Assistant 2026.9 or newer, a [National Grid online account](https://www.nationalgridus.com/), and
an electric smart meter. Gas meters, and electric meters without smart meter data, aren't supported.

1. **Download.** Install **National Grid** from the Marketplace (**Settings → Marketplace**, Home Assistant 2026.11 and newer), or copy the [`custom_components/nationalgrid`](custom_components/nationalgrid) folder into `/config/custom_components/` and restart Home Assistant.
2. **Sign in.** Press the button above, or go to **Settings → Devices & services → Add integration → National Grid**, and enter the email and password you use on National Grid's website. The first start imports your history, which can take a few minutes.
3. **Connect the Energy dashboard.** The [Energy Dashboard](docs/Energy-Dashboard.md) page shows what to pick for each field.

## Documentation

The other pages here cover everything else:

| Page | What's in it |
|---|---|
| [Installation](docs/Installation.md) | Download, sign-in, the first start, coming from Opower, updating and removing. |
| [Energy Dashboard](docs/Energy-Dashboard.md) | What to pick for each field of the grid entry. |
| [How It Works](docs/How-It-Works.md) | Real-time and settled data, the history import, daily corrections, and how cost is worked out. |
| [Sensors and Statistics](docs/Sensors-and-Statistics.md) | Every sensor and statistic, with its ID. |
| [Troubleshooting](docs/Troubleshooting.md) | Missing meters or statistics, sign-in problems, and the log. |
| [Privacy](docs/Privacy.md) | What's stored and what leaves your Home Assistant. |
| [Development](docs/Development.md) | The simulation test and the file map. |

## Privacy

The integration only talks to National Grid, with the email and password you enter, which Home Assistant keeps
like any other integration's sign-in. Nothing goes anywhere else. See [Privacy](docs/Privacy.md).

## Contributing

Bug reports and pull requests are welcome: [open an issue](https://github.com/soullink9/HA-Marketplace-National-Grid/issues/new/choose). [CONTRIBUTING.md](CONTRIBUTING.md) covers how the code is laid out, how to run the checks and how to release a new version.

## Credits

This integration stands on other people's work:
- [py-nationalgrid](https://github.com/virtitnerd/py-nationalgrid) by virtitnerd (Apache-2.0) does all of the talking to National Grid: signing in, accounts, real-time and settled usage, and bills. It's installed automatically.
- [ha_nationalgrid](https://github.com/virtitnerd/ha_nationalgrid) by virtitnerd, a fork of [Ryan Morash's original integration](https://github.com/ryanmorash/ha_nationalgrid): this integration's approach came from studying it, in particular joining National Grid's settled readings with its real-time reads, working out cost rates from bill history (total charges ÷ kWh, blended over the last three bills), and the cookie setup National Grid's sign-in needs. Ryan Morash first worked out National Grid's new API, in [aionatgrid](https://github.com/ryanmorash/aionatgrid).
- Home Assistant's [Opower integration](https://github.com/home-assistant/core/tree/dev/homeassistant/components/opower) by tronikos: the pattern for writing usage, cost and compensation as long-term statistics for the Energy dashboard.

Everything else was written for this project, with help from Claude, Anthropic's AI model.

## License

[GNU General Public License v3.0](LICENSE). You may use, study, share and change this integration; if you share a changed version, share its source under the same licence.
