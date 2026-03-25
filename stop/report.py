import csv
import datetime
import json
import os
import time
import argparse
from pathlib import Path
from typing import Any


def wait_for_file(path: Path, timeout: int = 15) -> bool:
    """Wait until a file exists and is non-empty."""
    for _ in range(timeout):
        if path.exists() and path.stat().st_size > 0:
            return True
        time.sleep(1)
    return False


def print_report(energy_row: dict, metrics: dict):
    duration = float(energy_row["duration"])
    energy_kwh = float(energy_row["energy_consumed"])
    co2_kg = float(energy_row["emissions"])
    cpu_energy_kwh = float(energy_row.get("cpu_energy", 0))
    ram_energy_kwh = float(energy_row.get("ram_energy", 0))
    energy_source = energy_row.get("energy_consumed_source", "estimated")

    print()
    print("=== CI Energy Report ===")
    print(f"  Duration       : {duration:.2f} s")
    print(f"  Energy         : {energy_kwh * 1000:.4f} Wh  (source: {energy_source})")
    print(f"    CPU energy   : {cpu_energy_kwh * 1000:.4f} Wh")
    print(f"    RAM energy   : {ram_energy_kwh * 1000:.4f} Wh")
    print(f"  CO\u2082           : {co2_kg * 1000:.4f} g")
    print()
    print(f"  CPU avg/peak   : {metrics['cpu_avg']}% / {metrics['cpu_peak']}%")
    print(f"  Memory avg     : {metrics['mem_avg_pct']}%  (peak: {metrics['mem_peak_mb']} MB)")
    print(f"  Disk read      : {metrics['disk_read_mb']} MB")
    print(f"  Disk write     : {metrics['disk_write_mb']} MB")
    print(f"  Network sent   : {metrics['net_sent_mb']} MB")
    print(f"  Network recv   : {metrics['net_recv_mb']} MB")
    print(f"  Samples        : {metrics['sample_count']}")
    print("========================")
    print()
    suggestions = generate_suggestions(energy_row, metrics)
    if suggestions:
        print("  (LIMIT REACHED) Apply these suggestions to Reduce CO2 Impact")
        for suggestion in suggestions:
            print(f"   - {suggestion}")
        print()

def generate_suggestions(energy_row: dict, metrics: dict) -> list[str]:
    suggestions = []

    energy_wh = float(energy_row["energy_consumed"]) * 1000

    # Example limits - need to be adjusted based on typical values for the repo and workflow type
    ENERGY_LIMIT_WH = 0.15

    if energy_wh > ENERGY_LIMIT_WH:
        suggestions = [
            "Reduce runtime / space complexity of algorithms",
            "Use caching / lazy loading",
            "Remove unused libraries / frameworks / imports",
            "Stop over-engineering (unnecessary infrastructure or design patterns)",
            "Only trigger the pipeline for the changed code, this can be easier in a microservice architecture than in a monolith",
            "Avoid running unnecessary tests (focus on impacted areas)",
            "Reuse build artifacts instead of rebuilding everything",
            "Use lighter base images / dependencies where possible"
        ]

    return suggestions

