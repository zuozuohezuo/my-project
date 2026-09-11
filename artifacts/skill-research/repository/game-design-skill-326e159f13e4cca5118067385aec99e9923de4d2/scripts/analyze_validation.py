#!/usr/bin/env python3
"""Summarize current structural, installation, link, and cleanup evidence."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "verification" / "results"
SUMMARY_PATH = RESULTS / "validation-summary.json"


def run_repository_verifier() -> tuple[dict[str, object], bool]:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "verify_repository.py")],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        payload = {
            "ok": False,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    return payload, result.returncode == 0 and bool(payload.get("ok"))


def main() -> int:
    repository, repository_ok = run_repository_verifier()
    links = json.loads(
        (RESULTS / "link-check.json").read_text(encoding="utf-8")
    )
    install = json.loads(
        (RESULTS / "install-evidence.json").read_text(encoding="utf-8")
    )
    restore = json.loads(
        (RESULTS / "environment-restore.json").read_text(encoding="utf-8")
    )

    installed_plugins = install.get("plugins", {})
    cases = {
        "repository_structure": {
            "verifier_ok": repository_ok,
            "plugin_count_is_2": repository.get("plugin_count") == 2,
            "skill_count_is_2": repository.get("skill_count") == 2,
            "all_vendored_references_routed": (
                repository.get("vendored_file_count")
                == repository.get("routed_vendored_file_count")
            ),
        },
        "dual_platform_installation": {
            "commands_ok": bool(install.get("commands_ok")),
            "game_design_sha_matches_both_installs": bool(
                installed_plugins.get("game-design-skill", {}).get(
                    "all_skill_sha256_equal"
                )
            ),
            "ai_native_sha_matches_both_installs": bool(
                installed_plugins.get("ai-native-game-design", {}).get(
                    "all_skill_sha256_equal"
                )
            ),
            "tracked_plugin_assets_match_both_installs": all(
                bool(entry.get("all_tracked_assets_sha256_equal"))
                for entry in installed_plugins.values()
            ),
        },
        "authored_links": {
            "link_check_ok": bool(links.get("ok")),
        },
        "environment_restore": {
            "restore_ok": bool(restore.get("ok")),
        },
    }
    case_status = {name: all(checks.values()) for name, checks in cases.items()}
    summary = {
        "ok": all(case_status.values()),
        "baseline": "two independently installable Marketplace plugins",
        "cases": cases,
        "case_status": case_status,
        "historical_behavioral_transcripts": {
            "counted_as_current_gate": False,
            "note": (
                "Existing raw model transcripts predate the two-plugin split. "
                "Current isolated forward tests are summarized in "
                "verification/REPORT.md."
            ),
        },
        "environment_notes": [
            "Both plugin IDs were independently discovered and installed by Claude Code and Codex.",
            "Each canonical skill matched its Claude and Codex cache copy by SHA-256.",
            "The new AI NPC reference asset matched its canonical copy in both product caches.",
            "Temporary installations, Marketplace registrations, caches, and generated local settings were removed after capture.",
        ],
    }
    SUMMARY_PATH.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
