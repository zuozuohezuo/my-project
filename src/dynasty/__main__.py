"""Application entrypoint and reproducible UI snapshot mode."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="大明 · 御览")
    parser.add_argument("--screenshot", type=Path, help="save an offscreen desktop preview and exit")
    destination = parser.add_mutually_exclusive_group()
    destination.add_argument("--page", type=int, choices=range(7), help="preview an in-game page")
    destination.add_argument("--screen", choices=["menu", "setup", "load", "settings"], help="preview a launcher page")
    parser.add_argument("--emperor-tab", type=int, choices=range(3), help="emperor tab to preview with --page 5")
    parser.add_argument("--smoke", action="store_true", help="construct all pages, process events, and exit")
    parser.add_argument("--m03-demo", action="store_true", help="open a fresh 30-AP demonstration schedule")
    parser.add_argument("--county-demo", choices=["normal", "shortage", "input_shortage"],
                        nargs="?", const="normal", help="open a fresh, fictional county economy demo")
    parser.add_argument("--load-game", type=Path, help="open a saved game without replacing any player file")
    args = parser.parse_args()
    if args.emperor_tab is not None and args.page != 5:
        parser.error("--emperor-tab requires --page 5")
    if args.county_demo and (args.load_game or args.m03_demo or args.screen):
        parser.error("--county-demo cannot be combined with --load-game, --m03-demo or --screen")
    if args.screenshot or args.smoke:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication
    from dynasty.ui.launcher import AppWindow
    from dynasty.content import create_county_demo, load_demo_config
    from dynasty.core import GameSession, ScenarioProfile

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("MingDynastySimulator")
    app.setOrganizationName("DynastyWorkshop")
    window = AppWindow()
    if args.county_demo:
        window.enter_game(create_county_demo(args.county_demo, window.repository.root))
        window.game.show_page(args.page if args.page is not None else 6)
    elif args.load_game:
        window.enter_game(GameSession.load_json(args.load_game))
        window.game.show_page(args.page if args.page is not None else
                              6 if window.game.session.state.economy is not None else 1)
        if window.game._m03_mode and window.game.session.state.phase.value != "planning":
            window.game.turn_tabs.setCurrentIndex(1)
            window.game.refresh()
    elif args.page is not None or args.m03_demo:
        config = load_demo_config()
        profile = (ScenarioProfile("M03 · 三阶段试玩", "朱祐樘", "弘治", 1488)
                   if args.m03_demo and config.turn_rules_version >= 3 else None)
        window.enter_game(GameSession.new_game(window.repository.initial_world(), config, profile))
        window.game.show_page(args.page if args.page is not None else 1)
        if args.m03_demo:
            window.game.planning_page.load_example()
            window.game.planning_page.capture_draft()
            if window.game.session.config.turn_rules_version >= 3:
                window.game.session.inject_emergency(
                    "演示急报 · 边关请示", "示范局预先登记的急报，将按本旬阶段规则送达。")
            window.game.refresh()
        if args.emperor_tab is not None:
            window.game.emperor_page.tabs.setCurrentIndex(args.emperor_tab)
    elif args.screen:
        {"menu": window.show_home, "setup": window.show_setup,
         "load": window.show_load, "settings": window.show_settings}[args.screen]()
    if not args.smoke or args.screenshot:
        window.show()
    if args.screenshot or args.smoke:
        def finish() -> None:
            try:
                app.processEvents()
                if args.screenshot:
                    args.screenshot.parent.mkdir(parents=True, exist_ok=True)
                    if not window.grab().save(str(args.screenshot)):
                        raise RuntimeError("Unable to save screenshot")
                print("UI smoke OK")
                app.exit(0)
            except Exception as error:
                print(f"UI smoke failed: {error}", file=sys.stderr)
                app.exit(1)
        QTimer.singleShot(650, finish)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
