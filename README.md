# CI Carbon Tracker

Simple local tracker to measure runtime energy and CO₂ emissions for Python code using `codecarbon`.

## Files

- `tracker.py`: starts emissions + system metrics tracking
- `report.py`: stops tracking and prints the final report
- `hello_world.py`: sample Python workload

## Prerequisites (Windows)

1. Install Python 3.12+
2. Install `uv` (choose one):

```powershell
winget install --id=astral-sh.uv -e
```

or

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Verify:

```powershell
uv --version
```

## Setup

From the project root:

```powershell
uv sync
```

## Run Hello World with Tracking

Run these commands in PowerShell from the project root:

```powershell
$stateDir = Join-Path $PWD ".emissions-hello"    #  Create state directory "emissions-hello" for tracker outputs 
New-Item -ItemType Directory -Force -Path $stateDir | Out-Null  # Optional: Ensure the directory exists
$tracker = Start-Process -FilePath "uv" -ArgumentList @("run","python","tracker.py","--dir",$stateDir) -PassThru # Start the tracker in the background
uv run python hello_world.py # Run the sample workload while tracking is active
uv run python report.py --dir $stateDir # Report 
```

## Output

After `report.py` runs, you will see:

- Terminal summary (`CI Energy Report`) with duration, energy, and CO₂
- `.emissions-hello/emissions.csv` for emissions details
- `.emissions-hello/tracker_metrics.json` for CPU, memory, disk, and network metrics

## Troubleshooting

- If `uv` is not recognized, restart PowerShell and run `uv --version` again.
- If emissions look near zero, run a longer/heavier workload so sampling has more data.
