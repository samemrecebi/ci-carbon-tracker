import json
import os
import time
import argparse
from pathlib import Path

import psutil
from codecarbon import EmissionsTracker


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dir",
        default=os.environ.get("RUNNER_TEMP", "/tmp"),
        help="Directory to write state file and emissions CSV (default: $RUNNER_TEMP or /tmp)",
    )
    args = parser.parse_args()

    state_dir = Path(args.dir)
    state_dir.mkdir(parents=True, exist_ok=True)

    stop_file = state_dir / "tracker.stop"
    pid_file = state_dir / "tracker.pid"
    metrics_file = state_dir / "tracker_metrics.json"

    # clean up any leftover stop file from a previous run
    stop_file.unlink(missing_ok=True)

    tracker = EmissionsTracker(
        output_dir=str(state_dir),
        save_to_file=True,
        measure_power_secs=1,
        log_level="error",
    )
    tracker.start()
    pid_file.write_text(str(os.getpid()))
    print(f"[tracker] started (PID {os.getpid()}), output dir: {state_dir}", flush=True)

    # initialise psutil cpu_percent baseline (first call always returns 0.0)
    psutil.cpu_percent()
    disk_start = psutil.disk_io_counters()
    net_start = psutil.net_io_counters()

    cpu_samples: list[float] = []
    mem_samples: list[float] = []
    mem_used_samples: list[float] = []

    while not stop_file.exists():
        time.sleep(1)
        cpu_samples.append(psutil.cpu_percent())
        vm = psutil.virtual_memory()
        mem_samples.append(vm.percent)
        mem_used_samples.append(vm.used / 1024**2)  # MB

    tracker.stop()
    print("[tracker] stopped, emissions.csv written", flush=True)

    disk_end = psutil.disk_io_counters()
    net_end = psutil.net_io_counters()

    metrics = {
        "cpu_avg": round(sum(cpu_samples) / len(cpu_samples), 2) if cpu_samples else 0,
        "cpu_peak": round(max(cpu_samples), 2) if cpu_samples else 0,
        "mem_avg_pct": round(sum(mem_samples) / len(mem_samples), 2)
        if mem_samples
        else 0,
        "mem_peak_pct": round(max(mem_samples), 2) if mem_samples else 0,
        "mem_peak_mb": round(max(mem_used_samples), 1) if mem_used_samples else 0,
        "disk_read_mb": round(
            (disk_end.read_bytes - disk_start.read_bytes) / 1024**2, 2
        ),
        "disk_write_mb": round(
            (disk_end.write_bytes - disk_start.write_bytes) / 1024**2, 2
        ),
        "net_sent_mb": round((net_end.bytes_sent - net_start.bytes_sent) / 1024**2, 2),
        "net_recv_mb": round((net_end.bytes_recv - net_start.bytes_recv) / 1024**2, 2),
        "sample_count": len(cpu_samples),
    }
    metrics_file.write_text(json.dumps(metrics, indent=2))

    stop_file.unlink(missing_ok=True)
    pid_file.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
