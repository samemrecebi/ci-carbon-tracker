# A workaround for concurrent runs issue

import argparse
import json
import subprocess
import sys
import time


def get_older_in_progress(repo: str, this_run_id: int) -> list[int]:
    """Return IDs of in-progress runs with a lower ID than ours."""
    try:
        result = subprocess.run(
            [
                "gh",
                "api",
                f"repos/{repo}/actions/runs?status=in_progress",
                "--jq",
                f"[.workflow_runs[] | select(.id < {this_run_id}) | .id]",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(result.stdout.strip() or "[]")
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        return []


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--run-id", type=int, required=True)
    parser.add_argument("--max-wait", type=int, default=600)
    parser.add_argument("--poll-interval", type=int, default=15)
    args = parser.parse_args()

    older = get_older_in_progress(args.repo, args.run_id)
    if not older:
        print("[wait] no older concurrent runs — skipping")
        sys.exit(0)

    print(f"[wait] waiting for {len(older)} older run(s): {older}")

    waited = 0
    while waited < args.max_wait:
        time.sleep(args.poll_interval)
        waited += args.poll_interval

        still = get_older_in_progress(args.repo, args.run_id)
        if not still:
            print(f"[wait] all older runs finished after {waited}s")
            sys.exit(0)

        print(
            f"[wait] still waiting on {len(still)} run(s)... ({waited}s / {args.max_wait}s)"
        )

    print(f"[wait] timed out after {args.max_wait}s — proceeding with available data")


if __name__ == "__main__":
    main()
