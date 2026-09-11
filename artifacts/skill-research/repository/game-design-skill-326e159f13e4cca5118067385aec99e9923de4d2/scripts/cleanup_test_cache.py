#!/usr/bin/env python3
"""Delete only the exact shared Marketplace caches created by local validation."""

from __future__ import annotations

import os
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    user_profile = Path(os.environ["USERPROFILE"]).resolve()
    targets = [
        user_profile / ".claude" / "plugins" / "cache" / "game-design-skill",
        user_profile / ".codex" / "plugins" / "cache" / "game-design-skill",
        ROOT / ".claude",
    ]
    expected = {
        str(user_profile / ".claude" / "plugins" / "cache" / "game-design-skill"),
        str(user_profile / ".codex" / "plugins" / "cache" / "game-design-skill"),
        str(ROOT / ".claude"),
    }
    resolved = {str(path.resolve()) for path in targets}
    if resolved != expected:
        raise SystemExit(f"Refusing cleanup: resolved targets differ from allowlist: {resolved}")

    for path in targets:
        if path.exists():
            shutil.rmtree(path)
            print(f"removed: {path}")
        else:
            print(f"already absent: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
