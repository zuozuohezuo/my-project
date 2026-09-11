"""Title screen, scenario setup and save selection for the desktop game."""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QAbstractItemView, QAbstractSpinBox, QComboBox, QFileDialog, QFormLayout, QHBoxLayout,
    QLineEdit, QMainWindow, QScrollArea, QSpinBox, QStackedWidget,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from dynasty.content import HistoryRepository, create_county_demo, load_demo_config, user_data_dir
from dynasty.core import GameSession, ScenarioProfile
from dynasty.ui.main_window import MainWindow, button, card, label
from dynasty.ui.theme import STYLE, initialize_fonts


FILE_ERRORS = (OSError, ValueError, TypeError, KeyError, AttributeError, IndexError, OverflowError)


class PalaceArt(QWidget):
    """Small vector illustration that scales with the title panel."""

    def __init__(self):
        super().__init__()
        self.setMinimumHeight(175)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.scale(self.width() / 580, self.height() / 250)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#b9ac81"))
        painter.drawEllipse(QPointF(431, 62), 30, 30)
        for color, offset in [("#244a44", 0), ("#2b554c", 45)]:
            mountain = QPainterPath(QPointF(0, 190 + offset))
            mountain.cubicTo(90, 95 + offset, 110, 147 + offset, 177, 121 + offset)
            mountain.cubicTo(261, 202 + offset, 343, 97 + offset, 423, 121 + offset)
            mountain.cubicTo(489, 148 + offset, 523, 111 + offset, 580, 156 + offset)
            mountain.lineTo(580, 250)
            mountain.lineTo(0, 250)
            painter.setBrush(QColor(color))
            painter.drawPath(mountain)
        painter.setPen(QPen(QColor("#b9bd9b"), 1.5))
        painter.setBrush(QColor("#193b36"))
        painter.drawRect(195, 153, 190, 66)
        roof = QPainterPath(QPointF(161, 151))
        roof.cubicTo(204, 150, 246, 130, 290, 101)
        roof.cubicTo(334, 130, 376, 150, 419, 151)
        roof.lineTo(398, 163)
        roof.lineTo(183, 163)
        roof.closeSubpath()
        painter.drawPath(roof)
        for x in [207, 243, 278, 303, 339, 373]:
            painter.drawLine(x, 165, x, 217)
        painter.drawLine(171, 220, 409, 220)
        painter.drawLine(158, 228, 422, 228)
        painter.drawLine(141, 237, 439, 237)
        painter.end()


