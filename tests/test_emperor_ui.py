"""Exercise emperor inspection and manual editing through the actual desktop UI."""

import copy
import json

import pytest
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication, QDialogButtonBox, QFileDialog, QLabel

from dynasty.content import HistoryRepository
from dynasty.core import ScenarioProfile
from legacy_support import LegacyDemoConfig as DemoConfig, LegacyGameSession as GameSession
from dynasty.core.emperor import BodyCondition, EmperorModifier
from dynasty.ui.emperor_page import EmperorEditor
from dynasty.ui.emperor_status_dialogs import EmperorHealthEditor, EmperorModifierEditor
from dynasty.ui.main_window import MainWindow


ATTRIBUTE_IDS = {
    "logic", "emotional_intelligence", "memory", "insight", "creativity",
    "strength", "constitution", "agility", "perception", "appearance",
    "self_discipline", "emotional_resilience", "courage",
}
SKILL_IDS = {
    "administration", "military_strategy", "people_reading", "rhetoric",
    "calligraphy", "scholarship",
}


@pytest.fixture
def emperor_window(qtbot, monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "user-data"))
    directory = tmp_path / "data" / "history"
    directory.mkdir(parents=True)
    tables = {
        "regions": [
            {"id": "test_region", "name": "测试地区", "longitude": 115, "latitude": 35},
        ],
        "people": [], "offices": [], "prefectures": [], "counties": [], "laws": [],
    }
    for category, records in tables.items():
        (directory / f"{category}.json").write_text(
            json.dumps({"records": records}, ensure_ascii=False), encoding="utf-8"
        )
    repository = HistoryRepository(tmp_path)
    world = repository.initial_world()
    world["metrics"] = {"treasury": 4321, "grain": 6789}
    session = GameSession.new_game(world, DemoConfig(initial_year=1500))
    window = MainWindow(repository=repository, session=session)
    qtbot.addWidget(window)
    window.show()
    qtbot.waitUntil(window.isVisible)
    click(qtbot, window.nav_buttons[5])
    return window


def click(qtbot, widget):
    assert widget.isEnabled()
    qtbot.mouseClick(widget, Qt.MouseButton.LeftButton)


def use_editor(qtbot, page, callback):
    """Drive the modal dialog while preserving assertion failures for pytest."""
    failures = []

    def interact():
        dialog = QApplication.activeModalWidget()
        try:
            assert isinstance(dialog, EmperorEditor)
            assert set(dialog.attribute_inputs) == ATTRIBUTE_IDS
            assert set(dialog.skill_inputs) == SKILL_IDS
            callback(dialog)
            assert not dialog.isVisible(), "The editor should close after this interaction."
        except BaseException as error:
            failures.append(error)
        finally:
            if dialog is not None and dialog.isVisible():
                dialog.reject()

    QTimer.singleShot(0, interact)
    click(qtbot, page.edit_button)
    if failures:
        raise failures[0]


def test_all_base_attributes_and_skills_are_available_in_their_tabs(qtbot, emperor_window):
    window = emperor_window
    page = window.emperor_page
    assert window.stack.currentIndex() == 5
    assert page.session is window.session
    assert set(page.attribute_values) == ATTRIBUTE_IDS
    assert set(page.skill_values) == SKILL_IDS
    assert page.tabs.count() == 3
    assert all(value.text() == "50" for value in page.attribute_values.values())
    assert all(value.text() == "0" for value in page.skill_values.values())

    page.tabs.setCurrentIndex(0)
    assert all(value.isVisible() for value in page.attribute_values.values())
    assert not any(value.isVisible() for value in page.skill_values.values())
    page.tabs.setCurrentIndex(1)
    assert all(value.isVisible() for value in page.skill_values.values())
    assert not any(value.isVisible() for value in page.attribute_values.values())
    click(qtbot, page.skill_buttons["calligraphy"])
    assert "书法" in page.detail_title.text()
    calligraphy_description = page.detail_description.text()
    assert calligraphy_description.strip()
    click(qtbot, page.skill_buttons["people_reading"])
    assert "识人" in page.detail_title.text()
    assert page.detail_description.text().strip()
    assert page.detail_description.text() != calligraphy_description


def test_edit_above_100_preserves_unsaved_activity_draft_and_turn_resources(
    qtbot, emperor_window
):
    window = emperor_window
    click(qtbot, window.nav_buttons[1])
    draft = ["exercise", "private", "study"]
    for combo, kind in zip(window.activity_combos, draft):
        index = combo.findData(kind)
        assert index >= 0
        combo.setCurrentIndex(index)
    state_before = copy.deepcopy(window.session.state.to_dict())
    click(qtbot, window.nav_buttons[5])

    def edit(dialog):
        dialog.attribute_inputs["insight"].setText("250")
        dialog.attribute_inputs["constitution"].setText("9999")
        dialog.skill_inputs["people_reading"].setText("100001")
        click(qtbot, dialog.save_button)

    use_editor(qtbot, window.emperor_page, edit)
    state_after = window.session.state.to_dict()
    assert state_after["emperor"]["attributes"]["insight"] == 250
    assert state_after["emperor"]["attributes"]["constitution"] == 9999
    assert state_after["emperor"]["skills"]["people_reading"] == 100001
    assert window.emperor_page.attribute_values["insight"].text() == "250"
    assert window.emperor_page.skill_values["people_reading"].text() == "100001"
    # A profile edit may write an audit log, but cannot advance time, spend actions,
    # alter pending activities, or run world simulation.
    for key in state_before:
        if key not in {"emperor", "logs", "next_id"}:
            assert state_after[key] == state_before[key], key
    click(qtbot, window.nav_buttons[1])
    assert [combo.currentData() for combo in window.activity_combos] == draft


