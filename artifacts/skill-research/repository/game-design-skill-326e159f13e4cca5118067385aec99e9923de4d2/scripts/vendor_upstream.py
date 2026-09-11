#!/usr/bin/env python3
"""Vendor pinned upstream Git blobs and write a deterministic provenance lock."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "provenance" / "upstream-files.json"
LOCK_PATH = ROOT / "provenance" / "upstream-lock.json"


def run_git(repo: Path, *args: str) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        message = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"git {' '.join(args)} failed: {message}")
    return result.stdout


def normalized_github_identity(url: str) -> str:
    value = url.strip()
    for prefix in ("https://github.com/", "http://github.com/", "git@github.com:"):
        if value.startswith(prefix):
            value = value[len(prefix) :]
            break
    if value.endswith(".git"):
        value = value[:-4]
    return value.casefold()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path, help="Upstream Git checkout")
    args = parser.parse_args()

    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    source = args.source.resolve()
    expected_identity = normalized_github_identity(config["repository"])
    actual_origin = run_git(source, "remote", "get-url", "origin").decode("utf-8").strip()
    actual_identity = normalized_github_identity(actual_origin)
    if actual_identity != expected_identity:
        raise RuntimeError(
            f"Expected upstream {expected_identity}, got {actual_origin or '<no origin>'}"
        )

    commit = config["commit"]
    resolved = run_git(source, "rev-parse", f"{commit}^{{commit}}").decode("ascii").strip()
    if resolved != commit:
        raise RuntimeError(f"Pinned commit resolved to {resolved}, expected {commit}")

    lock_entries = []
    for entry in config["files"]:
        source_path = entry["source"]
        data = run_git(source, "show", f"{commit}:{source_path}")
        destination = ROOT / entry["destination"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)

        digest = hashlib.sha256(data).hexdigest()
        line_count = len(data.decode("utf-8").splitlines())
        blob_sha = run_git(source, "rev-parse", f"{commit}:{source_path}").decode("ascii").strip()
        lock_entries.append(
            {
                "repository": config["repository"],
                "commit": commit,
                "source": source_path,
                "source_url": (
                    "https://github.com/Donchitos/Claude-Code-Game-Studios/blob/"
                    f"{commit}/{source_path}"
                ),
                "source_lines": f"1-{line_count}",
                "source_blob": blob_sha,
                "destination": entry["destination"],
                "sha256": digest,
                "status": entry["status"],
                "reason": entry["reason"],
            }
        )

    lock = {
        "schema_version": 1,
        "repository": config["repository"],
        "commit": commit,
        "license": config["license"],
        "files": lock_entries,
    }
    LOCK_PATH.write_text(json.dumps(lock, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Vendored {len(lock_entries)} files from {commit}")
    print(f"Wrote {LOCK_PATH}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
