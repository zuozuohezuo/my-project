"""Pursuit controls require actual completed activities instead of completion clicks."""

import copy

import pytest
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication, QDialogButtonBox, QLabel

from legacy_support import LegacyDemoConfig as DemoConfig, LegacyGameSession as GameSession
from dynasty.ui.emperor_motives_page import (
    EmperorMotivesPage, EmperorObjectiveEditor, EmperorPersonalityEditor,
)


PERSONALITY_IDS = {
    "benevolence", "trust", "tradition", "luxury", "control", "humility",
    "partiality", "integrity", "sociability",
}


@pytest.fixture
def motives_page(qtbot):
    session = GameSession.new_game({"metrics": {"treasury": 123}}, DemoConfig(initial_year=1500))
    page = EmperorMotivesPage(session)
    page.resize(1100, 650)
    qtbot.addWidget(page)
    page.show()
    qtbot.waitUntil(page.isVisible)
    return page


def click(qtbot, widget):
    assert widget.isEnabled()
    qtbot.mouseClick(widget, Qt.MouseButton.LeftButton)


def modal(qtbot, button, expected_type, callback):
    failures = []

    def interact():
        dialog = QApplication.activeModalWidget()
        try:
            assert isinstance(dialog, expected_type)
            callback(dialog)
            assert not dialog.isVisible(), "The interaction should close the editor."
        except BaseException as error:
            failures.append(error)
        finally:
            if dialog is not None and dialog.isVisible():
                dialog.reject()

    QTimer.singleShot(0, interact)
    click(qtbot, button)
    if failures:
        raise failures[0]


def test_nine_personality_axes_and_two_pursuit_categories_are_separate_from_states(motives_page):
    page = motives_page
    assert set(page.personality_values) == PERSONALITY_IDS
    assert all(label.text() == "50" for label in page.personality_values.values())
    assert all(bar.value() == 50 for bar in page.personality_bars.values())
    assert page.tabs.count() == 2
    text = "\n".join(label.text() for label in page.findChildren(QLabel))
    for left, right in (
        ("仁厚", "严酷"), ("宽信", "多疑"), ("守成", "求变"), ("质朴", "奢华"),
        ("放权", "掌控"), ("谦逊", "自负"), ("重情", "秉公"), ("守信", "权宜"),
        ("合群", "独处"),
    ):
        assert left in text and right in text
    assert "心理状态" not in text
    assert "淡泊" not in text and "好名" not in text
    assert page.session.state.emperor.objectives == []


def test_personality_cancel_and_save_leave_abilities_and_turn_resources_unchanged(qtbot, motives_page):
    page = motives_page
    before = copy.deepcopy(page.session.state.to_dict())

    def cancel(dialog):
        assert set(dialog.inputs) == PERSONALITY_IDS
        dialog.sliders["benevolence"].setValue(5)
        assert dialog.inputs["benevolence"].value() == 5
        click(qtbot, dialog.buttons.button(QDialogButtonBox.StandardButton.Cancel))

    modal(qtbot, page.personality_edit_button, EmperorPersonalityEditor, cancel)
    assert page.session.state.to_dict() == before

    def save(dialog):
        dialog.inputs["benevolence"].setValue(5)
        dialog.inputs["control"].setValue(95)
        assert dialog.sliders["control"].value() == 95
        click(qtbot, dialog.save_button)

    with qtbot.waitSignal(page.updated):
        modal(qtbot, page.personality_edit_button, EmperorPersonalityEditor, save)
    assert page.personality_values["benevolence"].text() == "5"
    assert page.personality_bars["control"].value() == 95
    after = page.session.state.to_dict()
    expected = copy.deepcopy(before)
    expected["emperor"]["personality"]["benevolence"] = 5
    expected["emperor"]["personality"]["control"] = 95
    assert after == expected