def test_cancel_discards_every_edit(qtbot, emperor_window):
    window = emperor_window
    state_before = copy.deepcopy(window.session.state.to_dict())

    def cancel(dialog):
        dialog.attribute_inputs["logic"].setText("812")
        dialog.skill_inputs["scholarship"].setText("912")
        boxes = dialog.findChildren(QDialogButtonBox)
        cancel_buttons = [box.button(QDialogButtonBox.StandardButton.Cancel) for box in boxes]
        cancel_buttons = [button for button in cancel_buttons if button is not None]
        assert len(cancel_buttons) == 1
        click(qtbot, cancel_buttons[0])

    use_editor(qtbot, window.emperor_page, cancel)
    assert window.session.state.to_dict() == state_before
    assert window.emperor_page.attribute_values["logic"].text() == "50"
    assert window.emperor_page.skill_values["scholarship"].text() == "0"


@pytest.mark.parametrize("invalid", ["-1", "1.2", "", "abc"])
def test_invalid_input_is_atomic_and_can_be_corrected(qtbot, emperor_window, invalid):
    window = emperor_window
    state_before = copy.deepcopy(window.session.state.to_dict())

    def edit(dialog):
        dialog.attribute_inputs["logic"].setText("812")
        dialog.skill_inputs["scholarship"].setText(invalid)
        click(qtbot, dialog.save_button)
        assert dialog.isVisible()
        assert dialog.error_label.text().strip()
        assert window.session.state.to_dict() == state_before
        dialog.skill_inputs["scholarship"].setText("912")
        click(qtbot, dialog.save_button)

    use_editor(qtbot, window.emperor_page, edit)
    assert window.session.state.emperor.attributes["logic"] == 812
    assert window.session.state.emperor.skills["scholarship"] == 912


def test_loading_new_session_refreshes_identity_and_edit_target_and_saves_values(
    qtbot, emperor_window, monkeypatch, tmp_path
):
    window = emperor_window
    old_session = window.session
    old_state = copy.deepcopy(old_session.state.to_dict())
    profile = ScenarioProfile("玩家测试剧本", "自定义天子", "承明", 1499)
    replacement = GameSession.new_game(
        {"metrics": {"treasury": 77}}, DemoConfig(initial_year=1502), profile=profile
    )
    attributes = dict(replacement.state.emperor.attributes)
    skills = dict(replacement.state.emperor.skills)
    attributes["memory"] = 321
    skills["administration"] = 654
    assert replacement.update_emperor_profile(attributes, skills).ok
    source_path = tmp_path / "replacement.json"
    replacement.save_json(source_path)
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *args, **kwargs: (str(source_path), ""))
    window.load_game()

    page = window.emperor_page
    assert window.session is not old_session
    assert page.session is window.session
    page_text = "\n".join(widget.text() for widget in page.findChildren(QLabel))
    assert "自定义天子" in page_text
    assert "承明" in page_text
    assert page.attribute_values["memory"].text() == "321"
    assert page.skill_values["administration"].text() == "654"

    def edit(dialog):
        assert dialog.attribute_inputs["memory"].text() == "321"
        assert dialog.skill_inputs["administration"].text() == "654"
        dialog.skill_inputs["administration"].setText("987")
        click(qtbot, dialog.save_button)

    use_editor(qtbot, page, edit)
    assert old_session.state.to_dict() == old_state
    target_path = tmp_path / "edited.json"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args, **kwargs: (str(target_path), ""))
    window.save_game()
    restored = GameSession.load_json(target_path)
    assert restored.state.emperor.attributes["memory"] == 321
    assert restored.state.emperor.skills["administration"] == 987
    assert restored.state.scenario_profile == profile


def use_status_editor(qtbot, control, expected_type, callback):
    failures = []

    def interact():
        dialog = QApplication.activeModalWidget()
        try:
            assert isinstance(dialog, expected_type)
            callback(dialog)
            assert not dialog.isVisible()
        except BaseException as error:
            failures.append(error)
        finally:
            if dialog is not None and dialog.isVisible():
                dialog.reject()

    QTimer.singleShot(0, interact)
    click(qtbot, control)
    if failures:
        raise failures[0]


