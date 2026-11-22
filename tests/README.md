# Tests

Run everything from the repository root. Each test is a plain Python script, not a pytest suite: it prints what it
checks and exits non-zero if anything failed. These are the commands the Test workflow runs:

```sh
python3 tests/test_integration.py
python3 tests/test_bad_data.py
python3 tests/test_release.py
```

| Script | What it checks |
|---|---|
| `test_integration.py` | Nine days of the integration against a fake National Grid, checked against the true usage |
| `test_bad_data.py` | What National Grid could send that isn't usable: bills, settled readings and real-time reads holding NaN, infinity, text or nothing never reach the statistics or sensors, and errors are logged by type and HTTP status, never with their message |
| `test_release.py` | The release scripts in `scripts/`: the version check and notes, building and checking the zip, publishing to a fake Gitea server (including where the token may be sent and which files may be uploaded), and working out which releases GitHub still needs |

[CONTRIBUTING.md](../CONTRIBUTING.md#checking-a-change) says which to run for which change, and how long each takes.
The tests stand in for Home Assistant (`stubs.py`), so they can't prove the integration works on a real Home
Assistant: try changes on a real installation too.