def compute_history_stats(history_path: Path, current_workflow: str) -> dict:
    """Read history CSV and compute per-workflow and repo-wide stats."""
    stats = {
        "repo_total_runs": 0,
        "repo_total_energy_wh": 0.0,
        "repo_total_co2_g": 0.0,
        "repo_total_duration_s": 0.0,
        "workflow_total_runs": 0,
        "workflow_total_energy_wh": 0.0,
        "workflow_total_co2_g": 0.0,
        "workflow_total_duration_s": 0.0,
        "workflow_name": current_workflow,
        "workflows": {},
    }

    if not history_path.exists() or history_path.stat().st_size == 0:
        return stats

    with open(history_path, newline="") as f:
        rows = list(csv.DictReader(f))

    for row in rows:
        try:
            energy = float(row.get("energy_wh", 0))
            co2 = float(row.get("co2_g", 0))
            duration = float(row.get("duration_s", 0))
        except (ValueError, TypeError):
            continue  # skip malformed rows (e.g. old CSV format)
        wf = row.get("workflow", "")

        stats["repo_total_runs"] += 1
        stats["repo_total_energy_wh"] += energy
        stats["repo_total_co2_g"] += co2
        stats["repo_total_duration_s"] += duration

        if wf not in stats["workflows"]:
            stats["workflows"][wf] = {"runs": 0, "energy_wh": 0.0, "co2_g": 0.0, "duration_s": 0.0}
        stats["workflows"][wf]["runs"] += 1
        stats["workflows"][wf]["energy_wh"] += energy
        stats["workflows"][wf]["co2_g"] += co2
        stats["workflows"][wf]["duration_s"] += duration

        if wf == current_workflow:
            stats["workflow_total_runs"] += 1
            stats["workflow_total_energy_wh"] += energy
            stats["workflow_total_co2_g"] += co2
            stats["workflow_total_duration_s"] += duration

    return stats


def generate_markdown(energy_row: dict, metrics: dict, stats: dict) -> str:
    duration = float(energy_row["duration"])
    energy_kwh = float(energy_row["energy_consumed"])
    co2_kg = float(energy_row["emissions"])
    cpu_energy_kwh = float(energy_row.get("cpu_energy", 0))
    ram_energy_kwh = float(energy_row.get("ram_energy", 0))
    source = energy_row.get("energy_consumed_source", "estimated")

    md = f"""## CI Carbon Report

### This Run

| Metric | Value |
|--------|-------|
| Duration | {duration:.2f} s |
| Energy | {energy_kwh * 1000:.4f} Wh ({source}) |
| CPU energy | {cpu_energy_kwh * 1000:.4f} Wh |
| RAM energy | {ram_energy_kwh * 1000:.4f} Wh |
| CO2 | {co2_kg * 1000:.4f} g |
| CPU avg / peak | {metrics['cpu_avg']}% / {metrics['cpu_peak']}% |
| Memory avg (peak) | {metrics['mem_avg_pct']}% ({metrics['mem_peak_mb']} MB) |
| Disk R / W | {metrics['disk_read_mb']} / {metrics['disk_write_mb']} MB |
| Net sent / recv | {metrics['net_sent_mb']} / {metrics['net_recv_mb']} MB |

### Workflow: {stats['workflow_name']}

| Metric | Value |
|--------|-------|
| Total runs | {stats['workflow_total_runs']} |
| Total energy | {stats['workflow_total_energy_wh']:.4f} Wh |
| Total CO2 | {stats['workflow_total_co2_g']:.4f} g |
| Total duration | {stats['workflow_total_duration_s']:.1f} s |

### Repository Totals (all workflows)

| Metric | Value |
|--------|-------|
| Total runs | {stats['repo_total_runs']} |
| Total energy | {stats['repo_total_energy_wh']:.4f} Wh |
| Total CO2 | {stats['repo_total_co2_g']:.4f} g |
| Total duration | {stats['repo_total_duration_s']:.1f} s |
"""

    if len(stats["workflows"]) > 1:
        md += "\n### Per-Workflow Breakdown\n\n"
        md += "| Workflow | Runs | Energy (Wh) | CO2 (g) |\n"
        md += "|----------|------|-------------|--------|\n"
        for wf_name, wf_stats in sorted(stats["workflows"].items()):
            md += f"| {wf_name} | {wf_stats['runs']} | {wf_stats['energy_wh']:.4f} | {wf_stats['co2_g']:.4f} |\n"

    suggestions = generate_suggestions(energy_row, metrics)
    if suggestions:
        md += "\n### (LIMIT REACHED) Apply these suggestions to Reduce CO2 Impact\n\n"
        for suggestion in suggestions:
            md += f"- {suggestion}\n"
    
    return md


