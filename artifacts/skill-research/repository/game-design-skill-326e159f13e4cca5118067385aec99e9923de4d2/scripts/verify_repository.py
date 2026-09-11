#!/usr/bin/env python3
"""Verify the two-plugin Marketplace, source boundaries, and canonical skills."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MARKETPLACE_PATH = ROOT / ".claude-plugin" / "marketplace.json"
CONFIG_PATH = ROOT / "provenance" / "upstream-files.json"
LOCK_PATH = ROOT / "provenance" / "upstream-lock.json"

PLUGIN_NAMES = ("game-design-skill", "ai-native-game-design")
PLUGIN_ROOTS = {name: ROOT / "plugins" / name for name in PLUGIN_NAMES}
SKILL_ROOTS = {
    name: PLUGIN_ROOTS[name] / "skills" / name for name in PLUGIN_NAMES
}
SKILL_PATHS = {name: SKILL_ROOTS[name] / "SKILL.md" for name in PLUGIN_NAMES}
REFERENCE_ROOTS = {
    name: SKILL_ROOTS[name] / "references" for name in PLUGIN_NAMES
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    errors: list[str] = []

    required = [
        MARKETPLACE_PATH,
        CONFIG_PATH,
        LOCK_PATH,
        ROOT / "LICENSE",
        ROOT / "THIRD_PARTY_NOTICES.md",
    ]
    for name in PLUGIN_NAMES:
        required.extend(
            [
                PLUGIN_ROOTS[name] / ".claude-plugin" / "plugin.json",
                PLUGIN_ROOTS[name] / ".codex-plugin" / "plugin.json",
                SKILL_PATHS[name],
                SKILL_ROOTS[name] / "agents" / "openai.yaml",
                REFERENCE_ROOTS[name] / "provenance.md",
                REFERENCE_ROOTS[name] / "authoritative-sources.md",
            ]
        )
    required.append(
        REFERENCE_ROOTS["ai-native-game-design"] / "ai-native-game-design.md"
    )
    required.append(
        REFERENCE_ROOTS["ai-native-game-design"] / "ai-npc-design.md"
    )

    for path in required:
        if not path.is_file():
            errors.append(f"missing required file: {path.relative_to(ROOT)}")

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    marketplace = load_json(MARKETPLACE_PATH)
    config = load_json(CONFIG_PATH)
    lock = load_json(LOCK_PATH)
    marketplace_plugins = marketplace.get("plugins", [])
    if not isinstance(marketplace_plugins, list):
        marketplace_plugins = []
        errors.append("marketplace plugins must be an array")

    if marketplace.get("name") != "game-design-skill":
        errors.append("marketplace name must remain game-design-skill")

    published_names = tuple(
        entry.get("name") for entry in marketplace_plugins if isinstance(entry, dict)
    )
    if published_names != PLUGIN_NAMES:
        errors.append(
            "marketplace must publish game-design-skill followed by "
            f"ai-native-game-design; found={published_names}"
        )

    marketplace_by_name = {
        entry["name"]: entry
        for entry in marketplace_plugins
        if isinstance(entry, dict) and isinstance(entry.get("name"), str)
    }
    manifests: dict[str, dict[str, dict[str, object]]] = {}
    for name in PLUGIN_NAMES:
        entry = marketplace_by_name.get(name, {})
        expected_source = f"./plugins/{name}"
        if entry.get("source") != expected_source:
            errors.append(
                f"marketplace source for {name} must be {expected_source}"
            )

        claude_manifest = load_json(
            PLUGIN_ROOTS[name] / ".claude-plugin" / "plugin.json"
        )
        codex_manifest = load_json(
            PLUGIN_ROOTS[name] / ".codex-plugin" / "plugin.json"
        )
        manifests[name] = {
            "claude": claude_manifest,
            "codex": codex_manifest,
        }
        for product, manifest in manifests[name].items():
            if manifest.get("name") != name:
                errors.append(f"{product} manifest name mismatch for {name}")
            if manifest.get("license") != "MIT":
                errors.append(f"{product} manifest license for {name} must be MIT")
            if manifest.get("version") != entry.get("version"):
                errors.append(
                    f"{product} manifest and marketplace versions differ for {name}"
                )
        if claude_manifest.get("version") != codex_manifest.get("version"):
            errors.append(f"Claude and Codex manifest versions differ for {name}")
        if entry.get("license") != "MIT":
            errors.append(f"marketplace entry license for {name} must be MIT")

    expected_skill_files = sorted(SKILL_PATHS.values())
    all_skill_files = sorted(ROOT.rglob("SKILL.md"))
    if all_skill_files != expected_skill_files:
        shown = ", ".join(str(path.relative_to(ROOT)) for path in all_skill_files)
        errors.append(
            "repository must contain exactly the two canonical SKILL.md files; "
            f"found: {shown}"
        )

    skill_texts: dict[str, str] = {}
    for name, path in SKILL_PATHS.items():
        text = path.read_text(encoding="utf-8")
        skill_texts[name] = text
        if "[TODO" in text or "TODO:" in text:
            errors.append(f"{name} SKILL.md contains a TODO placeholder")
        if len(text.splitlines()) >= 500:
            errors.append(f"{name} SKILL.md must remain under 500 lines")
        interface_text = (
            SKILL_ROOTS[name] / "agents" / "openai.yaml"
        ).read_text(encoding="utf-8")
        if f"${name}" not in interface_text:
            errors.append(
                f"{name} openai.yaml default_prompt must mention ${name}"
            )

    general_text = skill_texts["game-design-skill"]
    if "ai-native-game-design.md" in general_text:
        errors.append(
            "game-design-skill must not route to the independently installed "
            "AI-native reference"
        )
    if (
        REFERENCE_ROOTS["game-design-skill"] / "ai-native-game-design.md"
    ).exists():
        errors.append("AI-native reference must not remain inside game-design-skill")

    ai_text = skill_texts["ai-native-game-design"]
    if "`references/ai-native-game-design.md`" not in ai_text:
        errors.append(
            "ai-native-game-design SKILL.md must route to its canonical reference"
        )
    if "`references/ai-npc-design.md`" not in ai_text:
        errors.append(
            "ai-native-game-design SKILL.md must route to its NPC reference"
        )
    if "../game-design-skill" in ai_text or "..\\game-design-skill" in ai_text:
        errors.append("ai-native-game-design must not depend on the sibling plugin")

    config_by_destination = {
        item["destination"]: item for item in config.get("files", [])
    }
    lock_by_destination = {
        item["destination"]: item for item in lock.get("files", [])
    }
    if set(config_by_destination) != set(lock_by_destination):
        missing = sorted(set(config_by_destination) - set(lock_by_destination))
        extra = sorted(set(lock_by_destination) - set(config_by_destination))
        errors.append(
            f"provenance lock/config mismatch; missing={missing}, extra={extra}"
        )

    for destination, source_entry in config_by_destination.items():
        path = ROOT / destination
        lock_entry = lock_by_destination.get(destination)
        if not path.is_file():
            errors.append(f"missing vendored file: {destination}")
            continue
        if not lock_entry:
            continue
        if sha256(path) != lock_entry.get("sha256"):
            errors.append(f"hash mismatch for {destination}")
        if lock_entry.get("commit") != config.get("commit"):
            errors.append(f"wrong commit in lock for {destination}")
        if lock_entry.get("repository") != config.get("repository"):
            errors.append(f"wrong repository in lock for {destination}")
        if lock_entry.get("source") != source_entry.get("source"):
            errors.append(f"wrong source path in lock for {destination}")
        if lock_entry.get("status") != "verbatim":
            errors.append(f"vendored entry is not marked verbatim: {destination}")
        if not re.fullmatch(
            r"1-[1-9][0-9]*", str(lock_entry.get("source_lines", ""))
        ):
            errors.append(f"invalid source line range for {destination}")
        expected_url = (
            "https://github.com/Donchitos/Claude-Code-Game-Studios/blob/"
            f"{config.get('commit')}/{source_entry.get('source')}"
        )
        if lock_entry.get("source_url") != expected_url:
            errors.append(
                f"source URL is not immutable or does not match for {destination}"
            )

    referenced_upstream = set(
        re.findall(r"`(upstream-[a-z0-9-]+\.md)`", general_text)
    )
    expected_upstream = {
        Path(destination).name for destination in config_by_destination
    }
    if referenced_upstream != expected_upstream:
        missing = sorted(expected_upstream - referenced_upstream)
        extra = sorted(referenced_upstream - expected_upstream)
        errors.append(
            "general skill routing must cover every and only vendored upstream "
            f"reference; missing={missing}, extra={extra}"
        )
    for filename in referenced_upstream:
        if not (REFERENCE_ROOTS["game-design-skill"] / filename).is_file():
            errors.append(f"game-design-skill references a missing file: {filename}")

    general_sources = (
        REFERENCE_ROOTS["game-design-skill"] / "authoritative-sources.md"
    ).read_text(encoding="utf-8")
    if "https://gameinstitute.qq.com/news/detail/317" in general_sources:
        errors.append(
            "Tencent AI-native practitioner source must not remain in the "
            "general plugin"
        )

    ai_sources = (
        REFERENCE_ROOTS["ai-native-game-design"] / "authoritative-sources.md"
    ).read_text(encoding="utf-8")
    if "https://gameinstitute.qq.com/news/detail/317" not in ai_sources:
        errors.append(
            "AI-native source index must retain the Tencent practitioner source"
        )
    if "https://mp.weixin.qq.com/s/KBCZWEY1lVvvFvfhq_3Pvw" not in ai_sources:
        errors.append(
            "AI-native source index must include the Tencent EP.02 practitioner source"
        )
    ai_reference = (
        REFERENCE_ROOTS["ai-native-game-design"] / "ai-native-game-design.md"
    ).read_text(encoding="utf-8")
    if "practitioner evidence" not in ai_reference.lower():
        errors.append(
            "AI-native reference must preserve its practitioner-evidence boundary"
        )
    ai_npc_reference = (
        REFERENCE_ROOTS["ai-native-game-design"] / "ai-npc-design.md"
    ).read_text(encoding="utf-8")
    if "project-specific model sizes" not in ai_npc_reference:
        errors.append(
            "AI NPC reference must reject universal model-size guidance"
        )

    notice = (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    for required_notice in (
        "Copyright (c) 2026 Donchitos",
        config["commit"],
        "MIT License",
    ):
        if required_notice not in notice:
            errors.append(f"third-party notice is missing: {required_notice}")
    root_license = (ROOT / "LICENSE").read_text(encoding="utf-8")
    if "MIT License" not in root_license:
        errors.append("root LICENSE does not contain the MIT license heading")

    result = {
        "ok": not errors,
        "plugin_count": len(marketplace_plugins),
        "skill_count": len(all_skill_files),
        "plugins": {
            name: {
                "version": manifests.get(name, {})
                .get("claude", {})
                .get("version"),
                "skill_lines": len(skill_texts.get(name, "").splitlines()),
            }
            for name in PLUGIN_NAMES
        },
        "vendored_file_count": len(config_by_destination),
        "routed_vendored_file_count": len(referenced_upstream),
        "errors": errors,
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
