#!/usr/bin/env python3
"""Check authored Markdown links and URL structure without network flakiness."""

from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
RESULT_PATH = ROOT / "verification" / "results" / "link-check.json"
AUTHORED = [
    ROOT / "README.md",
    ROOT / "THIRD_PARTY_NOTICES.md",
    ROOT
    / "plugins"
    / "game-design-skill"
    / "skills"
    / "game-design-skill"
    / "references"
    / "authoritative-sources.md",
    ROOT
    / "plugins"
    / "game-design-skill"
    / "skills"
    / "game-design-skill"
    / "references"
    / "provenance.md",
    ROOT
    / "plugins"
    / "ai-native-game-design"
    / "skills"
    / "ai-native-game-design"
    / "references"
    / "ai-native-game-design.md",
    ROOT
    / "plugins"
    / "ai-native-game-design"
    / "skills"
    / "ai-native-game-design"
    / "references"
    / "ai-npc-design.md",
    ROOT
    / "plugins"
    / "ai-native-game-design"
    / "skills"
    / "ai-native-game-design"
    / "references"
    / "authoritative-sources.md",
    ROOT
    / "plugins"
    / "ai-native-game-design"
    / "skills"
    / "ai-native-game-design"
    / "references"
    / "provenance.md",
    ROOT / "verification" / "README.md",
]


def main() -> int:
    errors: list[str] = []
    external: set[str] = set()
    local: set[str] = set()
    markdown_link = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
    angle_url = re.compile(r"<(https?://[^>]+)>")

    for path in AUTHORED:
        if not path.is_file():
            errors.append(f"missing authored Markdown file: {path.relative_to(ROOT)}")
            continue
        text = path.read_text(encoding="utf-8")
        targets = markdown_link.findall(text) + angle_url.findall(text)
        for target in targets:
            target = target.strip()
            if target.startswith(("https://", "http://")):
                parsed = urlparse(target)
                if parsed.scheme != "https" or not parsed.netloc or any(ch.isspace() for ch in target):
                    errors.append(f"invalid authoritative URL in {path.relative_to(ROOT)}: {target}")
                external.add(target)
            elif target.startswith("#"):
                continue
            else:
                destination = (path.parent / target).resolve()
                local.add(str(destination))
                if not destination.exists():
                    errors.append(
                        f"broken local Markdown link in {path.relative_to(ROOT)}: {target}"
                    )

    result = {
        "ok": not errors,
        "authored_files_checked": len(AUTHORED),
        "external_https_urls_checked": len(external),
        "local_links_checked": len(local),
        "note": "External links are checked for HTTPS syntax; source immutability and commit paths are checked by verify_repository.py.",
        "errors": errors,
    }
    RESULT_PATH.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
