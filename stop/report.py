import csv
import datetime
import json
import os
import tempfile
import time
import argparse
from pathlib import Path
from string import Template
from typing import Any

TEMPLATES_DIR = Path(__file__).parent / "templates"

DEFAULT_CONFIG = {
    "thresholds": {
        "energy_wh": 0.15,
        "co2_g": None,
        "duration_s": None,
    },
    "notifications": {
        "create_issue": True,
        "issue_label": "carbon-alert",
        "pr_comment": True,
    },
}

HISTORY_FIELDS = [
    "timestamp",
    "workflow",
    "run_number",
    "pr_number",
    "branch",
    "duration_s",
    "energy_wh",
    "co2_g",
    "cpu_avg",
    "cpu_peak",
    "mem_avg_pct",
    "mem_peak_mb",
    "disk_read_mb",
    "disk_write_mb",
    "net_sent_mb",
    "net_recv_mb",
]


def load_config(config_path: Path | None = None) -> dict:
    """Load the .cicarbon.json configuration file."""
    config = json.loads(json.dumps(DEFAULT_CONFIG))  # deep copy
    if config_path and config_path.exists():
        user_cfg = json.loads(config_path.read_text())
        for section, values in user_cfg.items():
            if section in config and isinstance(values, dict):
                config[section].update(values)
            else:
                config[section] = values
        print(f"[report] loaded config from {config_path}")
    else:
        print("[report] no .cicarbon.json found — using defaults")
    return config


def safe_float(value, default: float = 0.0) -> float:
    """Convert a value to float, returning default if empty or invalid."""
    try:
        return float(value) if value != "" else default
    except (TypeError, ValueError):
        return default


def wait_for_file(path: Path, timeout: int = 15) -> bool:
    """Wait until a file exists and is non-empty."""
    for _ in range(timeout):
        if path.exists() and path.stat().st_size > 0:
            return True
        time.sleep(1)
    return False


def print_report(energy_row: dict, metrics: dict, config: dict):
    """Print the report on the terminal. This is mainly used when testing locally."""
    duration = safe_float(energy_row["duration"])
    energy_kwh = safe_float(energy_row["energy_consumed"])
    co2_kg = safe_float(energy_row["emissions"])
    cpu_energy_kwh = safe_float(energy_row.get("cpu_energy", 0))
    ram_energy_kwh = safe_float(energy_row.get("ram_energy", 0))
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
    print(
        f"  Memory avg     : {metrics['mem_avg_pct']}%  (peak: {metrics['mem_peak_mb']} MB)"
    )
    print(f"  Disk read      : {metrics['disk_read_mb']} MB")
    print(f"  Disk write     : {metrics['disk_write_mb']} MB")
    print(f"  Network sent   : {metrics['net_sent_mb']} MB")
    print(f"  Network recv   : {metrics['net_recv_mb']} MB")
    print(f"  Samples        : {metrics['sample_count']}")
    print("========================")
    print()
    if is_threshold_breached(energy_row, config):
        print("  (LIMIT REACHED) Apply these suggestions to Reduce CO2 Impact")
        print()


def check_thresholds(energy_row: dict, config: dict) -> list[str]:
    """Check if the predefined thresholds are broken."""
    thresholds = config.get("thresholds", {})
    breached = []

    energy_wh = safe_float(energy_row["energy_consumed"]) * 1000
    co2_g = safe_float(energy_row["emissions"]) * 1000
    duration_s = safe_float(energy_row["duration"])

    energy_limit = thresholds.get("energy_wh")
    if energy_limit is not None and energy_wh > energy_limit:
        breached.append(f"energy ({energy_wh:.4f} Wh > {energy_limit} Wh)")

    co2_limit = thresholds.get("co2_g")
    if co2_limit is not None and co2_g > co2_limit:
        breached.append(f"CO2 ({co2_g:.4f} g > {co2_limit} g)")

    duration_limit = thresholds.get("duration_s")
    if duration_limit is not None and duration_s > duration_limit:
        breached.append(f"duration ({duration_s:.1f} s > {duration_limit} s)")

    return breached


def is_threshold_breached(energy_row: dict, config: dict) -> bool:
    """Check if any threshold was breached."""
    return len(check_thresholds(energy_row, config)) > 0


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
            stats["workflows"][wf] = {
                "runs": 0,
                "energy_wh": 0.0,
                "co2_g": 0.0,
                "duration_s": 0.0,
            }
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


