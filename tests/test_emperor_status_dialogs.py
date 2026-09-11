"""Real health and modifier controls apply complete drafts or no changes at all."""

import copy

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QDialogButtonBox

from legacy_support import LegacyDemoConfig as DemoConfig, LegacyGameSession as GameSession
from dynasty.ui.emperor_status_dialogs import EmperorHealthEditor, EmperorModifierEditor


@pytest.fixture
def session():
    return GameSession.new_game({"metrics": {"treasury": 123}}, DemoConfig(initial_year=1500))


def show(qtbot, dialog):
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.waitUntil(dialog.isVisible)
    return dialog


def click(qtbot, button):
    assert button.isEnabled()
    qtbot.mouseClick(button, Qt.MouseButton.LeftButton)


def choose(combo, value):
    index = combo.findData(value)
    assert index >= 0
    combo.setCurrentIndex(index)


def fill_condition(dialog, row, part, kind, name):
    table = dialog.conditions_table
    table.cellWidget(row, 0).setText(part)
    choose(table.cellWidget(row, 1), kind)
    table.cellWidget(row, 2).setText(name)


def test_health_adds_all_abnormality_types_and_deletes_the_focused_row(qtbot, session):
    dialog = show(qtbot, EmperorHealthEditor(session))
    assert dialog.health_input.value() == 100
    assert dialog.pressure_input.value() == 0
    assert dialog.conditions_table.rowCount() == 0
    for row, values in enumerate([
        ("眼睛", "disease", "眼疾"), ("右手", "disability", "缺指"), ("左腿", "injury", "刀伤"),
    ]):
        click(qtbot, dialog.add_button)
        fill_condition(dialog, row, *values)
    dialog.pressure_input.setValue(37)
    click(qtbot, dialog.save_button)
    assert dialog.result() == QDialog.DialogCode.Accepted
    assert session.state.emperor.pressure == 37
    assert [(item.part, item.kind, item.name) for item in session.state.emperor.body_conditions] == [
        ("眼睛", "disease", "眼疾"), ("右手", "disability", "缺指"), ("左腿", "injury", "刀伤"),
    ]

    second = show(qtbot, EmperorHealthEditor(session))
    click(qtbot, second.conditions_table.cellWidget(0, 0))
    click(qtbot, second.remove_button)
    click(qtbot, second.save_button)
    assert [item.part for item in session.state.emperor.body_conditions] == ["右手", "左腿"]
    empty = show(qtbot, EmperorHealthEditor(session))
    while empty.conditions_table.rowCount():
        empty.conditions_table.setCurrentCell(0, 0)
        click(qtbot, empty.remove_button)
    click(qtbot, empty.save_button)
    assert session.state.emperor.body_conditions == []


def test_health_incomplete_condition_is_atomic_and_can_be_fixed(qtbot, session):
    before = copy.deepcopy(session.state.to_dict())
    dialog = show(qtbot, EmperorHealthEditor(session))
    dialog.health_input.setValue(88)
    dialog.pressure_input.setValue(55)
    click(qtbot, dialog.add_button)
    fill_condition(dialog, 0, "左臂", "injury", "")
    click(qtbot, dialog.save_button)
    assert dialog.isVisible()
    assert dialog.error_label.text().strip()
    assert session.state.to_dict() == before
    dialog.conditions_table.cellWidget(0, 2).setText("擦伤")
    click(qtbot, dialog.save_button)
    assert not dialog.isVisible()
    assert session.state.health == 88
    assert session.state.emperor.pressure == 55
    assert session.state.emperor.body_conditions[0].name == "擦伤"


def test_health_reduction_cannot_discard_an_unsaved_activity_draft(qtbot, session):
    before = copy.deepcopy(session.state.to_dict())
    draft = ["court", "study", "rest"]
    dialog = show(qtbot, EmperorHealthEditor(session, activity_draft=draft))
    dialog.health_input.setValue(40)
    dialog.pressure_input.setValue(80)
    click(qtbot, dialog.save_button)
    assert dialog.isVisible()
    assert "活动" in dialog.error_label.text()
    assert session.state.to_dict() == before
    assert draft == ["court", "study", "rest"]
    dialog.health_input.setValue(80)
    click(qtbot, dialog.save_button)
    assert session.state.health == 80
    assert session.state.ap_capacity == 3
    assert session.state.emperor.pressure == 80


