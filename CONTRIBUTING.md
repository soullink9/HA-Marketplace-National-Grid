# Contributing to the National Grid integration

Thanks for helping. This page is for anyone changing the code: where things live, the rules the code keeps,
how to check a change, and how to release one.

## Ground rules

- **Keep it slim.** The whole integration is a few hundred lines. Prefer a small, clear change over a new layer.
- **Only National Grid is contacted, and only through [py-nationalgrid](https://github.com/virtitnerd/py-nationalgrid).**
  No other services, analytics or update checks. If National Grid changes its API, the fix belongs in the library;
  here we only bump the pinned version in `manifest.json`.
- **Never rename an ID people depend on.** The statistic IDs (`nationalgrid:<service point>_energy`, `_return`,
  `_cost`, `_compensation`) are what users pick in their Energy dashboard, and the sensors' unique IDs
  (`<service point>_power` and so on) keep their entity IDs and history. Renaming either silently breaks
  existing setups.
- **Running totals must always add up.** Every statistic row carries a running total. Any change that rewrites
  past hours must rewrite every row after them too (`_stored_hours` and `_build_rows` in `coordinator.py` already do this).
- **Do hour math in UTC.** Adding an hour in local time skips the repeated hour when daylight saving time ends.
  Use `_hour()` in `coordinator.py`.

## Where things live

The [Development](docs/Development.md) page has the full file map. The usual places to make a change:

| To change | Look in |
|---|---|
| Timings: poll interval, how far back the daily correction reaches, retry delays | `const.py` |
| How usage is fetched and written to the Energy dashboard statistics | `coordinator.py`: `_update_meter` and its seven step methods |
| How cost rates are worked out from bills | `coordinator.py`, `_update_rates` and `rate` |
| Which meters are included | `coordinator.py`, `_find_meters` |
| The sensors | `sensor.py` |
| The setup and re-authentication form | `config_flow.py`, with its text in `translations/en.json` |
| The icon | `brand/icon.png` (256×256) and `brand/icon@2x.png` (512×512), drawn from `docs/images/icon.svg` |

**Rebuilding everyone's history:** if a change means stored hours are wrong (not just future ones), bump
`HISTORY_VERSION` in `const.py`. Every installation then re-imports its full history once after updating.

## Checking a change

You need Python 3.13 or newer (Home Assistant 2026.9 itself runs on 3.14, which is what the workflows use). Nothing
else is needed for the simulation; `ruff` is the only tool to install.

| Command | When |
|---|---|
| `ruff check custom_components tests` and `ruff format custom_components tests` | every change |
| `python3 tests/test_integration.py` | every change (takes a few seconds) |
| `python3 tests/test_release.py` | any change to `scripts/` or the release workflows |
| `python3 scripts/build_package.py` | before a release: builds `dist/nationalgrid.zip` and checks it installs |

The simulation runs the real integration code against stand-ins for Home Assistant (`tests/stubs.py`) and a fake
National Grid, polling every 15 minutes for nine days through a daylight saving change, outages, a Home Assistant
restart and a new bill. It checks every stored hour against the true usage and prints `all checks passed` when
all is well. When you fix a bug, add the situation that caused it to the scenario so it stays fixed.

Gitea's runner runs `ruff`, the simulation, the release tests and the zip build on every push
(`.gitea/workflows/test.yml`). On GitHub the same checks run plus Home Assistant's `hassfest` and the Marketplace's
own checks, which come from GitHub and can only run there. [tests/README.md](tests/README.md) lists what each test
checks.

Code style: `ruff` settles formatting and import order (see `pyproject.toml`). Every function and class has a
docstring, and comments say why, not what.

## Documentation

[README.md](README.md) is the front page, and every other page lives in [`docs/`](docs). When a change alters
something a page describes, update that page in the same commit.

## Standards for every change

- **Readable over clever.** Write code a newcomer can follow on the first read. Prefer a few plain lines with a named
  variable to a dense one-liner, a nested conditional expression, or a trick that needs a comment to decode.
- **Comment the why.** Every function and class has a docstring. Comments explain why the code does something
  non-obvious (a quirk of the device or service, a Home Assistant rule, a deliberate trade-off), not what each line
  does.
- **Keep names consistent.** Follow the names already used in the integration: the same words for
  the same things, Home Assistant's conventions for entities and config entries, `snake_case` for Python names and
  `camelCase` for JavaScript.
- **Keep the docs in step.** When you change a function, class or behaviour, update its docstring, its comments and the
  pages under `docs/` (and the README) that describe it in the same commit.
- **Keep the tests green.** Every change keeps existing behaviour and passes all of the tests. When you
  fix a bug, add the situation that caused it to the tests so it stays fixed.
- **No new dependencies without approval.** Don't add a third-party library (to a `manifest.json`, a
  `requirements.txt` or CI) without asking in an issue first. This page says what it already depends on and why.

