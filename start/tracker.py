import json
import os
import tempfile
import time
import argparse
from pathlib import Path

import psutil
from codecarbon import EmissionsTracker


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dir",
        default=os.environ.get("RUNNER_TEMP", tempfile.gettempdir()),
        help="Directory to write state file and emissions CSV (default: $RUNNER_TEMP or system temp)",
    )
    parser.add_argument(
        "--config",
        default=os.environ.get("CONFIG_FILE", ".cicarbon.json"),
        help="Path to .cicarbon.json config file",
    )
    args = parser.parse_args()

    state_dir = Path(args.dir)
    state_dir.mkdir(parents=True, exist_ok=True)

    stop_file = state_dir / "tracker.stop"
    pid_file = state_dir / "tracker.pid"
    metrics_file = state_dir / "tracker_metrics.json"

    # clean up any leftover stop file from a previous run
    stop_file.unlink(missing_ok=True)

    # Load config file
    config_path = Path(args.config)
    config = {}
    if config_path.exists():
        config = json.loads(config_path.read_text())
        print(f"[tracker] loaded config from {config_path}", flush=True)
    cc_config = config.get("codecarbon", {})

    tracker_kwargs = dict(
        output_dir=str(state_dir),
        save_to_file=True,
        measure_power_secs=1,
        log_level="error",
    )

    electricitymaps_token = os.environ.get("ELECTRICITYMAPS_TOKEN", "")
    if electricitymaps_token:
        tracker_kwargs["electricitymaps_api_token"] = electricitymaps_token
        print("[tracker] using Electricity Maps API for carbon intensity", flush=True)

    tracking_mode = os.environ.get("TRACKING_MODE", "machine")
    tracker_kwargs["tracking_mode"] = tracking_mode
    print(f"[tracker] tracking mode: {tracking_mode}", flush=True)

    if cc_config.get("pue") is not None:
        tracker_kwargs["pue"] = float(cc_config["pue"])
        print(f"[tracker] PUE: {tracker_kwargs['pue']}", flush=True)

    if cc_config.get("force_cpu_power") is not None:
        tracker_kwargs["force_cpu_power"] = int(cc_config["force_cpu_power"])
        print(f"[tracker] forced CPU power: {tracker_kwargs['force_cpu_power']}W", flush=True)

    tracker = EmissionsTracker(**tracker_kwargs)
    tracker.start()
    pid_file.write_text(str(os.getpid()))
    print(f"[tracker] started (PID {os.getpid()}), output dir: {state_dir}", flush=True)

    # initialise psutil cpu_percent baseline (first call always returns 0.0)
    psutil.cpu_percent()
    disk_start = psutil.disk_io_counters()  # can be None on some macOS configs
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

    if disk_start and disk_end:
        disk_read_mb = round((disk_end.read_bytes - disk_start.read_bytes) / 1024**2, 2)
        disk_write_mb = round((disk_end.write_bytes - disk_start.write_bytes) / 1024**2, 2)
    else:
        disk_read_mb = 0
        disk_write_mb = 0

    metrics = {
        "cpu_avg": round(sum(cpu_samples) / len(cpu_samples), 2) if cpu_samples else 0,
        "cpu_peak": round(max(cpu_samples), 2) if cpu_samples else 0,
        "mem_avg_pct": round(sum(mem_samples) / len(mem_samples), 2)
        if mem_samples
        else 0,
        "mem_peak_pct": round(max(mem_samples), 2) if mem_samples else 0,
        "mem_peak_mb": round(max(mem_used_samples), 1) if mem_used_samples else 0,
        "disk_read_mb": disk_read_mb,
        "disk_write_mb": disk_write_mb,
        "net_sent_mb": round((net_end.bytes_sent - net_start.bytes_sent) / 1024**2, 2),
        "net_recv_mb": round((net_end.bytes_recv - net_start.bytes_recv) / 1024**2, 2),
        "sample_count": len(cpu_samples),
    }
    metrics_file.write_text(json.dumps(metrics, indent=2))

    stop_file.unlink(missing_ok=True)
    pid_file.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