def load_template(name: str, templates_dir: Path | None = None) -> Template:
    """Load a template file by name from the templates directory."""
    tpl_dir = templates_dir or TEMPLATES_DIR
    return Template((tpl_dir / name).read_text())


def generate_markdown(
    energy_row: dict, metrics: dict, stats: dict, config: dict,
) -> str:
    """Generate the markdown report by rendering templates."""
    tpl_dir = TEMPLATES_DIR

    duration = safe_float(energy_row["duration"])
    energy_kwh = safe_float(energy_row["energy_consumed"])
    co2_kg = safe_float(energy_row["emissions"])

    values = {
        "duration_s": f"{duration:.2f}",
        "energy_wh": f"{energy_kwh * 1000:.4f}",
        "energy_source": energy_row.get("energy_consumed_source", "estimated"),
        "cpu_energy_wh": f"{safe_float(energy_row.get('cpu_energy', 0)) * 1000:.4f}",
        "ram_energy_wh": f"{safe_float(energy_row.get('ram_energy', 0)) * 1000:.4f}",
        "co2_g": f"{co2_kg * 1000:.4f}",
        "cpu_avg": metrics["cpu_avg"],
        "cpu_peak": metrics["cpu_peak"],
        "mem_avg_pct": metrics["mem_avg_pct"],
        "mem_peak_mb": metrics["mem_peak_mb"],
        "disk_read_mb": metrics["disk_read_mb"],
        "disk_write_mb": metrics["disk_write_mb"],
        "net_sent_mb": metrics["net_sent_mb"],
        "net_recv_mb": metrics["net_recv_mb"],
        "workflow_name": stats["workflow_name"],
        "workflow_total_runs": stats["workflow_total_runs"],
        "workflow_total_energy_wh": f"{stats['workflow_total_energy_wh']:.4f}",
        "workflow_total_co2_g": f"{stats['workflow_total_co2_g']:.4f}",
        "workflow_total_duration_s": f"{stats['workflow_total_duration_s']:.1f}",
        "repo_total_runs": stats["repo_total_runs"],
        "repo_total_energy_wh": f"{stats['repo_total_energy_wh']:.4f}",
        "repo_total_co2_g": f"{stats['repo_total_co2_g']:.4f}",
        "repo_total_duration_s": f"{stats['repo_total_duration_s']:.1f}",
    }

    md = load_template("report.md", tpl_dir).safe_substitute(values)

    if len(stats["workflows"]) > 1:
        row_tpl = load_template("workflow-row.md", tpl_dir)
        rows = ""
        for wf_name, wf_stats in sorted(stats["workflows"].items()):
            rows += row_tpl.safe_substitute(
                name=wf_name,
                runs=wf_stats["runs"],
                energy_wh=f"{wf_stats['energy_wh']:.4f}",
                co2_g=f"{wf_stats['co2_g']:.4f}",
            )
        md += "\n" + load_template("workflow-breakdown.md", tpl_dir).safe_substitute(rows=rows)

    if is_threshold_breached(energy_row, config):
        md += "\n" + load_template("suggestions.md", tpl_dir).substitute()

    return md


def build_history_entry(energy_row: dict, metrics: dict) -> dict:
    """Create a history entry."""
    return {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "workflow": os.environ.get("WORKFLOW_NAME", ""),
        "run_number": os.environ.get("RUN_NUMBER", ""),
        "pr_number": os.environ.get("PR_NUMBER", ""),
        "branch": os.environ.get("BRANCH_NAME", ""),
        "duration_s": round(safe_float(energy_row["duration"]), 2),
        "energy_wh": round(safe_float(energy_row["energy_consumed"]) * 1000, 4),
        "co2_g": round(safe_float(energy_row["emissions"]) * 1000, 4),
        "cpu_avg": metrics["cpu_avg"],
        "cpu_peak": metrics["cpu_peak"],
        "mem_avg_pct": metrics["mem_avg_pct"],
        "mem_peak_mb": metrics["mem_peak_mb"],
        "disk_read_mb": metrics["disk_read_mb"],
        "disk_write_mb": metrics["disk_write_mb"],
        "net_sent_mb": metrics["net_sent_mb"],
        "net_recv_mb": metrics["net_recv_mb"],
    }


def append_history(history_path: Path, energy_row: dict, metrics: dict):
    """Append the history file with the entries from the current run."""
    file_exists = history_path.exists() and history_path.stat().st_size > 0
    entry = build_history_entry(energy_row, metrics)

    with open(history_path, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=HISTORY_FIELDS)
        if not file_exists:
            writer.writeheader()
        writer.writerow(entry)


