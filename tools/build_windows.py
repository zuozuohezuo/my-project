"""Build the local Windows app with the exact uv environment and bundled content."""

import argparse
import os
import re
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--console", action="store_true", help="build with a console for startup diagnosis")
    parser.add_argument("--name", default="MingImperialDesk", help="directory/executable name for a separate playable build")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.name):
        parser.error("Build name may contain only letters, digits, underscores, and hyphens.")
    if sys.platform != "win32":
        raise SystemExit("Run this build script on Windows.")
    required = ["data", "assets", "docs", "THIRD_PARTY_NOTICES.md", "README.md",
                "王朝模拟_框架草案.md", "王朝模拟_技术方案.md"]
    missing = [item for item in required if not (ROOT / item).exists()]
    if missing:
        raise SystemExit("Missing build inputs: " + ", ".join(missing))
    for target in [ROOT / "build", ROOT / "dist" / args.name]:
        if not target.resolve().is_relative_to(ROOT):
            raise SystemExit(f"Build output must stay inside the project: {target}")
    command = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--onedir", "--console" if args.console else "--windowed",
        "--name", args.name,
        "--paths", str(ROOT / "src"),
        "--specpath", str(ROOT / "build"),
        "--distpath", str(ROOT / "dist"),
        "--workpath", str(ROOT / "build" / "pyinstaller-isolated"),
        "--copy-metadata", "PySide6",
        "--copy-metadata", "shiboken6",
    ]
    for item in required:
        destination = item if (ROOT / item).is_dir() else "."
        command += ["--add-data", f"{ROOT / item};{destination}"]
    command.append(str(ROOT / "src" / "dynasty" / "__main__.py"))
    # Qt uses the Windows ICU library. Other apps' ICU/UCRT DLLs on PATH must not
    # be collected merely because their filenames match those system libraries.
    environment = os.environ.copy()
    windows = Path(environment.get("SystemRoot", "C:/Windows"))
    environment["PATH"] = os.pathsep.join(str(path) for path in [
        Path(sys.executable).parent, Path(sys.base_prefix), windows / "System32", windows,
    ])
    for key in ["PYTHONPATH", "PYTHONHOME"]:
        environment.pop(key, None)
    subprocess.run(command, cwd=ROOT, env=environment, check=True)
    print(ROOT / "dist" / args.name / f"{args.name}.exe")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
