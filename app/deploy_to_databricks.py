"""Deploy LakebaseOps Monitor app to Databricks Apps."""

import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
APP_DIR = ROOT  # The directory containing app.yaml, backend/, static/


def run(cmd: list[str], **kwargs):
    print(f"  > {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, **kwargs)
    if result.returncode != 0:
        print(f"  STDERR: {result.stderr.strip()}")
    return result


def main():
    parser = argparse.ArgumentParser(description="Deploy LakebaseOps to Databricks Apps")
    parser.add_argument("--app-name", default="lakebase-ops-monitor")
    parser.add_argument("--profile", default="DEFAULT")
    parser.add_argument("--hard-redeploy", action="store_true")
    args = parser.parse_args()

    profile = args.profile
    app_name = args.app_name

    # Step 1: Build frontend
    print("\n[1/4] Building frontend...")
    subprocess.run([sys.executable, str(ROOT / "build.py")], check=True)

    # Step 2: Create or update app
    print(f"\n[2/4] Creating/updating app '{app_name}'...")
    if args.hard_redeploy:
        print("  Hard redeploy: deleting existing app...")
        run(["databricks", "apps", "delete", app_name, "--profile", profile])
        time.sleep(5)

    create = run(["databricks", "apps", "create", app_name, "--profile", profile])
    if create.returncode != 0 and "already exists" not in create.stderr:
        print(f"  App may already exist, continuing...")

    # Step 3: Upload source
    print(f"\n[3/4] Uploading app source...")
    result = run([
        "databricks", "apps", "deploy", app_name,
        "--source-code-path", str(APP_DIR),
        "--profile", profile,
    ])
    if result.returncode != 0:
        print(f"Deploy failed: {result.stderr}")
        sys.exit(1)
    print(f"  Deploy initiated: {result.stdout.strip()}")

    # Step 4: Wait for deployment
    print(f"\n[4/4] Waiting for deployment...")
    for i in range(30):
        time.sleep(10)
        status = run(["databricks", "apps", "get", app_name, "--profile", profile])
        if "RUNNING" in status.stdout:
            print(f"\n  App is RUNNING!")
            # Extract URL
            for line in status.stdout.splitlines():
                if "url" in line.lower():
                    print(f"  {line.strip()}")
            break
        print(f"  Waiting... ({(i+1)*10}s)")
    else:
        print("  Timeout — check app status manually")

    print(f"\nDone! App: {app_name}")


if __name__ == "__main__":
    main()
