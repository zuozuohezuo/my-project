"""The emperor's personal record and an explicit, unrestricted numeric editor."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup, QDialog, QDialogButtonBox, QFormLayout, QFrame, QGridLayout,
    QGroupBox, QHBoxLayout, QLabel, QLineEdit, QProgressBar, QPushButton, QScrollArea,
    QSizePolicy, QTabWidget, QVBoxLayout, QWidget,
)

from dynasty.core import GameSession
from dynasty.core.emperor import ATTRIBUTE_DEFINITIONS, ATTRIBUTE_GROUPS, SKILL_DEFINITIONS
from dynasty.core.motives import PERSONALITY_DIMENSIONS


def text_label(text: str = "", name: str = "") -> QLabel:
    widget = QLabel(text)
    widget.setTextFormat(Qt.TextFormat.PlainText)
    widget.setWordWrap(True)
    widget.setObjectName(name)
    return widget


def panel() -> tuple[QFrame, QVBoxLayout]:
    widget = QFrame()
    widget.setObjectName("card")
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(18, 16, 18, 16)
    layout.setSpacing(10)
    return widget, layout


def scroll_content() -> tuple[QScrollArea, QVBoxLayout]:
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    content = QWidget()
    layout = QVBoxLayout(content)
    layout.setContentsMargins(16, 14, 16, 14)
    layout.setSpacing(14)
    scroll.setWidget(content)
    return scroll, layout


def numeric_label(name: str) -> QLabel:
    widget = text_label("", name)
    widget.setWordWrap(False)
    widget.setMinimumWidth(0)
    widget.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
    widget.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    return widget


def show_number(widget: QLabel, value: int) -> None:
    rendered = str(value)
    widget.setText(rendered)
    widget.setToolTip(rendered)


class EmperorEditor(QDialog):
    """Collect a full draft, committing it only after every field validates."""

    def __init__(self, session: GameSession, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.session = session
        self.result_message = ""
        self.setWindowTitle("手动调整 · 皇帝数值")
        self.resize(800, 610)
        self.setMinimumSize(720, 520)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(14)
        layout.addWidget(text_label("手动调整", "title"))
        layout.addWidget(text_label(
            "自由修改基础属性与技能，不消耗行动力或诏书。应用后记得保存游戏。", "subtitle"))
        self.tabs = QTabWidget()
        self.attribute_inputs: dict[str, QLineEdit] = {}
        self.skill_inputs: dict[str, QLineEdit] = {}
        attributes, attribute_layout = scroll_content()
        groups = QHBoxLayout()
        groups.setSpacing(12)
        for group_id, group_name in ATTRIBUTE_GROUPS:
            box = QGroupBox(group_name)
            form = QFormLayout(box)
            form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
            form.setSpacing(12)
            for definition in ATTRIBUTE_DEFINITIONS:
                if definition.group == group_id:
                    entry = self._input(session.state.emperor.attributes[definition.id], definition)
                    self.attribute_inputs[definition.id] = entry
                    form.addRow(definition.label, entry)
            groups.addWidget(box, 1, Qt.AlignmentFlag.AlignTop)
        attribute_layout.addLayout(groups)
        attribute_layout.addStretch()
        self.tabs.addTab(attributes, "基础属性 · 13")
        skills, skill_layout = scroll_content()
        grid = QGridLayout()
        for index, definition in enumerate(SKILL_DEFINITIONS):
            box = QWidget()
            form = QFormLayout(box)
            form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
            entry = self._input(session.state.emperor.skills[definition.id], definition)
            self.skill_inputs[definition.id] = entry
            form.addRow(definition.label, entry)
            grid.addWidget(box, index // 2, index % 2)
        skill_layout.addLayout(grid)
        skill_layout.addWidget(text_label("技能不设固定上限，也不受基础属性数值封顶。", "subtitle"))
        skill_layout.addStretch()
        self.tabs.addTab(skills, "技能 · 6")
        layout.addWidget(self.tabs, 1)
        self.error_label = text_label("请输入非负整数；可以填写超过 100 的数值。", "feedback")
        layout.addWidget(self.error_label)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        self.save_button = self.buttons.addButton("应用修改", QDialogButtonBox.ButtonRole.AcceptRole)
        self.save_button.setProperty("primary", True)
        self.save_button.setObjectName("applyEmperorValues")
        self.buttons.accepted.connect(self.apply_values)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

    @staticmethod
    def _input(value: int, definition) -> QLineEdit:
        widget = QLineEdit(str(value))
        widget.setObjectName(f"edit_{definition.id}")
        widget.setAccessibleName(definition.label)
        widget.setToolTip(definition.description)
        widget.setMinimumWidth(65)
        return widget

    def apply_values(self) -> None:
        values: list[dict[str, int]] = []
        for tab_index, (definitions, entries) in enumerate((
            (ATTRIBUTE_DEFINITIONS, self.attribute_inputs),
            (SKILL_DEFINITIONS, self.skill_inputs),
        )):
            parsed = {}
            for definition in definitions:
                entry = entries[definition.id]
                raw = entry.text().strip()
                try:
                    if not raw or not raw.isascii() or not raw.isdecimal():
                        raise ValueError
                    parsed[definition.id] = int(raw)
                except ValueError:
                    self.tabs.setCurrentIndex(tab_index)
                    self.error_label.setText(f"{definition.label}：请输入有效的非负整数。尚未应用任何修改。")
                    self.error_label.setProperty("error", True)
                    self.error_label.style().unpolish(self.error_label)
                    self.error_label.style().polish(self.error_label)
                    entry.setFocus()
                    entry.selectAll()
                    return
            values.append(parsed)
        result = self.session.update_emperor_profile(values[0], values[1])
        if result.ok:
            self.result_message = result.message
            self.accept()
        else:
            self.error_label.setText(result.message)


class EmperorPage(QWidget):
    profile_updated = Signal(str)
    health_updated = Signal(str)
    activity_requested = Signal(str)

    def __init__(self, session: GameSession) -> None:
        super().__init__()
        self.session = session
        self.attribute_values: dict[str, QLabel] = {}
        self.attribute_breakdowns: dict[str, QLabel] = {}
        self.skill_values: dict[str, QLabel] = {}
        self.skill_effect_labels: dict[str, QLabel] = {}
        self.skill_buttons: dict[str, QPushButton] = {}
        self.activity_draft_provider = lambda: []
        self.selected_skill = SKILL_DEFINITIONS[0].id
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        identity, _ = panel()
        # Replace the panel's vertical arrangement with one compact identity row.
        identity_row = QHBoxLayout()
        identity.layout().addLayout(identity_row)
        seal = text_label("御", "emperorSeal")
        seal.setAlignment(Qt.AlignmentFlag.AlignCenter)
        seal.setFixedSize(48, 48)
        identity_row.addWidget(seal)
        identity_row.addSpacing(8)
        ruler = QVBoxLayout()
        ruler.setSpacing(3)
        self.name_label = text_label("", "emperorName")
        self.identity_label = text_label("", "subtitle")
        ruler.addWidget(self.name_label)
        ruler.addWidget(self.identity_label)
        identity_row.addLayout(ruler, 1)
        state_box = QVBoxLayout()
        state_box.setSpacing(4)
        self.health_label = text_label()
        self.traits_label = text_label("性格 · 尚未设定", "subtitle")
        self.traits_label.setMaximumWidth(220)
        state_box.addWidget(self.health_label)
        state_box.addWidget(self.traits_label)
        identity_row.addLayout(state_box)
        identity_row.addSpacing(16)
        self.edit_button = QPushButton("手动调整…")
        self.edit_button.setObjectName("editEmperorProfile")
        self.edit_button.setToolTip("自由修改基础属性和技能，保留玩家的作弊入口。")
        self.edit_button.clicked.connect(self.edit_values)
        identity_row.addWidget(self.edit_button)
        layout.addWidget(identity)
        self.tabs = QTabWidget()
        self.tabs.setObjectName("emperorTabs")
        self.tabs.addTab(self._attributes_tab(), "基础属性 · 13")
        self.tabs.addTab(self._skills_tab(), "技能 · 6")
        from dynasty.ui.emperor_motives_page import EmperorMotivesPage

        self.motives_page = EmperorMotivesPage(session)
        self.motives_page.updated.connect(self._motives_updated)
        self.motives_page.activity_requested.connect(self.activity_requested.emit)
        self.tabs.addTab(self.motives_page, "性格与追求")
        layout.addWidget(self.tabs, 1)
        layout.addWidget(text_label(
            "演示初值：基础属性 50、技能 0，不代表历史评价。学习成长与事件判定尚未运行。", "subtitle"))
        self.refresh(session)

    def _attributes_tab(self) -> QScrollArea:
        scroll, layout = scroll_content()
        layout.addWidget(text_label(
            "基础属性展示当前值；存在修正时，下方同时列出底值与变化。悬停属性名称可查看释义。", "subtitle"))
        body = QHBoxLayout()
        body.setSpacing(16)
        attributes = QVBoxLayout()
        attributes.setSpacing(12)
        columns = QHBoxLayout()
        columns.setSpacing(12)
        for group_id, group_name in ATTRIBUTE_GROUPS:
            frame, group_layout = panel()
            group_layout.setSpacing(7)
            definitions = [item for item in ATTRIBUTE_DEFINITIONS if item.group == group_id]
            heading = QHBoxLayout()
            heading.addWidget(text_label(group_name, "sectionTitle"), 1)
            heading.addWidget(text_label(f"{len(definitions):02} 项", "eyebrow"))
            group_layout.addLayout(heading)
            for index, definition in enumerate(definitions):
                if index:
                    line = QFrame()
                    line.setObjectName("emperorRule")
                    line.setFixedHeight(1)
                    group_layout.addWidget(line)
                row = QHBoxLayout()
                wording = QVBoxLayout()
                wording.setSpacing(3)
                name = text_label(definition.label, "emperorAttributeName")
                name.setToolTip(definition.description)
                wording.addWidget(name)
                breakdown = text_label("", "emperorHint")
                self.attribute_breakdowns[definition.id] = breakdown
                wording.addWidget(breakdown)
                row.addLayout(wording, 2)
                value = numeric_label("emperorAttributeValue")
                value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                value.setAccessibleName(f"{definition.label}数值")
                self.attribute_values[definition.id] = value
                row.addWidget(value, 1)
                group_layout.addLayout(row)
            group_layout.addStretch()
            columns.addWidget(frame, 1)
        attributes.addLayout(columns)
        attributes.addWidget(text_label(
            "属性修正与底值分开保存。技能效果修正可在技能页查看，不改变已学会的熟练度。", "subtitle"))
        attributes.addStretch()
        body.addLayout(attributes, 2)
        status = QVBoxLayout()
        status.setSpacing(12)
        status.addWidget(self._health_panel())
        status.addWidget(self._modifier_panel())
        status.addStretch()
        body.addLayout(status, 1)
        layout.addLayout(body)
        layout.addStretch()
        return scroll

    def _health_panel(self) -> QFrame:
        frame, layout = panel()
        heading = QHBoxLayout()
        heading.addWidget(text_label("健康", "sectionTitle"), 1)
        self.health_edit_button = QPushButton("调整…")
        self.health_edit_button.setObjectName("editEmperorHealth")
        self.health_edit_button.clicked.connect(self.edit_health)
        heading.addWidget(self.health_edit_button)
        layout.addLayout(heading)
        self.health_value_label = text_label()
        self.pressure_value_label = text_label()
        self.health_bar = QProgressBar()
        self.pressure_bar = QProgressBar()
        for name, value_label, bar in [
            ("emperorHealthBar", self.health_value_label, self.health_bar),
            ("emperorPressureBar", self.pressure_value_label, self.pressure_bar),
        ]:
            layout.addWidget(value_label)
            bar.setObjectName(name)
            bar.setRange(0, 100)
            bar.setTextVisible(False)
            bar.setFixedHeight(7)
            layout.addWidget(bar)
        self.body_conditions_widget = QWidget()
        self.body_conditions_layout = QVBoxLayout(self.body_conditions_widget)
        self.body_conditions_layout.setContentsMargins(0, 5, 0, 0)
        self.body_conditions_layout.setSpacing(6)
        layout.addWidget(self.body_conditions_widget)
        return frame

    def _modifier_panel(self) -> QFrame:
        frame, layout = panel()
        heading = QHBoxLayout()
        self.modifiers_title = text_label("当前修正", "sectionTitle")
        heading.addWidget(self.modifiers_title, 1)
        self.modifier_edit_button = QPushButton("管理…")
        self.modifier_edit_button.setObjectName("editEmperorModifiers")
        self.modifier_edit_button.clicked.connect(self.edit_modifiers)
        heading.addWidget(self.modifier_edit_button)
        layout.addLayout(heading)
        self.modifiers_empty = text_label("暂无修正", "subtitle")
        layout.addWidget(self.modifiers_empty)
        self.modifiers_widget = QWidget()
        self.modifiers_layout = QVBoxLayout(self.modifiers_widget)
        self.modifiers_layout.setContentsMargins(0, 0, 0, 0)
        self.modifiers_layout.setSpacing(10)
        layout.addWidget(self.modifiers_widget)
        layout.addWidget(text_label("长期持续至移除；短期每完成一旬递减。", "emperorHint"))
        return frame

    @staticmethod
    def _clear_rows(layout: QVBoxLayout) -> None:
        while layout.count():
            widget = layout.takeAt(0).widget()
            if widget:
                widget.hide()
                widget.deleteLater()

    def _refresh_status(self) -> None:
        state = self.session.state
        emperor = state.emperor
        self.health_value_label.setText(f"整体健康度  {state.health} / 100")
        self.pressure_value_label.setText(f"压力  {emperor.pressure} / 100")
        self.health_bar.setValue(state.health)
        self.pressure_bar.setValue(emperor.pressure)
        self._clear_rows(self.body_conditions_layout)
        kinds = {"disease": "疾病", "disability": "残疾", "injury": "伤势"}
        for condition in emperor.body_conditions:
            wording = f"{condition.part}  ·  {kinds[condition.kind]}：{condition.name}"
            row = text_label(wording, "emperorCondition")
            self.body_conditions_layout.addWidget(row)
        self.body_conditions_widget.setVisible(bool(emperor.body_conditions))
        self._clear_rows(self.modifiers_layout)
        self.modifiers_title.setText("当前修正" + (f" · {len(emperor.modifiers)}" if emperor.modifiers else ""))
        self.modifiers_empty.setVisible(not emperor.modifiers)
        self.modifiers_widget.setVisible(bool(emperor.modifiers))
        names = {item.id: item.label for item in (*ATTRIBUTE_DEFINITIONS, *SKILL_DEFINITIONS)}
        for modifier in emperor.modifiers:
            row = QFrame()
            row.setObjectName("emperorModifierRow")
            content = QVBoxLayout(row)
            content.setContentsMargins(10, 8, 10, 8)
            content.setSpacing(4)
            heading = QHBoxLayout()
            name = text_label(modifier.name, "emperorAttributeName")
            heading.addWidget(name, 1)
            duration = "长期" if modifier.duration == "long_term" else f"余 {modifier.remaining_turns} 旬"
            heading.addWidget(text_label(duration, "emperorHint"))
            content.addLayout(heading)
            target = names[modifier.target]
            effect = (f"{target} {modifier.amount:+d}" if modifier.target_type == "attribute"
                      else f"{target}效果 {modifier.amount:+d}%")
            content.addWidget(text_label(effect, "emperorModifierEffect"))
            if modifier.source:
                content.addWidget(text_label(f"来源：{modifier.source}", "emperorHint"))
            self.modifiers_layout.addWidget(row)

    def _skills_tab(self) -> QScrollArea:
        scroll, layout = scroll_content()
        layout.addWidget(text_label("技能可经学习增长；同等技能水平具有相同的常规表现。选择技能查看说明。", "subtitle"))
        content = QHBoxLayout()
        content.setSpacing(16)
        grid = QGridLayout()
        grid.setSpacing(12)
        self.skill_group = QButtonGroup(self)
        self.skill_group.setExclusive(True)
        for index, definition in enumerate(SKILL_DEFINITIONS):
            tile = QPushButton()
            tile.setObjectName("emperorSkill")
            tile.setCheckable(True)
            tile.setMinimumHeight(100)
            tile.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            tile.setAccessibleName(definition.label)
            tile_layout = QVBoxLayout(tile)
            tile_layout.setContentsMargins(16, 12, 16, 12)
            heading = QHBoxLayout()
            heading.addWidget(text_label(definition.label, "sectionTitle"), 2)
            value = numeric_label("emperorSkillValue")
            value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            heading.addWidget(value, 1)
            tile_layout.addLayout(heading)
            tile_layout.addWidget(text_label(definition.description, "emperorHint"))
            effect_label = text_label("", "emperorModifierEffect")
            self.skill_effect_labels[definition.id] = effect_label
            tile_layout.addWidget(effect_label)
            for child in tile.findChildren(QLabel):
                child.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            self.skill_values[definition.id] = value
            self.skill_buttons[definition.id] = tile
            self.skill_group.addButton(tile)
            tile.clicked.connect(lambda _=False, skill_id=definition.id: self.select_skill(skill_id))
            grid.addWidget(tile, index // 2, index % 2)
        content.addLayout(grid, 3)
        detail, detail_layout = panel()
        detail_layout.addWidget(text_label("技能详解", "eyebrow"))
        title_row = QHBoxLayout()
        self.detail_title = text_label("", "emperorName")
        self.detail_value = numeric_label("emperorSkillValue")
        self.detail_value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        title_row.addWidget(self.detail_title, 2)
        title_row.addWidget(self.detail_value, 1)
        detail_layout.addLayout(title_row)
        self.detail_description = text_label("", "subtitle")
        detail_layout.addWidget(self.detail_description)
        self.detail_effect_label = text_label("", "emperorModifierEffect")
        detail_layout.addWidget(self.detail_effect_label)
        for title, explanation in [
            ("常规表现", "同等技能、相同修正下，正常表现相同。"),
            ("学习成长", "增长速度受基础属性和性格影响。"),
            ("事件判定", "技能与相关基础属性共同参与判定。"),
        ]:
            detail_layout.addWidget(text_label(title, "emperorAttributeName"))
            detail_layout.addWidget(text_label(explanation, "emperorHint"))
        detail_layout.addStretch()
        detail_layout.addWidget(text_label("成长不封顶 · 基础属性不限制技能上限", "notice"))
        content.addWidget(detail, 2)
        layout.addLayout(content)
        layout.addStretch()
        return scroll

    def refresh(self, session: GameSession) -> None:
        self.session = session
        state = session.state
        profile = state.scenario_profile
        self.name_label.setText(profile.emperor_name)
        self.identity_label.setText(f"{profile.scenario_name}  /  {state.era_date_label}")
        self.health_label.setText(f"健康  {state.health}   ·   每旬行动力  {state.ap_capacity}")
        prominent = sorted(PERSONALITY_DIMENSIONS,
                           key=lambda item: abs(state.emperor.personality[item.id] - 50), reverse=True)
        tendencies = [item.left if state.emperor.personality[item.id] < 50 else item.right
                      for item in prominent if abs(state.emperor.personality[item.id] - 50) >= 10]
        self.traits_label.setText("性格 · " + ("、".join(tendencies[:3]) or "倾向居中"))
        if state.emperor.traits:
            self.traits_label.setToolTip("原有特质记录：" + "、".join(state.emperor.traits))
        else:
            self.traits_label.setToolTip("九组稳定性格详见性格与追求页签；默认居中为演示初值。")
        for key, widget in self.attribute_values.items():
            base = state.emperor.attributes[key]
            bonus = state.emperor.attribute_bonus(key)
            show_number(widget, state.emperor.effective_attribute(key))
            widget.setToolTip(f"底值 {base}；修正 {bonus:+d}；当前 {state.emperor.effective_attribute(key)}")
            breakdown = self.attribute_breakdowns[key]
            breakdown.setText(f"底值 {base} · {bonus:+d}")
            breakdown.setVisible(bool(bonus))
        for key, widget in self.skill_values.items():
            show_number(widget, state.emperor.skills[key])
            bonus = state.emperor.skill_effect_bonus(key)
            effect = self.skill_effect_labels[key]
            effect.setText(f"技能效果 {state.emperor.skill_effect_percent(key)}% · 修正 {bonus:+d}%")
            effect.setVisible(bool(bonus))
        self._refresh_status()
        self.motives_page.refresh(session)
        self.select_skill(self.selected_skill)

    def select_skill(self, skill_id: str) -> None:
        definition = next(item for item in SKILL_DEFINITIONS if item.id == skill_id)
        self.selected_skill = skill_id
        self.skill_buttons[skill_id].setChecked(True)
        self.detail_title.setText(definition.label)
        self.detail_description.setText(definition.description)
        show_number(self.detail_value, self.session.state.emperor.skills[skill_id])
        emperor = self.session.state.emperor
        bonus = emperor.skill_effect_bonus(skill_id)
        self.detail_effect_label.setText(
            f"技能效果 {emperor.skill_effect_percent(skill_id)}% · 修正 {bonus:+d}%\n熟练度保持不变")
        self.detail_effect_label.setVisible(bool(bonus))

    def edit_values(self) -> None:
        dialog = EmperorEditor(self.session, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh(self.session)
            self.profile_updated.emit(dialog.result_message + " 请保存游戏以保留修改。")
        dialog.deleteLater()

    def edit_health(self) -> None:
        from dynasty.ui.emperor_status_dialogs import EmperorHealthEditor

        dialog = EmperorHealthEditor(self.session, self, activity_draft=self.activity_draft_provider())
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh(self.session)
            self.health_updated.emit(dialog.result_message + " 请保存游戏以保留修改。")
        dialog.deleteLater()

    def edit_modifiers(self) -> None:
        from dynasty.ui.emperor_status_dialogs import EmperorModifierEditor

        dialog = EmperorModifierEditor(self.session, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh(self.session)
            self.profile_updated.emit(dialog.result_message + " 请保存游戏以保留修改。")
        dialog.deleteLater()

    def _motives_updated(self, message: str) -> None:
        self.refresh(self.session)
        self.profile_updated.emit(message + " 请保存游戏以保留修改。")
