import csv
import json
import os
import time
import argparse
from pathlib import Path


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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dir",
        default=os.environ.get("RUNNER_TEMP", "/tmp"),
        help="Directory where tracker.py wrote its state (default: $RUNNER_TEMP or /tmp)",
    )
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

    rows = list(csv.DictReader(csv_file.open()))
    if not rows:
        print("[report] ERROR: emissions.csv is empty")
        raise SystemExit(1)

    metrics = json.loads(metrics_file.read_text())
    print_report(rows[-1], metrics)


if __name__ == "__main__":
    main()