@pytest.mark.parametrize("editor_type", [EmperorHealthEditor, EmperorModifierEditor])
def test_cancel_never_changes_the_game(qtbot, session, editor_type):
    before = copy.deepcopy(session.state.to_dict())
    dialog = show(qtbot, editor_type(session))
    click(qtbot, dialog.add_button)
    if isinstance(dialog, EmperorHealthEditor):
        dialog.health_input.setValue(1)
        fill_condition(dialog, 0, "肺", "disease", "肺病")
    else:
        dialog.modifiers_table.cellWidget(0, 0).setText("未提交修正")
        dialog.modifiers_table.cellWidget(0, 5).setText("-500")
    click(qtbot, dialog.buttons.button(QDialogButtonBox.StandardButton.Cancel))
    assert not dialog.isVisible()
    assert session.state.to_dict() == before


def test_modifier_target_switch_and_signed_values_preserve_learned_skills(qtbot, session):
    before_attributes = dict(session.state.emperor.attributes)
    before_skills = dict(session.state.emperor.skills)
    dialog = show(qtbot, EmperorModifierEditor(session))
    click(qtbot, dialog.add_button)
    table = dialog.modifiers_table
    assert table.cellWidget(0, 4).count() == 13
    assert not table.cellWidget(0, 6).isEnabled()
    table.cellWidget(0, 0).setText("疲惫")
    table.cellWidget(0, 1).setText("<状态来源>")
    choose(table.cellWidget(0, 3), "skill_effect")
    assert table.cellWidget(0, 4).count() == 6
    assert table.cellWidget(0, 4).findData("logic") == -1
    choose(table.cellWidget(0, 4), "people_reading")
    table.cellWidget(0, 5).setText("-30")
    choose(table.cellWidget(0, 2), "short_term")
    assert table.cellWidget(0, 6).isEnabled()
    table.cellWidget(0, 6).setText("2")
    choose(table.cellWidget(0, 2), "long_term")
    assert not table.cellWidget(0, 6).isEnabled()
    choose(table.cellWidget(0, 2), "short_term")
    assert table.cellWidget(0, 6).text() == "2"
    click(qtbot, dialog.add_button)
    table.cellWidget(1, 0).setText("强健")
    choose(table.cellWidget(1, 4), "strength")
    table.cellWidget(1, 5).setText("+150")
    click(qtbot, dialog.save_button)
    assert not dialog.isVisible()
    assert session.state.emperor.attributes == before_attributes
    assert session.state.emperor.skills == before_skills
    first, second = session.state.emperor.modifiers
    assert (first.target_type, first.target, first.amount, first.remaining_turns) == (
        "skill_effect", "people_reading", -30, 2,
    )
    assert first.source == "<状态来源>"
    assert (second.target, second.amount, second.duration, second.remaining_turns) == (
        "strength", 150, "long_term", None,
    )
    remove = show(qtbot, EmperorModifierEditor(session))
    click(qtbot, remove.modifiers_table.cellWidget(0, 0))
    click(qtbot, remove.remove_button)
    click(qtbot, remove.save_button)
    assert [item.name for item in session.state.emperor.modifiers] == ["强健"]


@pytest.mark.parametrize("invalid", ["1.5", "-", "abc"])
def test_modifier_invalid_value_or_duration_never_partly_commits(qtbot, session, invalid):
    before = copy.deepcopy(session.state.to_dict())
    dialog = show(qtbot, EmperorModifierEditor(session))
    for row in range(2):
        click(qtbot, dialog.add_button)
        dialog.modifiers_table.cellWidget(row, 0).setText(f"修正 {row + 1}")
        dialog.modifiers_table.cellWidget(row, 5).setText("10")
    table = dialog.modifiers_table
    table.cellWidget(1, 5).setText(invalid)
    click(qtbot, dialog.save_button)
    assert dialog.isVisible()
    assert dialog.error_label.text().strip()
    assert session.state.to_dict() == before
    table.cellWidget(1, 5).setText("-20")
    choose(table.cellWidget(1, 2), "short_term")
    table.cellWidget(1, 6).setText("0")
    click(qtbot, dialog.save_button)
    assert dialog.isVisible()
    assert session.state.to_dict() == before
    table.cellWidget(1, 6).setText("3")
    click(qtbot, dialog.save_button)
    assert not dialog.isVisible()
    assert len(session.state.emperor.modifiers) == 2
    assert session.state.emperor.modifiers[1].remaining_turns == 3
