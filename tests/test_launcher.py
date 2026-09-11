"""Player-facing paths from the title screen through setup, saves and resume."""

import json
from dataclasses import asdict

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QFileDialog, QPushButton

from dynasty.content import HistoryRepository
from dynasty.ui.launcher import AppWindow
from legacy_support import LegacyDemoConfig


@pytest.fixture
def launcher_factory(qtbot, tmp_path, monkeypatch):
    history = tmp_path / "content" / "data" / "history"
    history.mkdir(parents=True)
    (history / "regions.json").write_text(json.dumps({"records": [
        {"id": "test_region", "name": "测试地区", "longitude": 116, "latitude": 39}
    ]}, ensure_ascii=False), encoding="utf-8")
    repository = HistoryRepository(tmp_path / "content")
    # Existing launcher flows also remain supported for v1 scenarios.
    config_path = tmp_path / "content" / "data" / "config"
    config_path.mkdir()
    (config_path / "framework.json").write_text(json.dumps({
        "schema_version": 1, "world_simulation_enabled": False,
        "demo": asdict(LegacyDemoConfig(initial_year=1500)),
    }), encoding="utf-8")
    directory = tmp_path / "player"
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local-app-data"))

    def create():
        window = AppWindow(repository, data_directory=directory)
        qtbot.addWidget(window)
        window.show()
        qtbot.waitUntil(window.isVisible)
        return window

    return create


def click(qtbot, parent, name):
    control = parent.findChild(QPushButton, name)
    assert control is not None, f"Missing player control: {name}"
    assert control.isEnabled(), f"Disabled player control: {name}"
    qtbot.mouseClick(control, Qt.MouseButton.LeftButton)


def select(combo, value):
    index = combo.findData(value)
    assert index >= 0
    combo.setCurrentIndex(index)


def custom_setup(qtbot, window):
    click(qtbot, window.home_page, "menuStart")
    window.preset_combo.setCurrentIndex(1)
    window.scenario_name.setText("江山新篇")
    window.emperor_name.setText("朱明远")
    window.era_name.setText("景宁")
    window.year.setValue(1511)
    select(window.month, 12)
    select(window.xun, 3)
    window.era_year.setValue(2)
    window.health.setValue(55)


def start_default(qtbot, window):
    click(qtbot, window.home_page, "menuStart")
    click(qtbot, window.setup_page, "beginGame")
    assert window.pages.currentWidget() is window.game
    return window.game


def test_primary_menu_opens_each_destination_and_exit_closes_window(qtbot, launcher_factory):
    window = launcher_factory()
    assert window.pages.currentWidget() is window.home_page
    assert not window.continue_button.isVisible()
    click(qtbot, window.home_page, "menuStart")
    assert window.pages.currentWidget() is window.setup_page
    click(qtbot, window.setup_page, "backHome")
    click(qtbot, window.home_page, "menuLoad")
    assert window.pages.currentWidget() is window.load_page
    assert window.save_table.rowCount() == 0
    assert not window.load_selected_button.isEnabled()
    click(qtbot, window.load_page, "backHome")
    click(qtbot, window.home_page, "menuSettings")
    assert window.pages.currentWidget() is window.settings_page
    settings = window.settings_page.findChildren(QComboBox)
    assert len(settings) == 1 and not settings[0].isEnabled()
    assert "暂未启用" in settings[0].currentText()
    click(qtbot, window.settings_page, "backHome")
    click(qtbot, window.home_page, "menuExit")
    qtbot.waitUntil(lambda: not window.isVisible())


def test_custom_opening_advances_era_and_roundtrips_through_save_list(
    qtbot, launcher_factory, monkeypatch
):
    window = launcher_factory()
    custom_setup(qtbot, window)
    assert "景宁2年" in window.setup_preview.text()
    assert "行动力 2" in window.setup_preview.text()
    click(qtbot, window.setup_page, "beginGame")
    game = window.game
    assert window.pages.currentWidget() is game
    state = game.session.state
    assert state.scenario_profile.scenario_name == "江山新篇"
    assert state.scenario_profile.emperor_name == "朱明远"
    assert state.scenario_profile.era_start_year == 1510
    assert (state.year, state.month, state.xun, state.health, state.ap_capacity) == (1511, 12, 3, 55, 2)
    assert "朱明远" in game.ruler_label.text()
    assert "景宁2年12月下旬" in game.metrics["date"].text()
    # Choosing another year changes the run's clock, not the source material's date.
    world = game.session.world_facts
    assert world["reference_year"] == 1500
    qtbot.mouseClick(game.nav_buttons[1], Qt.MouseButton.LeftButton)
    for combo in game.activity_combos:
        select(combo, "rest")
    click(qtbot, game, "advanceTurn")
    assert "景宁3年1月上旬" in game.metrics["date"].text()
    assert game.session.world_facts == world
    path = window.data_directory / "custom-ruler.json"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args, **kwargs: (str(path), "JSON"))
    save = next(button for button in game.findChildren(QPushButton) if button.text() == "保存")
    qtbot.mouseClick(save, Qt.MouseButton.LeftButton)
    expected = game.session.to_dict()
    assert path.exists()
    click(qtbot, game, "returnMainMenu")
    click(qtbot, window.home_page, "menuLoad")
    assert window.save_table.rowCount() == 1
    assert "江山新篇" in window.save_table.item(0, 0).text()
    assert "朱明远" in window.save_table.item(0, 1).text()
    window.save_table.selectRow(0)
    click(qtbot, window.load_page, "loadSelected")
    assert window.pages.currentWidget() is window.game
    assert window.game.session.to_dict() == expected
    assert window.game.last_save == path


