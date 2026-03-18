# CI Carbon Tracker — Plan

## Goal

A **reusable GitHub Action** that users drop into any existing workflow to track energy usage.
It measures energy while their steps run and prints a report at the end.

---

## How Users Will Use It

```yaml
# user's existing workflow
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: your-org/ci-carbon-tracker@v1   # ← they add this ONE line
                                               #   tracking starts here

      - name: Build Docker image              # ← their existing steps, unchanged
        run: docker build -t myapp .

      - name: Run tests
        run: pytest tests/
                                              # tracking stops + report printed after last step
```

No changes to their existing steps. One line added.

---

## How GitHub Actions Work (the building blocks)

A GitHub Action is just a repository with an `action.yml` file at the root.
When a user writes `uses: your-org/ci-carbon-tracker@v1`, GitHub:
1. Clones your repo at that tag/branch onto their runner
2. Reads `action.yml` to know what to run
3. Executes it

There are 3 action types:

| Type | How it runs | Best for |
|---|---|---|
| **JavaScript** | Node.js directly on runner | Fast, supports `pre`/`post` hooks |
| **Docker** | Pulls/builds a container | Fully controlled environment |
| **Composite** | Runs shell steps, like a mini workflow | Simple, no compilation needed |

---

## Best Pattern: JavaScript Action with `pre` / `post`

This is the cleanest approach. JavaScript actions support `pre` and `post` hooks:
- `pre`: runs **before** all other steps in the job → start tracking
- (user's steps run here)
- `post`: runs **after** all steps → stop tracking, print report

```
Job timeline:
  pre: (our action) → start tracker background process, note start time
  step 1: checkout
  step 2: docker build      ← user's existing steps, untouched
  step 3: pytest
  post: (our action) → stop tracker, read energy data, print/save report
```

The user only adds `uses: your-org/ci-carbon-tracker@v1` once.

---

## Alternative: Composite Action with `command` input

Simpler to build (no JS needed), but the user must change their command:

```yaml
- uses: your-org/ci-carbon-tracker@v1
  with:
    command: "docker build -t myapp ."   # wraps a single command
```

Good for tracking one specific step rather than the whole job.

---

## Recommended Approach for MVP: Composite with start/stop steps

No JS or Docker needed. Users add two steps — one before, one after:

```yaml
steps:
  - uses: your-org/ci-carbon-tracker/start@v1   # start tracking

  - name: Build Docker image
    run: docker build -t myapp .

  - name: Run tests
    run: pytest tests/

  - uses: your-org/ci-carbon-tracker/stop@v1    # stop + print report
    if: always()                                 # runs even if steps fail
```

Each `start` / `stop` is a sub-action in a subdirectory of the same repo.

---

## File Structure for This Repo

```
ci-carbon-tracker/           ← your GitHub repo
├── action.yml               ← main action (composite, wraps a single command)
├── start/
│   └── action.yml           ← start-tracking sub-action
├── stop/
│   └── action.yml           ← stop-tracking sub-action
├── tracker.py               ← Python script: starts codecarbon, writes state to file
├── report.py                ← Python script: reads state, stops tracker, prints report
├── pyproject.toml
└── README.md
```

---

## How the Python Side Works

`tracker.py` (called by `start/action.yml`):
- Starts `codecarbon` in the background as a subprocess
- Writes a PID file + start timestamp to a temp file (shared between steps via `$RUNNER_TEMP`)

`report.py` (called by `stop/action.yml`):
- Reads the PID/state file
- Signals the tracker process to stop
- Reads `emissions.csv` written by codecarbon
- Prints the energy/CO₂ summary

Sharing state between steps uses `$RUNNER_TEMP` — a directory GitHub Actions guarantees is shared across all steps in a job.

---

## Energy Measurement

Use `codecarbon` — it handles:
- Intel RAPL (real measurements on Linux runners)
- Fallback to CPU% × TDP estimate if RAPL unavailable
- CO₂ calculation from energy × grid carbon intensity

```bash
pip install codecarbon
```

---

## What the Report Looks Like (printed in Actions log)

```
=== CI Energy Report ===
Duration : 42.3 s
Energy   : 0.0312 Wh
CO₂      : 0.0148 g
Source   : RAPL (measured)
========================
```

Also optionally uploads `emissions.csv` as a workflow artifact.

---

## Implementation Steps

1. Create `tracker.py` — starts codecarbon EmissionsTracker, saves state to `$RUNNER_TEMP/tracker_state.json`
2. Create `report.py` — loads state, stops tracker, prints report
3. Create `start/action.yml` — composite action: installs codecarbon, runs `tracker.py`
4. Create `stop/action.yml` — composite action: runs `report.py`
5. Create top-level `action.yml` — composite action accepting a `command` input (single-step variant)
6. Create `pyproject.toml` with `codecarbon` dependency
7. Test with an example workflow in `.github/workflows/example.yml`
