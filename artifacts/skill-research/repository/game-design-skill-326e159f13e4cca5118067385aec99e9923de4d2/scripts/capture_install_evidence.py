#!/usr/bin/env python3
"""Capture dual-platform discovery and canonical SHA evidence for both plugins."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULT_PATH = ROOT / "verification" / "results" / "install-evidence.json"
MARKETPLACE = "game-design-skill"
PLUGIN_NAMES = ("game-design-skill", "ai-native-game-design")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def powershell(command: str) -> dict[str, object]:
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
        check=False,
    )
    return {
        "command": command,
        "returncode": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }


def main() -> int:
    user_profile = Path(os.environ["USERPROFILE"])
    plugin_evidence: dict[str, object] = {}

    for name in PLUGIN_NAMES:
        manifest_path = (
            ROOT / "plugins" / name / ".claude-plugin" / "plugin.json"
        )
        version = json.loads(manifest_path.read_text(encoding="utf-8"))["version"]
        skill_relative = Path("skills") / name / "SKILL.md"
        tracked_relatives = [skill_relative]
        if name == "ai-native-game-design":
            tracked_relatives.append(
                Path("skills")
                / name
                / "references"
                / "ai-npc-design.md"
            )
        files = {
            "canonical": ROOT / "plugins" / name / skill_relative,
            "claude_installed": (
                user_profile
                / ".claude"
                / "plugins"
                / "cache"
                / MARKETPLACE
                / name
                / version
                / skill_relative
            ),
            "codex_installed": (
                user_profile
                / ".codex"
                / "plugins"
                / "cache"
                / MARKETPLACE
                / name
                / version
                / skill_relative
            ),
        }
        file_evidence: dict[str, object] = {}
        for label, path in files.items():
            file_evidence[label] = {
                "path": str(path),
                "exists": path.is_file(),
                "sha256": sha256(path) if path.is_file() else None,
            }
        hashes = [entry["sha256"] for entry in file_evidence.values()]
        tracked_assets: dict[str, object] = {}
        for relative in tracked_relatives:
            asset_paths = {
                "canonical": ROOT / "plugins" / name / relative,
                "claude_installed": (
                    user_profile
                    / ".claude"
                    / "plugins"
                    / "cache"
                    / MARKETPLACE
                    / name
                    / version
                    / relative
                ),
                "codex_installed": (
                    user_profile
                    / ".codex"
                    / "plugins"
                    / "cache"
                    / MARKETPLACE
                    / name
                    / version
                    / relative
                ),
            }
            asset_files = {
                label: {
                    "path": str(path),
                    "exists": path.is_file(),
                    "sha256": sha256(path) if path.is_file() else None,
                }
                for label, path in asset_paths.items()
            }
            asset_hashes = [entry["sha256"] for entry in asset_files.values()]
            tracked_assets[str(relative).replace("\\", "/")] = {
                "files": asset_files,
                "all_sha256_equal": (
                    all(asset_hashes) and len(set(asset_hashes)) == 1
                ),
            }
        plugin_evidence[name] = {
            "plugin": f"{name}@{MARKETPLACE}",
            "version": version,
            "files": file_evidence,
            "all_skill_sha256_equal": all(hashes) and len(set(hashes)) == 1,
            "tracked_assets": tracked_assets,
            "all_tracked_assets_sha256_equal": all(
                bool(asset["all_sha256_equal"])
                for asset in tracked_assets.values()
            ),
        }

    commands = {
        "claude_version": powershell("claude --version"),
        "claude_game_design_details": powershell(
            "claude plugin details game-design-skill@game-design-skill"
        ),
        "claude_ai_native_details": powershell(
            "claude plugin details ai-native-game-design@game-design-skill"
        ),
        "claude_marketplace_match": powershell(
            "claude plugin marketplace list | "
            "Select-String -Pattern 'game-design-skill'"
        ),
        "codex_version": powershell("codex --version"),
        "codex_plugin_list": powershell(
            "codex plugin list --marketplace game-design-skill --json"
        ),
        "codex_marketplace_match": powershell(
            "codex plugin marketplace list --json | "
            "Select-String -Pattern 'game-design-skill'"
        ),
    }
    plugins_ok = all(
        bool(entry["all_skill_sha256_equal"])
        and bool(entry["all_tracked_assets_sha256_equal"])
        for entry in plugin_evidence.values()
    )
    commands_ok = all(entry["returncode"] == 0 for entry in commands.values())
    evidence = {
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "marketplace": MARKETPLACE,
        "plugins": plugin_evidence,
        "commands": commands,
        "commands_ok": commands_ok,
        "ok": plugins_ok and commands_ok,
    }
    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(
        json.dumps(evidence, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"path": str(RESULT_PATH), "ok": evidence["ok"]}, indent=2))
    return 0 if evidence["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
