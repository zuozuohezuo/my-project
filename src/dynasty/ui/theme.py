"""A restrained ink, jade and parchment desktop theme."""

from pathlib import Path

from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

from dynasty.content import project_root


def initialize_fonts() -> None:
    if getattr(initialize_fonts, "loaded", False):
        return
    font = project_root() / "assets" / "fonts" / "NotoSansSC.ttf"
    if font.exists():
        QFontDatabase.addApplicationFont(str(font))
    else:
        fallback = Path("C:/Windows/Fonts/msyh.ttc")
        if fallback.exists():
            QFontDatabase.addApplicationFont(str(fallback))
    QApplication.instance().setFont(QFont("Noto Sans SC", 10))
    initialize_fonts.loaded = True


STYLE = """
QWidget { font-family: 'Noto Sans SC', 'Microsoft YaHei UI', 'Microsoft YaHei';
          font-size: 13px; color: #263c3b; }
QMainWindow, QDialog { background: #f2f0e9; }
QWidget#sidebar { background: #173c39; }
QWidget#sidebar QLabel { color: #d4ded5; background: transparent; }
QLabel#seal { color: #f0dfb4; font-size: 32px; font-weight: bold; padding: 10px 0; }
QLabel#brand { color: #ffffff; font-size: 22px; font-weight: 600; }
QPushButton { background: #ffffff; border: 1px solid #d7dbd0; border-radius: 6px;
              padding: 8px 14px; min-height: 20px; }
QPushButton:hover { background: #e9eee5; border-color: #9aaa97; }
QPushButton:pressed { background: #d9e3d5; }
QPushButton:disabled { color: #a4aaa2; background: #e9e9e2; border-color: #dddfd5; }
QPushButton[primary="true"] { background: #24574f; color: white; border-color: #24574f; font-weight: 600; }
QPushButton[primary="true"]:hover { background: #306b61; }
QPushButton[primary="true"]:disabled { background: #97aaa2; color: #e7ece8; }
QPushButton[danger="true"] { color: #963e2d; border-color: #d7b5a3; background: #fff8ef; }
QPushButton#nav { background: transparent; border: none; color: #c7d8cc; text-align: left;
                  padding: 12px 14px; font-size: 14px; border-radius: 6px; }
QPushButton#nav:hover { background: #24524a; }
QPushButton#nav:checked { background: #e6dfc8; color: #1c423b; font-weight: bold; }
QLabel#eyebrow { color: #7d866e; font-size: 11px; letter-spacing: 2px; }
QLabel#title { font-size: 26px; font-weight: 600; color: #1c423b; }
QLabel#subtitle { color: #788376; }
QLabel#metricValue { color: #234e47; font-size: 22px; font-weight: bold; }
QLabel#metricLabel { color: #858e7d; font-size: 12px; }
QFrame#card { background: #fffef9; border: 1px solid #dce0d3; border-radius: 9px; }
QFrame#card QLabel { background: transparent; border: none; }
QLabel#sectionTitle { font-size: 17px; font-weight: bold; color: #2b4841; }
QLabel#notice { background: #e7ebdc; color: #59674d; padding: 9px 14px; border-radius: 5px; }
QLabel#feedback { background: #fcf9ef; color: #566548; padding: 8px 12px; border: 1px solid #dce0ce; border-radius: 5px; }
QLabel#feedback[error="true"] { background: #fff0e5; color: #943b2a; border-color: #e4bca3; }
QComboBox, QLineEdit, QSpinBox, QDoubleSpinBox { background: #fffef9; border: 1px solid #cdd5c9;
    padding: 7px; border-radius: 5px; min-height: 21px; selection-background-color: #c7d8c0; }
QComboBox::drop-down { border: none; width: 24px; }
QComboBox QAbstractItemView { background: #fffef9; selection-background-color: #d9e5d3; }
QTableWidget, QTreeWidget, QListWidget, QTextBrowser { background: #fffef9; border: 1px solid #d7ddcf;
    border-radius: 5px; alternate-background-color: #f2f5eb; selection-background-color: #d9e4d0;
    selection-color: #153d36; gridline-color: #e6eadf; }
QHeaderView::section { background: #e9eee1; border: none; border-bottom: 1px solid #d4ddcb;
    padding: 8px; color: #5b6b54; font-weight: bold; }
QTabWidget::pane { border: 1px solid #d5ddce; background: #fffef9; border-radius: 5px; }
QTabBar::tab { background: #e5eadc; padding: 10px 18px; margin-right: 3px; }
QTabBar::tab:selected { background: #fffef9; color: #234f44; font-weight: bold; }
QScrollBar:vertical { width: 10px; background: #ecefe5; }
QScrollBar::handle:vertical { background: #becbb5; min-height: 25px; border-radius: 4px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QStatusBar { background: #e6eadd; color: #6f7c62; }
QToolTip { background: #fff9e8; color: #26443a; padding: 8px; border: 1px solid #acbba0; }
QGroupBox { border: 1px solid #d8dfcf; border-radius: 6px; margin-top: 16px; padding: 14px; font-weight: bold; }
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 5px; }
QCheckBox { spacing: 7px; }
QSplitter::handle { background: transparent; }
QFrame#card QLabel#emperorSeal { background: #954b38; color: #fff4d7; font-size: 26px;
    font-weight: bold; border: 2px solid #b98962; border-radius: 4px; }
QLabel#emperorName { font-size: 23px; font-weight: 600; color: #214c43; }
QLabel#emperorAttributeName { font-size: 14px; font-weight: 600; color: #2b4841; }
QLabel#emperorHint { color: #758171; font-size: 12px; }
QLabel#emperorAttributeValue, QLabel#emperorSkillValue {
    font-size: 26px; font-weight: 600; color: #285b50; }
QFrame#emperorRule { background: #e7e9df; border: none; }
QPushButton#emperorSkill { padding: 0; background: #fffef9; border-radius: 8px;
    border: 1px solid #d5ddce; text-align: left; }
QPushButton#emperorSkill:hover { background: #f2f5eb; border-color: #8ca58e; }
QPushButton#emperorSkill:checked { background: #eaf0e3; border: 2px solid #628571; }
QPushButton#emperorSkill QLabel { background: transparent; border: none; }
QProgressBar#emperorHealthBar, QProgressBar#emperorPressureBar {
    border: none; border-radius: 3px; background: #e5e9dd; }
QProgressBar#emperorHealthBar::chunk { background: #568672; border-radius: 3px; }
QProgressBar#emperorPressureBar::chunk { background: #b69054; border-radius: 3px; }
QFrame#card QLabel#emperorCondition { color: #8c4d36; background: #f8ede0;
    border-radius: 4px; padding: 6px 8px; }
QFrame#emperorModifierRow { background: #f0f3e9; border: 1px solid #dde4d4; border-radius: 5px; }
QLabel#emperorModifierEffect { color: #43705b; font-size: 12px; }
QProgressBar#personalityBar, QProgressBar#pursuitProgress {
    border: none; border-radius: 3px; background: #dfe5d7; }
QProgressBar#personalityBar::chunk, QProgressBar#pursuitProgress::chunk {
    background: #618776; border-radius: 3px; }
QSlider#personalitySlider::groove:horizontal { height: 5px; background: #d9e1d1; border-radius: 2px; }
QSlider#personalitySlider::sub-page:horizontal { background: #648773; border-radius: 2px; }
QSlider#personalitySlider::handle:horizontal { width: 13px; margin: -5px 0;
    border: 1px solid #446a55; border-radius: 6px; background: #f7faef; }
"""