def test_saved_custom_scenario_can_be_selected_after_restarting(qtbot, launcher_factory):
    first = launcher_factory()
    custom_setup(qtbot, first)
    click(qtbot, first.setup_page, "savePreset")
    assert "剧本已保存" in first.setup_feedback.text()
    assert len(list((first.data_directory / "scenarios").glob("*.json"))) == 1
    first.close()
    second = launcher_factory()
    click(qtbot, second.home_page, "menuStart")
    index = second.preset_combo.findText("自定义 · 江山新篇")
    assert index >= 0
    second.preset_combo.setCurrentIndex(index)
    assert "景宁2年" in second.setup_preview.text()
    click(qtbot, second.setup_page, "beginGame")
    assert second.game.session.state.scenario_profile.emperor_name == "朱明远"
    assert second.game.session.state.health == 55
    assert second.game.session.state.year == 1511


@pytest.mark.parametrize("field", ["scenario_name", "emperor_name", "era_name"])
def test_blank_identity_cannot_start_or_persist_a_scenario(qtbot, launcher_factory, field):
    window = launcher_factory()
    custom_setup(qtbot, window)
    getattr(window, field).setText("   ")
    click(qtbot, window.setup_page, "beginGame")
    assert window.pages.currentWidget() is window.setup_page
    assert window.game is None
    assert "非空" in window.setup_feedback.text()
    click(qtbot, window.setup_page, "savePreset")
    assert not list((window.data_directory / "scenarios").glob("*.json"))


def test_era_year_cannot_imply_a_nonpositive_start_year(qtbot, launcher_factory):
    window = launcher_factory()
    custom_setup(qtbot, window)
    window.year.setValue(2)
    window.era_year.setValue(4)
    click(qtbot, window.setup_page, "beginGame")
    assert window.game is None
    assert window.pages.currentWidget() is window.setup_page
    assert "年号起算" in window.setup_feedback.text()


def test_broken_save_and_cancelled_browse_preserve_the_current_game(
    qtbot, launcher_factory, monkeypatch
):
    window = launcher_factory()
    game = start_default(qtbot, window)
    broken = window.data_directory / "broken.json"
    broken.write_text("{not valid json", encoding="utf-8")
    original_bytes = broken.read_bytes()
    expected = game.session.to_dict()
    click(qtbot, game, "returnMainMenu")
    click(qtbot, window.home_page, "menuLoad")
    window.save_table.selectRow(0)
    assert window.save_table.item(0, 4).text() == "无法读取"
    assert not window.load_selected_button.isEnabled()
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *args, **kwargs: (str(broken), "JSON"))
    click(qtbot, window.load_page, "browseSave")
    assert "无法读取此存档" in window.load_feedback.text()
    assert window.game is game
    assert game.session.to_dict() == expected
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *args, **kwargs: ("", ""))
    click(qtbot, window.load_page, "browseSave")
    assert window.pages.currentWidget() is window.load_page
    assert game.session.to_dict() == expected
    assert broken.read_bytes() == original_bytes


def test_return_to_menu_and_cancel_new_game_keeps_current_activity_draft(qtbot, launcher_factory):
    window = launcher_factory()
    game = start_default(qtbot, window)
    qtbot.mouseClick(game.nav_buttons[1], Qt.MouseButton.LeftButton)
    select(game.activity_combos[0], "court")
    select(game.activity_combos[1], "private")
    assert game.session.state.activities == []
    click(qtbot, game, "returnMainMenu")
    assert window.pages.currentWidget() is window.home_page
    assert window.continue_button.isVisible()
    click(qtbot, window.home_page, "menuStart")
    window.emperor_name.setText("尚未登基的新皇帝")
    click(qtbot, window.setup_page, "backHome")
    click(qtbot, window.home_page, "menuContinue")
    assert window.pages.currentWidget() is game
    assert window.game is game
    assert game.session.state.scenario_profile.emperor_name == "朱祐樘"
    assert game.session.state.turn_index == 0
    assert [combo.currentData() for combo in game.activity_combos] == ["court", "private", None]
    assert [activity.kind for activity in game.session.state.activities] == ["court", "private"]


def test_choose_save_folder_then_load_an_external_save(qtbot, launcher_factory, monkeypatch, tmp_path):
    window = launcher_factory()
    game = start_default(qtbot, window)
    directory = tmp_path / "external-saves"
    directory.mkdir()
    path = directory / "travel-save.json"
    game.session.save_json(path)
    expected = game.session.to_dict()
    click(qtbot, game, "returnMainMenu")
    click(qtbot, window.home_page, "menuLoad")
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *args, **kwargs: str(directory))
    click(qtbot, window.load_page, "chooseSaveFolder")
    assert window.save_table.rowCount() == 1
    assert str(directory) in window.folder_label.text()
    window.save_table.selectRow(0)
    click(qtbot, window.load_page, "loadSelected")
    assert window.game.last_save == path
    assert window.game.session.to_dict() == expected
