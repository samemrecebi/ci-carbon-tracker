# Wait for older runs of the same workflow to finish before downloading artifacts

import argparse
import json
import subprocess
import sys
import time


def get_older_in_progress(repo: str, this_run_id: int, workflow_name: str) -> list[int]:
    """Return IDs of in-progress runs of the same workflow with a lower ID than ours."""
    try:
        jq_filter = (
            f'[.workflow_runs[] | select(.id < {this_run_id} and .name == "{workflow_name}") | .id]'
        )
        result = subprocess.run(
            [
                "gh",
                "api",
                f"repos/{repo}/actions/runs?status=in_progress",
                "--jq",
                jq_filter,
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
    parser.add_argument("--workflow-name", default="")
    parser.add_argument("--max-wait", type=int, default=600)
    parser.add_argument("--poll-interval", type=int, default=15)
    args = parser.parse_args()

    workflow_name = args.workflow_name
    print(f"[wait] this run: {args.run_id}, workflow: '{workflow_name}'")

    older = get_older_in_progress(args.repo, args.run_id, workflow_name)
    if not older:
        print("[wait] no older concurrent runs — skipping")
        sys.exit(0)

    print(f"[wait] waiting for {len(older)} older run(s) of '{workflow_name}': {older}")

    waited = 0
    while waited < args.max_wait:
        time.sleep(args.poll_interval)
        waited += args.poll_interval

        still = get_older_in_progress(args.repo, args.run_id, workflow_name)
        if not still:
            print(f"[wait] all older runs finished after {waited}s")
            sys.exit(0)

        print(
            f"[wait] still waiting on {len(still)} run(s)... ({waited}s / {args.max_wait}s)"
        )

    print(f"[wait] timed out after {args.max_wait}s — proceeding with available data")


if __name__ == "__main__":
    main()
