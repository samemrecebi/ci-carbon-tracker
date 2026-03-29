# CI Carbon Tracker

Measures energy usage and CO2 emissions during Github Action runs. Posts a report as a PR comment and logs results to `carbon-history.csv`.

## How it works

The workflow in `.github/workflows/carbon-tracker.yml` uses two composite actions:

1. `./start` — installs dependencies and starts `tracker.py` in the background
2. Your CI steps run (build, test, etc.)
3. `./stop` — stops the tracker, posts a markdown report on the PR, and commits `carbon-history.csv`

## Configuration

### Action inputs

The **start** action accepts:

| Input | Default | Description |
|---|---|---|
| `python-version` | `3.12` | Python version to use on the runner |
| `electricitymaps-token` | _(empty)_ | [Electricity Maps](https://www.electricitymaps.com/) API token for real-time carbon intensity data. Without it, CodeCarbon uses static grid averages. |
| `tracking-mode` | `machine` | `machine` measures the whole runner, `process` isolates just your CI job |
| `config-file` | `.cicarbon.json` | Path to the config file (relative to repo root) |

The **stop** action accepts:

| Input | Default | Description |
|---|---|---|
| `pr-comment` | `true` | Post the carbon report as a PR comment |
| `history-file` | `carbon-history.csv` | Path to the CSV history file (relative to repo root) |
| `create-issue` | `true` | Open a GitHub Issue when an energy threshold is exceeded |
| `issue-label` | `carbon-alert` | Label applied to carbon threshold issues |
| `config-file` | `.cicarbon.json` | Path to the config file (relative to repo root) |

### Config file (`.cicarbon.json`)

You can place a `.cicarbon.json` file in your repo root to customize thresholds and notification behavior. All fields are optional and fall back to defaults if omitted.

```json
{
  "thresholds": {
    "energy_wh": 0.15,
    "co2_g": null,
    "duration_s": null
  },
  "notifications": {
    "create_issue": true,
    "issue_label": "carbon-alert",
    "pr_comment": true
  },
  "codecarbon": {
    "pue": null,
    "force_cpu_power": null
  }
}
```

**Thresholds** control when alerts are triggered. Set a value to `null` to disable that threshold:

| Field | Type | Description |
|---|---|---|
| `energy_wh` | `float \| null` | Maximum energy consumption in watt-hours |
| `co2_g` | `float \| null` | Maximum CO2 emissions in grams |
| `duration_s` | `float \| null` | Maximum job duration in seconds |

**Notifications** control what happens when a threshold is exceeded:

| Field | Type | Description |
|---|---|---|
| `create_issue` | `bool` | Create or update a GitHub Issue on threshold breach |
| `issue_label` | `string` | Label applied to the issue |
| `pr_comment` | `bool` | Post the report as a PR comment |

**CodeCarbon** settings are passed directly to the CodeCarbon `EmissionsTracker`. Set a value to `null` to use CodeCarbon's default:

| Field | Type | Description |
|---|---|---|
| `pue` | `float \| null` | Power Usage Effectiveness of the data center. Multiplier applied to energy to account for cooling/overhead. Recommended value for GitHub-hosted runners us on 1.18, the reported value of Azure datacenters . Default: 1.0 |
| `force_cpu_power` | `int \| null` | Force a specific CPU TDP in watts. Useful for self-hosted runners where you know the exact hardware. On shared GitHub runners, CodeCarbon already scales by vCPU count so this is usually not needed. |

## Testing locally

Create a virtual environment and install dependencies:

```bash
python3 -m venv venv
source venv/bin/activate
pip install .
```

Run the local test:

```bash
source venv/bin/activate
bash test_local.sh
```

This simulates a 10-second CI job, prints the energy report, and appends a row to `carbon-history.csv`.

## PR comments

The stop action automatically posts a carbon report as a comment on the PR. It uses GitHub's built-in `GITHUB_TOKEN` — no bot or PAT needed. If the workflow runs again on the same PR, the previous comment is replaced so there's no spam.

## How `carbon-history.csv` avoids re-triggering workflows

After each run, the stop action commits the updated `carbon-history.csv` back to the branch. This commit is made as `github-actions[bot]` and uses `[skip ci]` in the commit message. Both of these prevent the workflow from re-triggering:

- Pushes by `github-actions[bot]` do not trigger `on: push` or `on: pull_request` events by default
- `[skip ci]` in the commit message is a GitHub-recognized flag that skips all workflow runs for that commit

## Testing on GitHub

Push a branch and open a PR. The workflow triggers automatically and posts a carbon report comment on the PR.

You can also trigger it manually from the Actions tab (workflow_dispatch).
