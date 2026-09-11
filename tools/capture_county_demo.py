"""Create isolated playable county saves and render real Qt pages for review."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from dynasty.content import create_county_demo, project_root
from dynasty.ui.launcher import AppWindow


def main():
    target = project_root() / "artifacts" / "county_demo"
    target.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    window = AppWindow(data_directory=target / "launcher")
    window.show()
    for scenario in ("normal", "shortage", "input_shortage"):
        session = create_county_demo(scenario)
        session.save_json(target / f"qinghe_{scenario}.json")
    normal = create_county_demo()
    window.enter_game(normal)
    window.game.show_page(6)
    for index, name in [(0, "population"), (1, "land"), (4, "pools"), (6, "production")]:
        window.game.county_page.tabs.setCurrentIndex(index)
        app.processEvents()
        if not window.grab().save(str(target / f"qinghe_{name}.png")):
            raise RuntimeError("Screenshot failed")
    population_page = window.game.county_page.tabs.widget(0)
    window.game.county_page.tabs.setCurrentIndex(0)
    population_page.ensureWidgetVisible(window.game.county_page.population_editor)
    population_page.verticalScrollBar().setValue(population_page.verticalScrollBar().maximum())
    app.processEvents()
    window.grab().save(str(target / "qinghe_population_parameters.png"))
    window.resize(1180, 800)
    app.processEvents()
    population_page.verticalScrollBar().setValue(population_page.verticalScrollBar().maximum())
    app.processEvents()
    window.grab().save(str(target / "qinghe_population_parameters_minimum.png"))
    window.resize(1480, 940)
    year = create_county_demo()
    for _ in range(36):
        result = year.advance_economy_demo_turn()
        if not result.ok:
            raise RuntimeError(result.message)
    year.save_json(target / "qinghe_normal_after_1_year.json")
    shortage = create_county_demo("shortage")
    for _ in range(4):
        result = shortage.advance_economy_demo_turn()
        if not result.ok:
            raise RuntimeError(result.message)
    shortage.save_json(target / "qinghe_shortage_after_4_turns.json")
    window.enter_game(shortage)
    window.game.show_page(6)
    window.game.county_page.tabs.setCurrentIndex(7)
    app.processEvents()
    window.grab().save(str(target / "qinghe_shortage_report.png"))
    window.resize(1180, 800)
    app.processEvents()
    window.grab().save(str(target / "qinghe_minimum.png"))
    window.close()
    print(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