def test_player_creates_desire_and_only_actual_turn_completions_satisfy_it(qtbot, motives_page):
    page = motives_page
    session = page.session
    before = copy.deepcopy(session.state.to_dict())

    def create(dialog):
        assert dialog.target_count_input.text() == "1"
        dialog.title_input.setText("静心读书")
        dialog.description_input.setPlainText("读两次书\n由玩家自行设立")
        dialog.target_count_input.setText("0")
        click(qtbot, dialog.save_button)
        assert dialog.isVisible()
        assert dialog.error_label.text().strip()
        assert session.state.to_dict() == before
        dialog.target_count_input.setText("2")
        click(qtbot, dialog.save_button)

    modal(qtbot, page.objective_add_buttons["desire"], EmperorObjectiveEditor, create)
    objective = session.state.emperor.objectives[0]
    key = objective.id
    assert objective.progress == 0 and objective.status == "active"
    assert "0 / 2" in page.objective_progress_labels[key].text()
    assert "由玩家自行设立" in objective.description
    state_after_creation = copy.deepcopy(session.state.to_dict())
    for _ in range(2):
        with qtbot.waitSignal(page.activity_requested) as request:
            click(qtbot, page.objective_activity_buttons[key])
        assert request.args == ["study"]
    assert session.state.to_dict() == state_after_creation

    assert session.set_activities(["study", "rest", "rest"]).ok
    page.refresh(session)
    assert "0 / 2" in page.objective_progress_labels[key].text()
    assert session.advance_turn().ok
    page.refresh(session)
    assert "1 / 2" in page.objective_progress_labels[key].text()
    assert key in page.objective_activity_buttons
    assert session.set_activities(["study", "rest", "rest"]).ok
    assert session.advance_turn().ok
    page.refresh(session)
    assert "2 / 2" in page.objective_progress_labels[key].text()
    assert key in page.objective_cards
    assert key not in page.objective_activity_buttons
    assert key not in page.objective_discard_buttons
    completed_text = "\n".join(label.text() for label in page.objective_cards[key].findChildren(QLabel))
    assert "已满足" in completed_text
    assert session.state.emperor.objectives[0].status == "fulfilled"
    assert session.state.emperor.skills == before["emperor"]["skills"]
    assert session.state.emperor.pressure == before["emperor"]["pressure"]
    assert session.state.world_snapshot == before["world_snapshot"]


def test_ambition_is_customizable_and_active_objective_can_be_withdrawn(qtbot, motives_page):
    page = motives_page
    page.tabs.setCurrentIndex(1)

    def create(dialog):
        assert dialog.target_count_input.text() == "6"
        dialog.title_input.setText("坚持习武")
        dialog.activity_input.setCurrentIndex(dialog.activity_input.findData("exercise"))
        dialog.target_count_input.setText("9")
        click(qtbot, dialog.save_button)

    modal(qtbot, page.objective_add_buttons["ambition"], EmperorObjectiveEditor, create)
    objective = page.session.state.emperor.objectives[0]
    assert (objective.kind, objective.activity_kind, objective.target_count) == ("ambition", "exercise", 9)
    assert page.tabs.currentIndex() == 1
    with qtbot.waitSignal(page.updated):
        click(qtbot, page.objective_discard_buttons[objective.id])
    assert page.session.state.emperor.objectives == []
    assert objective.id not in page.objective_cards


def test_objective_cancel_and_refresh_use_the_current_session(qtbot, motives_page):
    page = motives_page
    old_session = page.session
    before = copy.deepcopy(old_session.state.to_dict())

    def cancel(dialog):
        dialog.title_input.setText("不设立的目标")
        click(qtbot, dialog.buttons.button(QDialogButtonBox.StandardButton.Cancel))

    modal(qtbot, page.objective_add_buttons["desire"], EmperorObjectiveEditor, cancel)
    assert old_session.state.to_dict() == before
    replacement = GameSession.new_game({}, DemoConfig(initial_year=1500))
    personality = dict(replacement.state.emperor.personality)
    personality["sociability"] = 90
    assert replacement.update_emperor_personality(personality).ok
    assert replacement.add_emperor_objective("desire", "休息一旬", "", "rest", 1).ok
    page.refresh(replacement)
    assert page.session is replacement
    assert page.personality_values["sociability"].text() == "90"
    target = replacement.state.emperor.objectives[0]
    click(qtbot, page.objective_discard_buttons[target.id])
    assert replacement.state.emperor.objectives == []
    assert old_session.state.to_dict() == before