def write_run_entry(entry_path: Path, energy_row: dict, metrics: dict):
    """Write a single-row CSV with just this run's data (for per-run artifacts)."""
    entry = build_history_entry(energy_row, metrics)
    with open(entry_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=HISTORY_FIELDS)
        writer.writeheader()
        writer.writerow(entry)


def rebuild_history_from_artifacts(runs_dir: Path, history_path: Path):
    """Concatenate all per-run CSV artifacts into a single history file."""
    csv_files = sorted(runs_dir.rglob("*.csv"))
    if not csv_files:
        print("[history] no previous runs found — first run")
        return

    with open(history_path, "w", newline="") as out:
        header_written = False
        for f in csv_files:
            with open(f, newline="") as inp:
                reader = csv.reader(inp)
                header = next(reader, None)
                if not header_written and header:
                    out.write(",".join(header) + "\n")
                    header_written = True
                for row in reader:
                    out.write(",".join(row) + "\n")

    row_count = sum(1 for _ in open(history_path)) - 1
    print(f"[history] rebuilt history from {row_count} previous runs")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dir",
        default=os.environ.get("RUNNER_TEMP", tempfile.gettempdir()),
        help="Directory where tracker.py wrote its state (default: $RUNNER_TEMP or system temp)",
    )
    parser.add_argument(
        "--markdown", default=None, help="Path to write markdown report"
    )
    parser.add_argument(
        "--history", default=None, help="Path to CSV history file to append to"
    )
    parser.add_argument(
        "--config",
        default=".cicarbon.json",
        help="Path to config file (default: .cicarbon.json)",
    )
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="Skip tracker stop; just regenerate the markdown from existing data",
    )
    parser.add_argument(
        "--rebuild-history",
        default=None,
        help="Path to directory of per-run CSV artifacts to rebuild history from",
    )
    args = parser.parse_args()

    state_dir = Path(args.dir)

    # If --rebuild-history is given, merge artifacts into the history file and exit
    if args.rebuild_history:
        if not args.history:
            print("[report] ERROR: --rebuild-history requires --history")
            raise SystemExit(1)
        rebuild_history_from_artifacts(Path(args.rebuild_history), Path(args.history))
        return

    csv_file = state_dir / "emissions.csv"
    metrics_file = state_dir / "tracker_metrics.json"

    if not args.report_only:
        pid_file = state_dir / "tracker.pid"
        stop_file = state_dir / "tracker.stop"

        if not pid_file.exists():
            print("[report] ERROR: tracker.pid not found — was tracker.py started?")
            raise SystemExit(1)

        print("[report] signalling tracker to stop...")
        stop_file.write_text("stop")

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

    config = load_config(Path(args.config))
    metrics = json.loads(metrics_file.read_text())

    if not args.report_only:
        print_report(rows[-1], metrics, config)

        # Write individual run entry (for per-run artifact uploads)
        run_entry_file = state_dir / "carbon-run-entry.csv"
        write_run_entry(run_entry_file, rows[-1], metrics)
        print(f"[report] individual run entry written to {run_entry_file}")

    if args.history:
        if not args.report_only:
            append_history(Path(args.history), rows[-1], metrics)
            print(f"[report] history appended to {args.history}")

    breached = check_thresholds(rows[-1], config)

    threshold_file = state_dir / "threshold_exceeded"
    if breached:
        threshold_file.write_text("true")
        if not args.report_only:
            print(f"[report] thresholds exceeded: {', '.join(breached)}")
    else:
        threshold_file.write_text("false")

    if args.markdown:
        workflow_name = os.environ.get("WORKFLOW_NAME", "unknown")
        history_path = Path(args.history) if args.history else None
        stats = (
            compute_history_stats(history_path, workflow_name)
            if history_path
            else {
                "repo_total_runs": 0,
                "repo_total_energy_wh": 0,
                "repo_total_co2_g": 0,
                "repo_total_duration_s": 0,
                "workflow_total_runs": 0,
                "workflow_total_energy_wh": 0,
                "workflow_total_co2_g": 0,
                "workflow_total_duration_s": 0,
                "workflow_name": workflow_name,
                "workflows": {},
            }
        )
        md = generate_markdown(rows[-1], metrics, stats, config)
        Path(args.markdown).write_text(md)
        print(f"[report] markdown written to {args.markdown}")


if __name__ == "__main__":
    main()
