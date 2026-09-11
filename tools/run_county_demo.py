"""Run the explicit county fixture through complete M03 rest turns."""

import argparse
import json
from pathlib import Path

from dynasty.content import create_county_demo


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=["normal", "shortage", "input_shortage"], default="normal")
    parser.add_argument("--turns", type=int, default=12)
    parser.add_argument("--save", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    if not 0 <= args.turns <= 360:
        parser.error("--turns must be between 0 and 360")
    game = create_county_demo(args.scenario)
    for _ in range(args.turns):
        result = game.advance_economy_demo_turn()
        if not result.ok:
            raise RuntimeError(result.message)
        print(game.state.economy["history"][-1]["summary"])
    if args.save:
        game.save_json(args.save)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(game.economy_view, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