HISTORY_FIELDS = [
    "timestamp", "workflow", "run_number", "pr_number", "branch",
    "duration_s", "energy_wh", "co2_g", "cpu_avg", "cpu_peak",
    "mem_avg_pct", "mem_peak_mb", "disk_read_mb", "disk_write_mb",
    "net_sent_mb", "net_recv_mb",
]


def append_history(history_path: Path, energy_row: dict, metrics: dict):
    file_exists = history_path.exists() and history_path.stat().st_size > 0

    entry = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "workflow": os.environ.get("WORKFLOW_NAME", ""),
        "run_number": os.environ.get("RUN_NUMBER", ""),
        "pr_number": os.environ.get("PR_NUMBER", ""),
        "branch": os.environ.get("BRANCH_NAME", ""),
        "duration_s": round(float(energy_row["duration"]), 2),
        "energy_wh": round(float(energy_row["energy_consumed"]) * 1000, 4),
        "co2_g": round(float(energy_row["emissions"]) * 1000, 4),
        "cpu_avg": metrics["cpu_avg"],
        "cpu_peak": metrics["cpu_peak"],
        "mem_avg_pct": metrics["mem_avg_pct"],
        "mem_peak_mb": metrics["mem_peak_mb"],
        "disk_read_mb": metrics["disk_read_mb"],
        "disk_write_mb": metrics["disk_write_mb"],
        "net_sent_mb": metrics["net_sent_mb"],
        "net_recv_mb": metrics["net_recv_mb"],
    }

    with open(history_path, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=HISTORY_FIELDS)
        if not file_exists:
            writer.writeheader()
        writer.writerow(entry)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dir",
        default=os.environ.get("RUNNER_TEMP", "/tmp"),
        help="Directory where tracker.py wrote its state (default: $RUNNER_TEMP or /tmp)",
    )
    parser.add_argument("--markdown", default=None, help="Path to write markdown report")
    parser.add_argument("--history", default=None, help="Path to CSV history file to append to")
    args = parser.parse_args()

    state_dir = Path(args.dir)
    pid_file = state_dir / "tracker.pid"
    stop_file = state_dir / "tracker.stop"
    csv_file = state_dir / "emissions.csv"
    metrics_file = state_dir / "tracker_metrics.json"

    if not pid_file.exists():
        print("[report] ERROR: tracker.pid not found — was tracker.py started?")
        raise SystemExit(1)

    print("[report] signalling tracker to stop...")
    stop_file.write_text("stop")

    # wait for tracker to remove the pid file (signals clean exit)
    for _ in range(15):
        if not pid_file.exists():
            break
        time.sleep(1)

    if not wait_for_file(csv_file):
        print("[report] ERROR: emissions.csv was not written within timeout")
        raise SystemExit(1)

    if not wait_for_file(metrics_file):
        print("[report] ERROR: tracker_metrics.json was not written within timeout")
        raise SystemExit(1)

    rows = list[dict[str | Any, str | Any]](csv.DictReader(csv_file.open()))
    if not rows:
        print("[report] ERROR: emissions.csv is empty")
        raise SystemExit(1)

    metrics = json.loads(metrics_file.read_text())
    print_report(rows[-1], metrics)

    if args.history:
        append_history(Path(args.history), rows[-1], metrics)
        print(f"[report] history appended to {args.history}")

    if args.markdown:
        workflow_name = os.environ.get("WORKFLOW_NAME", "unknown")
        history_path = Path(args.history) if args.history else None
        stats = compute_history_stats(history_path, workflow_name) if history_path else {
            "repo_total_runs": 0, "repo_total_energy_wh": 0, "repo_total_co2_g": 0,
            "repo_total_duration_s": 0, "workflow_total_runs": 0, "workflow_total_energy_wh": 0,
            "workflow_total_co2_g": 0, "workflow_total_duration_s": 0,
            "workflow_name": workflow_name, "workflows": {},
        }
        md = generate_markdown(rows[-1], metrics, stats)
        Path(args.markdown).write_text(md)
        print(f"[report] markdown written to {args.markdown}")


if __name__ == "__main__":
    main()
