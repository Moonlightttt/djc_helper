from typing import List, Tuple

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QValidator, QWheelEvent
from PyQt5.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout,
                             QFrame, QHBoxLayout, QLabel, QLayout, QLineEdit,
                             QMessageBox, QPushButton, QScrollArea, QSpinBox,
                             QVBoxLayout, QWidget)

from log import logger
from qt_collapsible_box import CollapsibleBox
from util import padLeftRight


class QHLine(QFrame):
    def __init__(self):
        super(QHLine, self).__init__()
        self.setFrameShape(QFrame.HLine)
        self.setFrameShadow(QFrame.Sunken)


class QVLine(QFrame):
    def __init__(self):
        super(QVLine, self).__init__()
        self.setFrameShape(QFrame.VLine)
        self.setFrameShadow(QFrame.Sunken)


class MySpinbox(QSpinBox):
    def __init__(self, parent=None):
        super(MySpinbox, self).__init__(parent)

        self.setFocusPolicy(Qt.StrongFocus)

    def wheelEvent(self, event: QWheelEvent) -> None:
        if self.hasFocus():
            super(MySpinbox, self).wheelEvent(event)
        else:
            event.ignore()


class MyDoubleSpinbox(QDoubleSpinBox):
    def __init__(self, parent=None):
        super(MyDoubleSpinbox, self).__init__(parent)

        self.setFocusPolicy(Qt.StrongFocus)

    def wheelEvent(self, event: QWheelEvent) -> None:
        if self.hasFocus():
            super(MyDoubleSpinbox, self).wheelEvent(event)
        else:
            event.ignore()


class MyComboBox(QComboBox):
    clicked = pyqtSignal()

    def showPopup(self):
        self.clicked.emit()
        super(MyComboBox, self).showPopup()

    def wheelEvent(self, event: QWheelEvent) -> None:
        if self.hasFocus():
            super(MyComboBox, self).wheelEvent(event)
        else:
            event.ignore()


def create_pushbutton(text, color="", tooltip="") -> QPushButton:
    btn = QPushButton(text)
    btn.setStyleSheet(f"background-color: {color}; font-weight: bold; font-family: Microsoft YaHei")
    btn.setToolTip(tooltip)

    return btn


def create_checkbox(val=False, name="") -> QCheckBox:
    checkbox = QCheckBox(name)

    checkbox.setChecked(val)

    return checkbox


def create_spin_box(value: int, maximum: int = 99999, minimum: int = 0) -> MySpinbox:
    spinbox = MySpinbox()
    spinbox.setMaximum(maximum)
    spinbox.setMinimum(minimum)

    spinbox.setValue(value)

    return spinbox


def create_double_spin_box(value: float, maximum: float = 1.0, minimum: float = 0.0) -> MyDoubleSpinbox:
    spinbox = MyDoubleSpinbox()
    spinbox.setMaximum(maximum)
    spinbox.setMinimum(minimum)

    spinbox.setValue(value)

    return spinbox


def create_combobox(current_val: str, values: List[str] = None) -> MyComboBox:
    combobox = MyComboBox()

    combobox.setFocusPolicy(Qt.StrongFocus)

    if values is not None:
        combobox.addItems(values)
    combobox.setCurrentText(current_val)

    return combobox


def create_lineedit(current_text: str, placeholder_text="") -> QLineEdit:
    lineedit = QLineEdit(current_text)

    lineedit.setPlaceholderText(placeholder_text)

    return lineedit


def add_form_seperator(form_layout: QFormLayout, title: str):
    add_row(form_layout, f"=== {title} ===", QHLine())


def add_vbox_seperator(vbox_layout: QVBoxLayout, title: str):
    hbox = QHBoxLayout()

    hbox.addStretch(1)
    hbox.addWidget(QLabel(title))
    hbox.addStretch(1)

    vbox_layout.addWidget(QHLine())
    vbox_layout.addLayout(hbox)
    vbox_layout.addWidget(QHLine())


def add_row(form_layout: QFormLayout, row_name: str, row_widget: QWidget, minium_row_name_size=0):
    if minium_row_name_size > 0:
        row_name = padLeftRight(row_name, minium_row_name_size, mode="left")
    form_layout.addRow(row_name, row_widget)


def make_scroll_layout(inner_layout: QLayout):
    widget = QWidget()
    widget.setLayout(inner_layout)

    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setWidget(widget)

    scroll_layout = QVBoxLayout()
    scroll_layout.addWidget(scroll)

    return scroll_layout


def create_collapsible_box_with_sub_form_layout_and_add_to_parent_layout(title: str, parent_layout: QLayout, fold: bool = True, title_backgroup_color="") -> Tuple[CollapsibleBox, QFormLayout]:
    collapsible_box = CollapsibleBox(title, title_backgroup_color=title_backgroup_color)
    parent_layout.addWidget(collapsible_box)

    form_layout = QFormLayout()
    collapsible_box.setContentLayout(form_layout)

    collapsible_box.set_fold(fold)

    return collapsible_box, form_layout


def create_collapsible_box_add_to_parent_layout(title: str, parent_layout: QLayout, title_backgroup_color="") -> CollapsibleBox:
    collapsible_box = CollapsibleBox(title, title_backgroup_color=title_backgroup_color)
    parent_layout.addWidget(collapsible_box)

    return collapsible_box


def init_collapsible_box_size(parent_widget: QWidget):
    # 尝试更新各个折叠区域的大小
    for attr_name in dir(parent_widget):
        if not attr_name.startswith("collapsible_box_"):
            continue

        collapsible_box = getattr(parent_widget, attr_name)  # type: CollapsibleBox
        collapsible_box.try_adjust_size()


def list_to_str(vlist: List[str]):
    return ','.join(str(v) for v in vlist)


def str_to_list(str_list: str):
    str_list = str_list.strip(" ,")
    if str_list == "":
        return []

    return [s.strip() for s in str_list.split(',')]


class QQListValidator(QValidator):
    def validate(self, text: str, pos: int) -> Tuple['QValidator.State', str, int]:
        sl = str_to_list(text)

        for qq in sl:
            if not qq.isnumeric():
                return (QValidator.Invalid, text, pos)

        return (QValidator.Acceptable, text, pos)


def show_message(title, text):
    logger.info(f"{title} {text}")

    message_box = QMessageBox()
    message_box.setWindowTitle(title)
    message_box.setText(text)
    message_box.exec_()
