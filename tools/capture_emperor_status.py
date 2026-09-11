"""Capture explicit status fixtures without changing a player's game or save."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication

from dynasty.content import project_root
from dynasty.core.emperor import BodyCondition, EmperorModifier
from dynasty.ui.emperor_status_dialogs import EmperorHealthEditor, EmperorModifierEditor
from dynasty.ui.main_window import MainWindow


def main() -> None:
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    output = project_root() / "artifacts"
    output.mkdir(exist_ok=True)
    window.show()
    window.show_page(5)

    def capture(widget, filename):
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        app.processEvents()
        app.processEvents()
        if not widget.grab().save(str(output / filename)):
            raise RuntimeError(f"Could not save {filename}")

    window._message("皇帝档案：整体健康、压力与当前修正。身体健康时不显示部位明细。")
    capture(window, "emperor-health-preview.png")
    window.resize(1180, 800)
    capture(window, "emperor-health-minimum.png")
    window.resize(1480, 940)
    assert window.session.update_emperor_health(76, 42, [
        BodyCondition("左臂", "旧伤", "injury"),
    ]).ok
    assert window.session.update_emperor_modifiers([
        EmperorModifier("左臂活动受限", "attribute", "agility", -8, "旧伤 · 演示样例"),
        EmperorModifier("心境澄明", "skill_effect", "calligraphy", 20, "演示样例",
                        "short_term", 2),
    ]).ok
    window.refresh()
    window._message("演示样例：手动录入身体异常与修正，仅供页面检查，不代表历史设定或疾病公式。")
    capture(window, "emperor-status-example.png")
    window.session.save_json(output / "皇帝健康修正_演示存档.json")
    window.resize(1180, 800)
    capture(window, "emperor-status-example-minimum.png")
    window.resize(1480, 940)
    window.emperor_page.tabs.setCurrentIndex(1)
    window.emperor_page.select_skill("calligraphy")
    capture(window, "emperor-skill-modifier-example.png")
    health = EmperorHealthEditor(window.session, window)
    health.show()
    capture(health, "emperor-health-editor.png")
    health.close()
    modifiers = EmperorModifierEditor(window.session, window)
    modifiers.show()
    capture(modifiers, "emperor-modifier-editor.png")
    modifiers.close()
    window.close()
    print(f"Saved 7 emperor status previews to {output}")


if __name__ == "__main__":
    main()
