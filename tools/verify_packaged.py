"""Verify a Windows build starts outside the source directory with bundled assets."""

from datetime import datetime, timezone
import argparse
import hashlib
import json
import os
import re
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", default="MingImperialDesk")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.name):
        parser.error("Invalid packaged app name")
    output = ROOT / "artifacts"
    output.mkdir(exist_ok=True)
    working = output / "packaged-cwd"
    working.mkdir(exist_ok=True)
    executable = ROOT / "dist" / args.name / f"{args.name}.exe"
    bundle = executable.parent / "_internal"
    failures = []
    count = 0
    for directory in ["data", "assets", "docs"]:
        for source in sorted((ROOT / directory).rglob("*")):
            if not source.is_file():
                continue
            relative = source.relative_to(ROOT)
            target = bundle / relative
            if not target.exists() or digest(source) != digest(target):
                failures.append(f"Missing or mismatched bundle content: {relative}")
            count += 1
    for filename in ["README.md", "THIRD_PARTY_NOTICES.md", "王朝模拟_技术方案.md", "王朝模拟_框架草案.md"]:
        if not (bundle / filename).exists() or digest(ROOT / filename) != digest(bundle / filename):
            failures.append(f"Missing or mismatched bundled document: {filename}")
        count += 1
    for required in ["python312.dll", "PySide6/Qt6Widgets.dll", "assets/fonts/NotoSansSC.ttf"]:
        if not (bundle / required).exists():
            failures.append(f"Missing runtime component: {required}")
    environment = os.environ.copy()
    for key in ["VIRTUAL_ENV", "PYTHONPATH", "PYTHONHOME", "DYNASTY_ROOT"]:
        environment.pop(key, None)
    runs = []
    destinations = [("page", str(page)) for page in [0, 1, 4, 5]]
    destinations += [("screen", screen) for screen in ["menu", "setup", "load", "settings"]]
    destinations += [("m03", name) for name in ["demo", "emergency", "office", "appointments"]]
    stage_saves = {
        "planning": "M03_三阶段旬初_演示存档.json",
        "work-emergency": "M03_三阶段工作急报_演示存档.json",
        "private-choice": "M03_三阶段转私生活_演示存档.json",
        "garden": "M03_三阶段宫苑_演示存档.json",
    }
    destinations += [("stages", name) for name in stage_saves]
    for mode, page in destinations:
        screenshot = output / f"packaged-{mode}-{page}.png"
        # A fresh filename ensures an earlier preview cannot make a failed run appear successful.
        started_at = datetime.now(timezone.utc).timestamp()
        command = [str(executable), "--screenshot", str(screenshot)]
        if mode == "stages":
            command += ["--load-game", str(output / stage_saves[page])]
        elif mode == "m03":
            if page == "demo":
                command += ["--m03-demo"]
            else:
                files = {"emergency": "M03_宫苑中断_演示存档.json", "office": "M03_办公中途_演示存档.json",
                         "appointments": "M03_未来预约_演示存档.json"}
                command += ["--load-game", str(output / files[page])]
        else:
            command += [f"--{mode}", page]
        if mode == "page" and page == "5":
            command += ["--emperor-tab", "2"]
        try:
            result = subprocess.run(command, cwd=working, env=environment, timeout=30,
                                    capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
        except subprocess.TimeoutExpired:
            failures.append(f"Packaged UI did not exit within 30 seconds on page {page}")
            runs.append({mode: page, "passed": False, "timeout_seconds": 30})
            break
        fresh = screenshot.exists() and screenshot.stat().st_mtime >= started_at
        passed = result.returncode == 0 and fresh and screenshot.stat().st_size > 1000
        runs.append({mode: page, "exit_code": result.returncode, "screenshot_created": fresh,
                     "passed": passed, "screenshot": str(screenshot.relative_to(ROOT))})
        if not passed:
            failures.append(f"Packaged UI failed on page {page}: {result.stderr!r}")
    native_environment = dict(environment, QT_QPA_PLATFORM="windows")
    try:
        native = subprocess.run([str(executable), "--smoke", "--m03-demo"], cwd=working,
                                env=native_environment, timeout=30, capture_output=True,
                                creationflags=subprocess.CREATE_NO_WINDOW)
        native_passed = native.returncode == 0
        if not native_passed:
            failures.append(f"Native Windows platform initialization failed: {native.stderr!r}")
    except subprocess.TimeoutExpired:
        native_passed = False
        failures.append("Native Windows platform initialization timed out")
    report = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "status": "failed" if failures else "passed",
        "executable": str(executable.relative_to(ROOT)),
        "executable_sha256": digest(executable),
        "working_directory": str(working.relative_to(ROOT)),
        "python_environment_overrides_removed": True,
        "native_windows_platform_hidden_smoke_passed": native_passed,
        "bundled_content_files_checked": count,
        "runs": runs,
        "failures": failures,
    }
    (output / "packaged-verification.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
