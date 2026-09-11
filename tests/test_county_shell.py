"""Player paths from county setup to the real game shell and draft protection."""

import copy

from dynasty.content import create_county_demo
from dynasty.ui.launcher import AppWindow
from dynasty.ui.main_window import MainWindow


def test_county_shortcut_does_not_discard_unsaved_planning_draft(qtbot):
    window = MainWindow(session=create_county_demo())
    qtbot.addWidget(window)
    window.planning_page.arrange_activity("lecture")
    draft = window.planning_page.draft_activities()
    before = window.session.to_dict()
    window.show_page(6)
    window.county_page.advance_turn()
    assert window.session.to_dict() == before
    assert window.planning_page.draft_activities() == draft
    assert "草稿" in window.county_page.feedback_label.text()


def test_resource_edit_keeps_planning_draft_and_updates_only_target_pool(qtbot):
    window = MainWindow(session=create_county_demo())
    qtbot.addWidget(window)
    window.planning_page.arrange_activity("lecture")
    draft = copy.deepcopy(window.planning_page.draft_activities())
    assert window.session.set_demo_economy_resource("private", "grain", 123).ok
    window.refresh()
    assert window.planning_page.draft_activities() == draft
    assert window.planning_page._dirty


def test_launcher_can_open_all_three_fresh_county_scenarios(qtbot, tmp_path):
    app = AppWindow(data_directory=tmp_path / "player")
    qtbot.addWidget(app)
    app.show_county_setup()
    for index, scenario in enumerate(["normal", "shortage", "input_shortage"]):
        app.county_scenario_combo.setCurrentIndex(index)
        app.start_county_demo()
        assert app.game.session.state.economy["scenario"] == scenario
        assert app.game.session.state.turn_index == 0
        assert app.game.stack.currentIndex() == 6
        assert app.game.county_page.tabs.count() == 8


def test_population_edit_preserves_unsubmitted_activity_plan(qtbot):
    window = MainWindow(session=create_county_demo())
    qtbot.addWidget(window)
    window.planning_page.arrange_activity("lecture")
    draft = copy.deepcopy(window.planning_page.draft_activities())
    window.show_page(6)
    assert window.session.set_demo_population_parameters(.6, .03, .02, 1).ok
    window.refresh()
    assert window.planning_page.draft_activities() == draft
    assert window.planning_page._dirty
    assert window.session.economy_view["population"]["base_labor"] == 600
    before = window.session.to_dict()
    window.county_page.advance_turn()
    assert window.session.to_dict() == before
    assert "草稿" in window.county_page.feedback_label.text()
