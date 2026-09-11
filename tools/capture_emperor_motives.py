"""Capture personality and pursuit examples in a separate demonstration game."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication

from dynasty.content import project_root
from dynasty.ui.emperor_motives_page import EmperorObjectiveEditor, EmperorPersonalityEditor
from dynasty.ui.main_window import MainWindow


def main() -> None:
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    output = project_root() / "artifacts"
    output.mkdir(exist_ok=True)
    window.show()
    window.show_page(5)
    window.emperor_page.tabs.setCurrentIndex(2)
    page = window.emperor_page.motives_page

    def capture(widget, filename):
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        app.processEvents()
        app.processEvents()
        if not widget.grab().save(str(output / filename)):
            raise RuntimeError(f"Could not save {filename}")

    window._message("性格与追求：九组稳定性格，以及由玩家完成的近期欲望与长期野心。")
    capture(window, "emperor-motives-preview.png")
    personality = dict(window.session.state.emperor.personality,
                       benevolence=25, trust=70, humility=20, partiality=30, sociability=35)
    assert window.session.update_emperor_personality(personality).ok
    assert window.session.add_emperor_objective(
        "desire", "静心读书", "完成一次读书安排，满足眼前的求知愿望。", "study", 1).ok
    assert window.session.add_emperor_objective(
        "ambition", "建立勤政习惯", "累计完成六次朝政活动；本例只核验活动完成，不代表已实现国家治理成果。", "court", 6).ok
    window.refresh()
    window._message("独立演示样例：性格与目标仅用于检查页面，不是历史皇帝评分或真实愿望。")
    capture(window, "emperor-desire-example.png")
    page.tabs.setCurrentIndex(1)
    capture(window, "emperor-ambition-example.png")
    page.tabs.setCurrentIndex(0)
    assert window.session.set_activities(["study", "rest", "rest"]).ok
    assert window.session.advance_turn().ok
    window.refresh()
    capture(window, "emperor-desire-fulfilled.png")
    window.session.save_json(output / "皇帝性格追求_演示存档.json")
    window.resize(1180, 800)
    capture(window, "emperor-motives-minimum.png")
    window.resize(1480, 940)
    editor = EmperorPersonalityEditor(window.session, window)
    editor.show()
    capture(editor, "emperor-personality-editor.png")
    editor.close()
    objective_editor = EmperorObjectiveEditor(window.session, "ambition", window)
    objective_editor.show()
    capture(objective_editor, "emperor-objective-editor.png")
    objective_editor.close()
    window.close()
    print(f"Saved 7 emperor motive previews to {output}")


if __name__ == "__main__":
    main()
