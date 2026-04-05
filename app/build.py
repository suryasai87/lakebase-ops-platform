"""Build frontend and copy to static/ for serving by FastAPI."""

import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FRONTEND = ROOT / "frontend"
DIST = FRONTEND / "dist"
STATIC = ROOT / "static"


def main():
    print("=== Installing frontend dependencies ===")
    subprocess.run(["bun", "install"], cwd=FRONTEND, check=True)

    print("=== Building frontend ===")
    subprocess.run(["bun", "run", "build"], cwd=FRONTEND, check=True)

    print("=== Copying dist -> static ===")
    if STATIC.exists():
        shutil.rmtree(STATIC)
    shutil.copytree(DIST, STATIC)

    print(f"Build complete: {STATIC}")


if __name__ == "__main__":
    main()
