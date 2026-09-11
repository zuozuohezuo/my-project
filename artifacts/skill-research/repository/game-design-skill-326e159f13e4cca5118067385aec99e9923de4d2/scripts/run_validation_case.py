#!/usr/bin/env python3
"""Run one installed-skill validation case and preserve raw CLI evidence."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "verification" / "results"


def command_version(executable: str, environment: dict[str, str]) -> str:
    result = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            f"& {executable} --version",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=environment,
    )
    return result.stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("platform", choices=("codex", "claude"))
    parser.add_argument("case", help="Case name without .md")
    parser.add_argument(
        "--codex-model",
        default="gpt-5.4",
        help="Explicit Codex model used to avoid relying on a possibly newer user default",
    )
    parser.add_argument(
        "--claude-model",
        default="sonnet",
        help="Explicit Claude model alias used for reproducible validation",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=360,
        help="Hard timeout; the complete spawned process tree is stopped on expiry",
    )
    args = parser.parse_args()

    case_path = ROOT / "verification" / "cases" / f"{args.case}.md"
    if not case_path.is_file():
        raise SystemExit(f"Missing case: {case_path}")
    prompt = case_path.read_text(encoding="utf-8")
    RESULTS.mkdir(parents=True, exist_ok=True)

    environment = os.environ.copy()
    environment["GAME_DESIGN_VALIDATION_ROOT"] = str(ROOT)
    environment["GAME_DESIGN_EMPTY_MCP_CONFIG"] = str(
        ROOT / "verification" / "fixtures" / "empty-mcp.json"
    )
    if args.platform == "codex":
        powershell_script = (
            "& codex exec -C $env:GAME_DESIGN_VALIDATION_ROOT "
            f"-s read-only --ephemeral --json -m {args.codex_model} -"
        )
    else:
        powershell_script = (
            "& claude -p --permission-mode plan --max-turns 8 "
            f"--model {args.claude_model} --effort medium "
            "--no-session-persistence --no-chrome "
            "--strict-mcp-config --mcp-config $env:GAME_DESIGN_EMPTY_MCP_CONFIG "
            "--tools 'Skill,Read,Glob,Grep' --output-format json"
        )
    command = [
        "powershell.exe",
        "-NoProfile",
        "-NonInteractive",
        "-Command",
        powershell_script,
    ]

    started = time.monotonic()
    process = subprocess.Popen(
        command,
        cwd=ROOT,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=environment,
    )
    timed_out = False
    try:
        stdout, stderr = process.communicate(prompt, timeout=args.timeout_seconds)
    except subprocess.TimeoutExpired:
        timed_out = True
        subprocess.run(
            ["taskkill.exe", "/PID", str(process.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        try:
            stdout, stderr = process.communicate(timeout=30)
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate(timeout=10)
    elapsed = round(time.monotonic() - started, 3)

    stem = f"{args.platform}-{args.case}"
    stdout_path = RESULTS / f"{stem}.stdout"
    stderr_path = RESULTS / f"{stem}.stderr"
    meta_path = RESULTS / f"{stem}.meta.json"
    stdout_path.write_text(stdout, encoding="utf-8")
    stderr_path.write_text(stderr, encoding="utf-8")
    process_returncode = 124 if timed_out else process.returncode
    if args.platform == "codex":
        protocol_completed = any(
            '"type":"turn.completed"' in line for line in stdout.splitlines()
        )
    else:
        try:
            response = json.loads(stdout)
            protocol_completed = (
                response.get("subtype") == "success" and not response.get("is_error", False)
            )
        except json.JSONDecodeError:
            protocol_completed = False
    validation_returncode = 0 if protocol_completed else process_returncode
    metadata = {
        "platform": args.platform,
        "platform_version": command_version(args.platform, environment),
        "case": args.case,
        "requested_model": args.codex_model if args.platform == "codex" else args.claude_model,
        "case_path": str(case_path.relative_to(ROOT)).replace("\\", "/"),
        "working_directory": str(ROOT),
        "validation_returncode": validation_returncode,
        "process_returncode": process_returncode,
        "protocol_completed": protocol_completed,
        "timed_out": timed_out,
        "timeout_seconds": args.timeout_seconds,
        "elapsed_seconds": elapsed,
        "stdout": str(stdout_path.relative_to(ROOT)).replace("\\", "/"),
        "stderr": str(stderr_path.relative_to(ROOT)).replace("\\", "/"),
    }
    meta_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(metadata, indent=2))
    return validation_returncode


if __name__ == "__main__":
    raise SystemExit(main())
