"""Capture representative views using the real bundled historical content."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication

from dynasty.content import load_demo_config, project_root
from dynasty.core import GameSession
from dynasty.ui.dialogs import MonthPlanDialog
from dynasty.ui.emperor_page import EmperorEditor
from dynasty.ui.main_window import MainWindow


def main() -> None:
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    output = project_root() / "artifacts"
    output.mkdir(exist_ok=True)
    window.show()

    def capture(widget, filename):
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        app.processEvents()
        app.processEvents()
        if not widget.grab().save(str(output / filename)):
            raise RuntimeError(f"Could not save {filename}")

    capture(window, "map-preview.png")
    window.session.set_activities(["court", "private", "rest"])
    window.refresh()
    window.open_court()
    window.show_page(1)
    capture(window, "court-preview.png")
    for _ in range(window.session.state.edict_limit):
        window.session.issue_command("build_canal", {"target": "beizhili", "budget": None})
    window.inject_emergency()
    capture(window, "emergency-preview.png")
    window.session.save_json(output / "急报示例存档.json")
    window.session = GameSession.new_game(window.repository.initial_world(), load_demo_config())
    window.refresh()
    dialog = MonthPlanDialog(window.repository, window.session, window)
    dialog.show()
    capture(dialog, "month-preview.png")
    dialog.close()
    for index, filename in [(2, "history-preview.png"), (4, "pending-preview.png")]:
        window.show_page(index)
        capture(window, filename)
    window.show_page(5)
    window._message("皇帝档案：查看基础属性与技能，或手动调整数值。")
    capture(window, "emperor-attributes-preview.png")
    window.emperor_page.tabs.setCurrentIndex(1)
    window.emperor_page.select_skill("people_reading")
    capture(window, "emperor-skills-preview.png")
    editor = EmperorEditor(window.session, window)
    editor.show()
    capture(editor, "emperor-editor-preview.png")
    editor.close()
    window.resize(1180, 800)
    window.emperor_page.tabs.setCurrentIndex(0)
    capture(window, "emperor-attributes-minimum.png")
    window.emperor_page.tabs.setCurrentIndex(1)
    capture(window, "emperor-skills-minimum.png")
    window.close()
    print(f"Saved 11 desktop previews to {output}")


if __name__ == "__main__":
    main()
