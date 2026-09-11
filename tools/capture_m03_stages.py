"""Reproducible native Qt screenshots and independent v3 stage saves."""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from dynasty.content import HistoryRepository, load_demo_config
from dynasty.core import GameSession, Phase, ScenarioProfile
from dynasty.ui.main_window import MainWindow


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts"


def main():
    app = QApplication.instance() or QApplication([])
    repo = HistoryRepository()
    game = GameSession.new_game(repo.initial_world(), load_demo_config(),
                               ScenarioProfile("M03 · 三阶段试玩", "朱祐樘", "弘治", 1488))
    window = MainWindow(repo, game)
    window.show()
    window.show_page(1)
    OUT.mkdir(exist_ok=True)

    def capture(name, *, planning=False):
        window.refresh()
        if game.state.phase == Phase.INTERRUPTED:
            window.turn_tabs.setCurrentIndex(2)
        else:
            window.turn_tabs.setCurrentIndex(0 if planning else 1)
        app.processEvents()
        assert window.grab().save(str(OUT / name))

    capture("M03-stages-default.png", planning=True)
    game.save_json(OUT / "M03_三阶段旬初_演示存档.json")
    window.planning_page.load_example()
    capture("M03-stages-planning.png", planning=True)
    # Keep the live domain plan unassigned to demonstrate the stage picker.
    assert game.start_turn().ok
    capture("M03-stages-court.png")
    assert game.finish_activity().ok
    if game.state.turn_stage == "court":
        game.start_next_activity()
    assert game.state.turn_stage == "work"
    capture("M03-stages-work-choice.png")
    assert game.append_stage_activity("paperwork", 15).ok
    assert game.start_next_activity().ok
    game.inject_emergency("演示急报 · 边关请示", "工作阶段中间收到的示范急报。")
    for _ in range(9):
        if game.state.phase == Phase.INTERRUPTED:
            break
        game.continue_activity("work")
    assert game.state.phase == Phase.INTERRUPTED
    capture("M03-stages-emergency.png")
    game.save_json(OUT / "M03_三阶段工作急报_演示存档.json")
    assert game.resolve_emergency(command_id=None).ok
    capture("M03-stages-work-resumed.png")
    assert game.finish_work_stage().ok
    assert game.state.turn_stage == "private"
    capture("M03-stages-private-choice.png")
    game.save_json(OUT / "M03_三阶段转私生活_演示存档.json")
    assert game.append_stage_activity("garden", 1).ok
    assert game.start_next_activity().ok
    assert game.continue_activity("flowers").ok
    capture("M03-stages-garden.png")
    game.save_json(OUT / "M03_三阶段宫苑_演示存档.json")
    window.resize(1180, 800)
    capture("M03-stages-small.png")
    window.close()
    print("M03 stage previews and independent saves created")


if __name__ == "__main__":
    main()