class AppWindow(QMainWindow):
    def __init__(self, repository: HistoryRepository | None = None, data_directory: Path | None = None):
        super().__init__()
        initialize_fonts()
        self.repository = repository or HistoryRepository()
        self.data_directory = data_directory or user_data_dir()
        self.data_directory.mkdir(parents=True, exist_ok=True)
        self.save_directory = self.data_directory
        self.game: MainWindow | None = None
        self.setWindowTitle("御览 · 王朝人生")
        self.resize(1480, 940)
        self.setMinimumSize(1180, 800)
        self.setStyleSheet(STYLE + """
            QWidget#launchPage { background: #f2f0e9; }
            QWidget#titlePanel { background: #173c39; border-radius: 14px; }
            QWidget#titlePanel QLabel { color: #dce3d3; background: transparent; }
            QLabel#heroTitle { font-size: 76px; color: #f0e6c9; font-weight: 600; }
            QLabel#heroCopy { font-size: 18px; color: #c2d2bf; }
            QLabel#menuHeading { font-size: 32px; font-weight: 600; color: #25483f; }
            QLabel#previewName { font-size: 30px; font-weight: 600; }
            QPushButton#menuStart, QPushButton#menuLoad, QPushButton#menuSettings,
            QPushButton#menuExit, QPushButton#menuContinue {
                text-align: left; padding: 15px 20px; font-size: 17px; min-height: 29px;
            }
        """)
        self.pages = QStackedWidget()
        self.setCentralWidget(self.pages)
        self.home_page = self._home()
        self.setup_page = self._setup()
        self.load_page = self._load_page()
        self.settings_page = self._settings()
        self.county_setup_page = self._county_setup()
        for page in [self.home_page, self.setup_page, self.load_page, self.settings_page, self.county_setup_page]:
            self.pages.addWidget(page)
        self.show_home()

    def _page(self, title: str, subtitle: str):
        page = QWidget()
        page.setObjectName("launchPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(55, 38, 55, 35)
        layout.setSpacing(20)
        top = QHBoxLayout()
        top.addWidget(label("御览  /  王朝人生", "eyebrow"), 1)
        top.addWidget(button("← 返回主菜单", self.show_home, name="backHome"))
        layout.addLayout(top)
        layout.addWidget(label(title, "menuHeading"))
        layout.addWidget(label(subtitle, "subtitle"))
        return page, layout

    def _home(self):
        page = QWidget()
        page.setObjectName("launchPage")
        row = QHBoxLayout(page)
        row.setContentsMargins(48, 42, 48, 42)
        row.setSpacing(68)
        panel = QWidget()
        panel.setObjectName("titlePanel")
        hero = QVBoxLayout(panel)
        hero.setContentsMargins(48, 42, 48, 28)
        hero.addWidget(label("王 朝 人 生  /  IMPERIAL CHRONICLES", "eyebrow"))
        hero.addStretch(1)
        hero.addWidget(label("御览", "heroTitle"))
        hero.addWidget(label("执掌山河，落笔春秋。", "heroCopy"))
        hero.addSpacing(14)
        hero.addWidget(label("一旬之间，朝野万事。\n从一道诏令，开启你的王朝故事。"))
        hero.addStretch(1)
        hero.addWidget(PalaceArt(), 2)
        hero.addWidget(label("始于史实  ·  续写王朝"))
        row.addWidget(panel, 6)
        menu = QVBoxLayout()
        menu.setSpacing(14)
        menu.addStretch(1)
        menu.addWidget(label("开启一段帝王生涯", "menuHeading"))
        menu.addWidget(label("选择新的开局，或接续存档中的故事。", "subtitle"))
        menu.addSpacing(25)
        self.continue_button = button("继续游戏   →", self.continue_game, name="menuContinue")
        menu.addWidget(self.continue_button)
        menu.addWidget(button("开始游戏   →", self.show_setup, primary=True, name="menuStart"))
        menu.addWidget(button("县级经济试玩   →", self.show_county_setup, name="menuCountyDemo"))
        menu.addWidget(button("读取游戏", self.show_load, name="menuLoad"))
        menu.addWidget(button("设置", self.show_settings, name="menuSettings"))
        menu.addWidget(button("退出", self.close, name="menuExit"))
        menu.addSpacing(18)
        menu.addWidget(label("当前可用：明代资料开局 · 自定义剧本", "subtitle"))
        menu.addStretch(1)
        menu.addWidget(label("御览  /  开发预览版", "eyebrow"))
        row.addLayout(menu, 4)
        return page

    def _county_setup(self):
        page, layout = self._page("清河县 · 经济试玩", "一个虚构的县，用来观察生产、消费和人口的逐旬变化。")
        frame, body = card("选择初始情境")
        self.county_scenario_combo = QComboBox()
        self.county_scenario_combo.setObjectName("countyScenario")
        for key, title in [("normal", "正常供给"), ("shortage", "持续缺粮"),
                           ("input_shortage", "生产投入不足")]:
            self.county_scenario_combo.addItem(title, key)
        body.addWidget(self.county_scenario_combo)
        body.addWidget(label("正常供给：观察生产周期、收获和消费。\n"
                             "持续缺粮：观察财富层级的不同惩罚、死亡与降层。\n"
                             "生产投入不足：观察缺少原料如何限制生产。", "subtitle"))
        body.addWidget(label("人口按七类职业统计，财富由收入评定。默认劳动力比例50%，年出生率3%、年自然死亡率2%。"))
        body.addWidget(label("居民共用民间资源池，官府和皇家资源分别核算。初值均为演示参数。"))
        body.addWidget(label("进入后可在旬初调整资源、人口参数与群体收入，或休息一旬观察变化。也可进入起居与朝政按原流程行动。"))
        layout.addWidget(frame)
        self.county_replace_notice = label("开始试玩会替换当前未保存的进度；可返回原局先保存。", "notice")
        layout.addWidget(self.county_replace_notice)
        self.county_setup_feedback = label("", "feedback")
        layout.addWidget(self.county_setup_feedback)
        layout.addStretch()
        layout.addWidget(button("建立清河县 · 开始试玩 →", self.start_county_demo,
                                primary=True, name="beginCountyDemo"))
        return page

    def show_county_setup(self):
        self.county_replace_notice.setVisible(self.game is not None)
        self.county_setup_feedback.setText("")
        self.pages.setCurrentWidget(self.county_setup_page)

    def start_county_demo(self):
        try:
            session = create_county_demo(self.county_scenario_combo.currentData(), self.repository.root)
            self.enter_game(session)
            self.game.show_page(6)
        except FILE_ERRORS as error:
            self.county_setup_feedback.setText(f"无法开启县级试玩：{error}")

    def _setup(self):
        page, layout = self._page("设定你的开局", "选择剧本，写下皇帝与年号，再从指定的年份开始。")
        row = QHBoxLayout()
        row.setSpacing(25)
        frame, form_layout = card("剧本与帝王")
        self.preset_combo = QComboBox()
        self.preset_combo.setObjectName("scenarioPreset")
        self.preset_combo.currentIndexChanged.connect(self._preset_selected)
        form = QFormLayout()
        form.setVerticalSpacing(15)
        self.scenario_name = QLineEdit()
        self.scenario_name.setMaxLength(80)
        self.emperor_name = QLineEdit()
        self.emperor_name.setMaxLength(40)
        self.era_name = QLineEdit()
        self.era_name.setMaxLength(24)
        self.year = QSpinBox()
        self.year.setRange(1, 9999)
        self.month = QComboBox()
        for month in range(1, 13):
            self.month.addItem(f"{month} 月", month)
        self.xun = QComboBox()
        for index, name in enumerate(["上旬", "中旬", "下旬"], 1):
            self.xun.addItem(name, index)
        self.era_year = QSpinBox()
        self.era_year.setRange(1, 9999)
        self.health = QSpinBox()
        self.health.setRange(0, 100)
        for spinner in [self.year, self.era_year, self.health]:
            spinner.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        date = QWidget()
        date_row = QHBoxLayout(date)
        date_row.setContentsMargins(0, 0, 0, 0)
        date_row.addWidget(self.year, 2)
        date_row.addWidget(self.month, 1)
        date_row.addWidget(self.xun, 1)
        for caption, widget in [("选择剧本", self.preset_combo), ("剧本名称", self.scenario_name),
                                ("开局时间（公元）", date), ("皇帝姓名", self.emperor_name),
                                ("年号", self.era_name), ("开局为年号第几年", self.era_year),
                                ("初始健康", self.health)]:
            form.addRow(caption, widget)
        for name in ["scenario_name", "emperor_name", "era_name", "year", "era_year", "health"]:
            getattr(self, name).setObjectName(name)
        form_layout.addLayout(form)
        form_layout.addWidget(button("保存为自定义剧本", self.save_preset, name="savePreset"))
        form_layout.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(frame)
        row.addWidget(scroll, 3)
        preview, preview_layout = card("开局预览")
        self.setup_preview_name = label("", "previewName")
        self.setup_preview = label("")
        preview_layout.addWidget(self.setup_preview_name)
        preview_layout.addWidget(self.setup_preview)
        preview_layout.addStretch()
        preview_layout.addWidget(label("资料底本", "sectionTitle"))
        preview_layout.addWidget(label("明代 · 两京十三布政使司\n地图与人物资料以约 1500 年为工作基准。自定义年份和身份不会自动重建对应年代的史料。", "subtitle"))
        self.replace_notice = label("开始新局将替换当前未保存的进度；可先返回主菜单继续原局并保存。", "notice")
        preview_layout.addWidget(self.replace_notice)
        row.addWidget(preview, 2)
        layout.addLayout(row, 1)
        self.setup_feedback = label("", "feedback")
        layout.addWidget(self.setup_feedback)
        footer = QHBoxLayout()
        footer.addWidget(label("这些开局参数会随存档保存。", "subtitle"), 1)
        footer.addWidget(button("登基 · 开始游戏 →", self.start_game, primary=True, name="beginGame"))
        layout.addLayout(footer)
        for widget in [self.scenario_name, self.emperor_name, self.era_name]:
            widget.textChanged.connect(self.update_preview)
        for widget in [self.year, self.era_year, self.health]:
            widget.valueChanged.connect(self.update_preview)
        self.month.currentIndexChanged.connect(self.update_preview)
        self.xun.currentIndexChanged.connect(self.update_preview)
        self.refresh_presets()
        return page

    def _load_page(self):
        page, layout = self._page("读取游戏", "选择一份存档，接续皇帝的起居与朝政。")
        folder = QHBoxLayout()
        self.folder_label = label(str(self.save_directory), "subtitle")
        folder.addWidget(self.folder_label, 1)
        folder.addWidget(button("选择存档文件夹…", self.choose_save_directory, name="chooseSaveFolder"))
        folder.addWidget(button("刷新", self.refresh_saves, name="refreshSaves"))
        layout.addLayout(folder)
        self.save_table = QTableWidget(0, 5)
        self.save_table.setObjectName("saveList")
        self.save_table.setHorizontalHeaderLabels(["存档 / 剧本", "皇帝", "游戏日期", "保存时间", "状态"])
        self.save_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.save_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.save_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.save_table.verticalHeader().hide()
        self.save_table.horizontalHeader().setStretchLastSection(True)
        self.save_table.setColumnWidth(0, 320)
        self.save_table.setColumnWidth(1, 140)
        self.save_table.setColumnWidth(2, 255)
        self.save_table.setColumnWidth(3, 180)
        self.save_table.itemSelectionChanged.connect(self._save_selected)
        self.save_table.itemDoubleClicked.connect(lambda _: self.load_selected())
        layout.addWidget(self.save_table, 1)
        self.load_feedback = label("", "feedback")
        layout.addWidget(self.load_feedback)
        footer = QHBoxLayout()
        footer.addWidget(button("浏览其他存档文件…", self.browse_save, name="browseSave"))
        footer.addStretch()
        self.load_selected_button = button("读取选中存档 →", self.load_selected, primary=True, name="loadSelected")
        self.load_selected_button.setEnabled(False)
        footer.addWidget(self.load_selected_button)
        layout.addLayout(footer)
        return page

    def _settings(self):
        page, layout = self._page("设置", "游戏偏好与保存选项将在这里统一管理。")
        frame, body = card("保存设置")
        body.addWidget(label("自动保存周期", "sectionTitle"))
        row = QHBoxLayout()
        placeholder = QComboBox()
        placeholder.addItem("暂未启用")
        placeholder.setEnabled(False)
        row.addWidget(placeholder, 1)
        row.addWidget(label("预留", "subtitle"))
        body.addLayout(row)
        body.addWidget(label("当前请在游戏内手动保存。自动保存周期及其他选项后续补充。", "subtitle"))
        layout.addWidget(frame)
        layout.addStretch()
        return page

    def show_home(self):
        self.continue_button.setVisible(self.game is not None)
        self.pages.setCurrentWidget(self.home_page)
        self.setWindowTitle("御览 · 王朝人生")

    def show_setup(self):
        self.replace_notice.setVisible(self.game is not None)
        self.pages.setCurrentWidget(self.setup_page)
        self.setup_feedback.setText("")

    def show_load(self):
        self.refresh_saves()
        self.pages.setCurrentWidget(self.load_page)

    def show_settings(self):
        self.pages.setCurrentWidget(self.settings_page)

    def continue_game(self):
        if self.game is not None:
            self.pages.setCurrentWidget(self.game)
            self.setWindowTitle(self.game.windowTitle())

    def _preset_selected(self):
        payload = self.preset_combo.currentData()
        if not payload:
            return
        profile = payload["profile"]
        self.scenario_name.setText(profile["scenario_name"])
        self.emperor_name.setText(profile["emperor_name"])
        self.era_name.setText(profile["era_name"])
        self.year.setValue(payload["year"])
        self.month.setCurrentIndex(self.month.findData(payload["month"]))
        self.xun.setCurrentIndex(self.xun.findData(payload["xun"]))
        self.era_year.setValue(payload["year"] - profile["era_start_year"] + 1)
        self.health.setValue(payload["health"])
        self.update_preview()

    def refresh_presets(self, selected_path: Path | None = None):
        config = load_demo_config(self.repository.root)
        default = {"version": 1, "profile": {"scenario_name": "弘治中兴", "emperor_name": "朱祐樘",
                   "era_name": "弘治", "era_start_year": min(1488, config.initial_year)},
                   "year": config.initial_year, "month": config.initial_month,
                   "xun": config.initial_xun, "health": config.initial_health}
        self.preset_combo.blockSignals(True)
        self.preset_combo.clear()
        self.preset_combo.addItem("明代 · 弘治中兴", default)
        self.preset_combo.addItem("自定义开局（编辑下方参数）", None)
        selected = 0
        for path in sorted((self.data_directory / "scenarios").glob("*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                self._session_from_preset(payload)
            except FILE_ERRORS:
                continue
            self.preset_combo.addItem("自定义 · " + payload["profile"]["scenario_name"], payload)
            if path == selected_path:
                selected = self.preset_combo.count() - 1
        self.preset_combo.setCurrentIndex(selected)
        self.preset_combo.blockSignals(False)
        self._preset_selected()

    def _form_payload(self):
        return {"version": 1, "profile": {"scenario_name": self.scenario_name.text().strip(),
                "emperor_name": self.emperor_name.text().strip(), "era_name": self.era_name.text().strip(),
                "era_start_year": self.year.value() - self.era_year.value() + 1},
                "year": self.year.value(), "month": self.month.currentData(),
                "xun": self.xun.currentData(), "health": self.health.value()}

    def _session_from_preset(self, payload):
        if payload.get("version") != 1:
            raise ValueError("不支持的剧本文件版本。")
        for key, minimum, maximum in [("year", 1, 9999), ("month", 1, 12), ("xun", 1, 3), ("health", 0, 100)]:
            if type(payload[key]) is not int or not minimum <= payload[key] <= maximum:
                raise ValueError("剧本的年份、月旬或健康超出有效范围。")
        profile = ScenarioProfile(**payload["profile"])
        config = load_demo_config(self.repository.root)
        config.initial_year, config.initial_month, config.initial_xun = payload["year"], payload["month"], payload["xun"]
        config.initial_health = payload["health"]
        return GameSession.new_game(self.repository.initial_world(), config, profile=profile)

    def update_preview(self):
        if not hasattr(self, "setup_preview"):
            return
        config = load_demo_config(self.repository.root)
        self.setup_preview_name.setText(self.scenario_name.text().strip() or "未命名剧本")
        self.setup_preview.setText(
            f"皇帝　{self.emperor_name.text().strip() or '待填写'}\n\n"
            f"{self.era_name.text().strip() or '待定年号'}{self.era_year.value()}年 · "
            f"{self.month.currentText()}{self.xun.currentText()}\n"
            f"公元 {self.year.value()} 年\n\n"
            f"健康 {self.health.value()}　/　本旬行动力 {config.action_points(self.health.value())}"
        )

    def save_preset(self):
        try:
            payload = self._form_payload()
            self._session_from_preset(payload)
            directory = self.data_directory / "scenarios"
            directory.mkdir(parents=True, exist_ok=True)
            destination = directory / f"scenario-{uuid4().hex}.json"
            destination.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            self.refresh_presets(destination)
            self.setup_feedback.setText("剧本已保存。下次启动后可以从剧本列表选择。")
        except FILE_ERRORS as error:
            self.setup_feedback.setText(f"无法保存剧本：{error}")

    def start_game(self):
        try:
            session = self._session_from_preset(self._form_payload())
            self.enter_game(session)
        except FILE_ERRORS as error:
            self.setup_feedback.setText(f"请检查开局设定：{error}")

    def enter_game(self, session: GameSession, save_path: Path | None = None):
        replacement = MainWindow(self.repository, session)
        replacement.last_save = save_path
        replacement.menu_managed = True
        replacement.menu_button.show()
        replacement.main_menu_requested.connect(self.return_from_game)
        replacement.new_game_requested.connect(self.setup_from_game)
        replacement.windowTitleChanged.connect(self.setWindowTitle)
        prior = self.game
        self.pages.addWidget(replacement)
        self.game = replacement
        self.continue_game()
        if session.state.economy is not None:
            replacement.show_page(6)
        if prior is not None:
            self.pages.removeWidget(prior)
            prior.hide()
            prior.deleteLater()

    def return_from_game(self):
        if self.game is None or self.game._capture_activities():
            self.show_home()

    def setup_from_game(self):
        if self.game is None or self.game._capture_activities():
            self.show_setup()

    def refresh_saves(self):
        self.folder_label.setText(str(self.save_directory))
        self.save_table.setRowCount(0)
        try:
            paths = sorted(self.save_directory.glob("*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
        except OSError as error:
            self.load_feedback.setText(f"无法读取存档目录：{error}")
            return
        for path in paths:
            error = ""
            try:
                session = GameSession.load_json(path)
                name = session.state.scenario_profile.scenario_name
                emperor = session.state.scenario_profile.emperor_name
                date = session.state.era_date_label
                modified = datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
            except FILE_ERRORS as failure:
                name, emperor, date, modified = path.stem, "—", "—", "—"
                error = str(failure)
            row = self.save_table.rowCount()
            self.save_table.insertRow(row)
            for column, value in enumerate([f"{name}\n{path.name}", emperor, date, modified,
                                             "无法读取" if error else "可读取"]):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, (str(path), error))
                item.setToolTip(error or str(path))
                self.save_table.setItem(row, column, item)
            self.save_table.setRowHeight(row, 57)
        self.load_selected_button.setEnabled(False)
        self.load_feedback.setText("尚无存档。可以先开始游戏，或浏览其他位置的存档文件。" if not paths else "选择一份存档以继续。无法读取的文件会保留在列表中，原文件不会被修改。")

    def _save_selected(self):
        row = self.save_table.currentRow()
        item = self.save_table.item(row, 0) if row >= 0 else None
        if item is None:
            self.load_selected_button.setEnabled(False)
            return
        path, error = item.data(Qt.ItemDataRole.UserRole)
        self.load_selected_button.setEnabled(not error)
        self.load_feedback.setText(f"无法读取：{error}" if error else f"已选中：{path}")

    def load_selected(self):
        row = self.save_table.currentRow()
        if row < 0:
            return
        path, error = self.save_table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        if not error:
            self.load_path(Path(path))

    def load_path(self, path: Path):
        try:
            session = GameSession.load_json(path)
            self.enter_game(session, path)
        except FILE_ERRORS as error:
            self.load_feedback.setText(f"无法读取此存档：{error}")

    def browse_save(self):
        filename, _ = QFileDialog.getOpenFileName(self, "选择游戏存档", str(self.save_directory), "JSON 存档 (*.json)")
        if filename:
            self.load_path(Path(filename))

    def choose_save_directory(self):
        directory = QFileDialog.getExistingDirectory(self, "选择存档文件夹", str(self.save_directory))
        if directory:
            self.save_directory = Path(directory)
            self.refresh_saves()