def test_health_meters_hide_healthy_parts_and_show_only_recorded_abnormalities(qtbot, emperor_window):
    window = emperor_window
    page = window.emperor_page
    assert page.health_bar.value() == 100
    assert page.pressure_bar.value() == 0
    assert page.body_conditions_widget.isHidden()
    assert window.session.update_emperor_health(100, 100, [BodyCondition("左眼", "失明", "disability")]).ok
    window.refresh()
    assert page.pressure_bar.value() == 100
    assert page.body_conditions_widget.isVisible()
    assert "左眼  ·  残疾：失明" in [item.text() for item in page.body_conditions_widget.findChildren(QLabel)]
    assert window.session.update_emperor_health(100, 0, []).ok
    window.refresh()
    assert page.body_conditions_widget.isHidden()


def test_modifier_page_preserves_base_values_and_refreshes_after_expiry(qtbot, emperor_window):
    window = emperor_window
    page = window.emperor_page
    assert window.session.update_emperor_modifiers([
        EmperorModifier("旧伤", "attribute", "agility", -8),
        EmperorModifier("静心", "skill_effect", "calligraphy", 20, duration="short_term", remaining_turns=1),
    ]).ok
    window.refresh()
    assert page.attribute_values["agility"].text() == "42"
    assert "50" in page.attribute_breakdowns["agility"].text()
    assert "-8" in page.attribute_breakdowns["agility"].text()
    page.tabs.setCurrentIndex(1)
    page.select_skill("calligraphy")
    assert page.skill_values["calligraphy"].text() == "0"
    assert "120%" in page.detail_effect_label.text()
    assert page.detail_effect_label.isVisible()
    window.fill_rest()
    window.advance_turn()
    assert page.detail_effect_label.isHidden()
    assert page.attribute_values["agility"].text() == "42"
    assert len(window.session.state.emperor.modifiers) == 1
    assert window.session.state.emperor.attributes["agility"] == 50
    assert window.session.state.emperor.skills["calligraphy"] == 0


def test_health_editor_ap_change_retains_nonempty_draft_slots(qtbot, emperor_window):
    window = emperor_window
    window.activity_combos[0].setCurrentIndex(window.activity_combos[0].findData("study"))
    window.activity_combos[2].setCurrentIndex(window.activity_combos[2].findData("exercise"))

    def edit(dialog):
        dialog.health_input.setValue(45)
        dialog.pressure_input.setValue(30)
        click(qtbot, dialog.save_button)

    use_status_editor(qtbot, window.emperor_page.health_edit_button, EmperorHealthEditor, edit)
    assert window.session.state.health == 45
    assert window.session.state.emperor.pressure == 30
    assert window.emperor_page.health_bar.value() == 45
    assert len(window.activity_combos) == 2
    assert [combo.currentData() for combo in window.activity_combos] == ["study", "exercise"]
    assert window.session.state.activities == []
    assert window.metrics["ap"].text() == "0 / 2"
    assert window.stack.currentIndex() == 5


def test_modifier_editor_updates_page_without_discarding_activity_draft(qtbot, emperor_window):
    window = emperor_window
    window.activity_combos[1].setCurrentIndex(window.activity_combos[1].findData("study"))

    def edit(dialog):
        dialog.add_modifier(EmperorModifier("精神振奋", "attribute", "logic", 12))
        click(qtbot, dialog.save_button)

    use_status_editor(qtbot, window.emperor_page.modifier_edit_button, EmperorModifierEditor, edit)
    assert window.emperor_page.attribute_values["logic"].text() == "62"
    assert not window.emperor_page.modifiers_empty.isVisible()
    assert [combo.currentData() for combo in window.activity_combos] == [None, "study", None]


def test_pursuit_arranges_a_free_slot_and_only_actual_completion_fulfills(qtbot, emperor_window):
    window = emperor_window
    window.emperor_page.tabs.setCurrentIndex(2)
    assert window.session.add_emperor_objective("desire", "读书", "读一次书", "study", 1).ok
    objective = window.session.state.emperor.objectives[0]
    window.refresh()
    page = window.emperor_page.motives_page
    click(qtbot, page.objective_activity_buttons[objective.id])
    assert window.stack.currentIndex() == 1
    assert [combo.currentData() for combo in window.activity_combos] == ["study", None, None]
    assert objective.progress == 0
    assert window.session.state.activities == []
    window.fill_rest()
    window.advance_turn()
    objective = window.session.state.emperor.objectives[0]
    assert objective.progress == 1
    assert objective.status == "fulfilled"
    assert objective.id not in page.objective_activity_buttons
    assert objective.id not in page.objective_discard_buttons
    assert "1 / 1" in page.objective_progress_labels[objective.id].text()


def test_pursuit_action_does_not_overwrite_a_full_activity_draft(qtbot, emperor_window):
    window = emperor_window
    draft = ["rest", "exercise", "private"]
    for combo, kind in zip(window.activity_combos, draft):
        combo.setCurrentIndex(combo.findData(kind))
    window.emperor_page.activity_requested.emit("study")
    assert [combo.currentData() for combo in window.activity_combos] == draft
    assert window.session.state.activities == []
    assert window.stack.currentIndex() == 1