### Test layout

The tests use these names:

```
tests/
  stubs.py                stand-ins for Home Assistant and the libraries the integration uses
  test_integration.py     the real integration against the stand-ins and a fake device or service
  test_<subject>.py       any other checks (test_engine.py, test_blueprint.py, test_live_proxy.py)
  test_<subject>_soak.py  a long simulation: it takes a length as an argument, and CI runs a short one
  fake_<service>.py       a fake device or service, when it's too big to live inside the test
  requirements.txt        what the tests need beyond Python, if they need anything
```

Every `test_*.py` is a plain script, not a pytest suite: run it with `python3` from the repository root, and it
exits non-zero if any check fails.

### The Marketplace

`hacs.json` at the root is the Marketplace's file: the name it lists and the oldest Home Assistant version the
integration works with. Keep that version in step with the README's requirements.

## Commits

Use [Conventional Commits](https://www.conventionalcommits.org/): a type, an optional scope, then a short summary in
the imperative.

```
feat: add a diagnostics download
fix: keep the last value when the service is briefly unreachable
refactor: split the coordinator's update into steps
docs: explain the safety settings
test: cover a reply with a missing field
chore: update the CI actions
```

## Releasing

Gitea is the main copy of this repository. It push-mirrors to GitHub, which is the public copy: the Marketplace
installs from GitHub's releases, so every link in the docs and release notes points there.

1. Bump `version` in `custom_components/nationalgrid/manifest.json`. Versions go up together: there is only this
   one.
2. Add the release to the top of [CHANGELOG.md](CHANGELOG.md), under a heading `## X.Y.Z (date)` (move what's under
   `## Unreleased` into it).
3. Run the checks above.
4. Commit and push to Gitea, then publish with Gitea's **Release** workflow (`.gitea/workflows/release.yml`),
   either way:
   - **Actions → Release → Run workflow**, and enter the version without the `v` (for example `1.2.1`). It
     creates the tag `v1.2.1` on the commit it releases.
   - or push a version tag: `git tag v1.2.1 && git push origin v1.2.1`.

   The workflow checks the version matches the manifest and `CHANGELOG.md` (`scripts/release_notes.py`), runs every
   check, builds `nationalgrid.zip` and checks it installs as `custom_components/nationalgrid/`
   (`scripts/build_package.py`), and publishes the release on Gitea with the zip and notes: install steps, then that
   version's changelog section (`scripts/publish_gitea_release.py`). A version with a suffix (`-beta`) is published
   as a pre-release. If any check fails, nothing is published. Running it again for the same version updates the
   release and replaces its zip.

5. Gitea's push mirror then sends the commits and the new tag to GitHub, at its next push (every 8 hours). Every push
   from it starts GitHub's own **Release** workflow (`.github/workflows/release.yml`), which publishes each version
   tag that has no GitHub release yet: the same checks, then the same files (the builds are repeatable, byte for
   byte), title and notes, so GitHub's releases match Gitea's. The Marketplace picks it up from GitHub. If GitHub is
   down, the mirror catches up later; the Gitea release is already done. Don't make releases or tags on GitHub
   itself: the mirror deletes tags Gitea doesn't have, and GitHub follows Gitea on its own.

The Gitea workflows use no actions (`actions/checkout` and the like download from GitHub): each job runs in a plain
image from Docker Hub (`python:3.14-bookworm`) and fetches the code from Gitea with git, so testing and releasing
keep working when GitHub can't be reached. Only `ruff` comes from PyPI. When the runner's jobs can't reach Gitea at
its public address (a runner on the same Docker network as Gitea, say), set an Actions variable `GITEA_INTERNAL_URL`
to the address they can reach (`http://gitea-server:3000`); both workflows and the publish script use it.

Keep every tag on Gitea: the push mirror makes GitHub's tags match Gitea's, so a tag missing from Gitea is deleted on
GitHub, and the GitHub release on it turns into a draft.

## Reporting bugs

Open an issue with your Home Assistant version, the integration's version, what you did and what you expected.
The log helps: **Settings → System → Logs**, search for `nationalgrid`. Remove your email, account and meter
numbers before posting.

Please follow the [Code of Conduct](CODE_OF_CONDUCT.md).
