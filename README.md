# CI Carbon Tracker

Measures energy usage and CO2 emissions during CI runs. Posts a report as a PR comment and logs results to `carbon-history.csv`.

## How it works

The workflow in `.github/workflows/carbon-tracker.yml` uses two composite actions:

1. `./start` — installs dependencies and starts `tracker.py` in the background
2. Your CI steps run (build, test, etc.)
3. `./stop` — stops the tracker, posts a markdown report on the PR, and commits `carbon-history.csv`

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
