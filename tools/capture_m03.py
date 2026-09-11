"""Render actual M03 screens and isolated demonstration saves for review."""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from dynasty.content import HistoryRepository, load_demo_config
from dynasty.core import GameSession, ScenarioProfile
from dynasty.ui.appointments_dialog import AppointmentsDialog
from dynasty.ui.main_window import MainWindow
from dynasty.ui.month_planning_dialog import SequentialMonthPlanDialog


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "artifacts"


def main():
    if load_demo_config().turn_rules_version >= 3:
        from capture_m03_stages import main as capture_stages
        return capture_stages()
    app = QApplication.instance() or QApplication([])
    repo = HistoryRepository()
    game = GameSession.new_game(repo.initial_world(), load_demo_config(),
        ScenarioProfile("M03 · 起居日程试玩", "朱祐樘", "弘治", 1488))
    window = MainWindow(repo, game)
    window.show()
    window.show_page(1)
    window.planning_page.load_example()
    assert window.planning_page.capture_draft().ok
    OUTPUT.mkdir(exist_ok=True)

    def capture(name, widget=window):
        app.processEvents()
        assert widget.grab().save(str(OUTPUT / name))

    game.save_json(OUTPUT / "M03_旬初规划_演示存档.json")
    capture("M03-planning.png")
    assert game.start_turn().ok
    window.refresh()
    window.turn_tabs.setCurrentIndex(1)
    capture("M03-court.png")
    assert game.finish_activity().ok
    assert game.start_next_activity().ok
    assert game.current_activity.kind == "garden"
    assert game.continue_activity("flowers").ok
    window.refresh()
    capture("M03-garden.png")
    game.inject_emergency("演示急报 · 边关请示", "日程中途送达的演示急报，用于检查保存与恢复。")
    window.refresh()
    game.save_json(OUTPUT / "M03_宫苑中断_演示存档.json")
    capture("M03-emergency.png")
    assert game.resolve_emergency(command_id=None).ok
    window.refresh()
    window.turn_tabs.setCurrentIndex(1)
    capture("M03-resumed.png")
    assert game.continue_activity("pond").ok
    assert game.finish_activity().ok
    while game.current_activity is None or game.current_activity.kind != "paperwork":
        if game.current_activity:
            choice = game.current_activity.scene["choices"][-1]["id"]
            assert game.continue_activity(choice).ok
        else:
            assert game.start_next_activity().ok
    assert game.continue_activity("work").ok
    window.refresh()
    capture("M03-office.png")
    game.save_json(OUTPUT / "M03_办公中途_演示存档.json")

    fresh = GameSession.load_json(OUTPUT / "M03_旬初规划_演示存档.json")
    window.session = fresh
    window.refresh()
    window.turn_tabs.setCurrentIndex(0)
    fresh.create_appointment("seasonal", fresh.state.turn_index + 5, "lecture", "礼制讲议（演示）")
    fresh.create_appointment("event", fresh.state.turn_index + 1, "audience", "使者来访（演示）", cost=2)
    fresh.create_appointment("preparation", fresh.state.turn_index + 4, "garden", "游赏筹备（演示）")
    appointment = AppointmentsDialog(fresh, window)
    appointment.show()
    capture("M03-appointments.png", appointment)
    appointment.close()
    fresh.save_json(OUTPUT / "M03_未来预约_演示存档.json")
    month = SequentialMonthPlanDialog(repo, fresh, window)
    month._copy_first()
    month.show()
    capture("M03-three-turns.png", month)
    month.close()
    window.resize(1180, 800)
    capture("M03-small.png")
    window.close()
    print("M03 previews and isolated demonstration saves created")


if __name__ == "__main__":
    main()
