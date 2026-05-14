from __future__ import annotations

import locale
from copy import deepcopy
from pathlib import Path

from PySide6.QtCore import QByteArray, QProcess, QProcessEnvironment, Qt, QSize
from PySide6.QtGui import QAction, QFont, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QToolButton,
    QVBoxLayout,
    QWidget,
    QMenu,
)

from pipeline_config import (
    LOGO_PATH,
    PIPELINE_VERSION,
    PROJECT_ROOT,
    PipelineConfigError,
    list_pipeline_step_configs,
    save_pipeline_document,
    stage_names,
)
from pipeline_service import (
    available_stage_configs,
    check_step,
    detect_output_health,
    detect_status,
    discover_artifacts,
    list_steps,
    load_markdown,
    load_primary_table,
    open_external_path,
    run_step,
)
from stage_config import get_active_config_name, get_ui_setting, set_active_config_name, set_ui_setting
from step_types import ArtifactBundle, RunnerType, StepDefinition, StepStatus
from ui_panels import ConsolePanel, ImagePanel, MarkdownPanel, TablePanel


class StepListItemWidget(QFrame):
    def __init__(self, title: str, subtitle: str, subtitle_color: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._selected = False
        self._title_text = title
        self.setStyleSheet("QFrame { border: none; border-radius: 6px; }")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        self.title_label = QLabel(title)
        self.title_label.setStyleSheet(
            "border: none; color: #18212b; font-size: 14px; font-weight: 700; min-height: 20px;"
        )
        self.title_label.setWordWrap(False)
        self.title_label.setTextFormat(Qt.PlainText)
        self.title_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout.addWidget(self.title_label)

        self.subtitle_label = QLabel(subtitle)
        self.subtitle_label.setMinimumHeight(18)
        self.subtitle_label.setWordWrap(True)
        layout.addWidget(self.subtitle_label)
        self.set_status(subtitle, subtitle_color)
        self.set_selected(False)
        self.set_title(title)

    def set_title(self, title: str) -> None:
        self._title_text = title
        self.title_label.setToolTip(title)
        self._update_title_elision()

    def set_status(self, subtitle: str, subtitle_color: str) -> None:
        self.subtitle_label.setText(subtitle)
        self.subtitle_label.setStyleSheet(
            f"border: none; color: {subtitle_color}; font-size: 12px; font-weight: 700;"
        )

    def set_selected(self, selected: bool) -> None:
        self._selected = selected
        background = "#e8eef3" if selected else "transparent"
        self.setStyleSheet(f"QFrame {{ border: none; border-radius: 6px; background: {background}; }}")

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update_title_elision()

    def _update_title_elision(self) -> None:
        available_width = max(40, self.title_label.width() - 4)
        elided = self.title_label.fontMetrics().elidedText(self._title_text, Qt.ElideRight, available_width)
        self.title_label.setText(elided)


class StepEditorDialog(QDialog):
    def __init__(self, step_data: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("编辑步骤")
        self.resize(860, 420)
        self.result_data: dict | None = None

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignTop)

        self.enabled_check = QCheckBox("启用该步骤")
        form.addRow("启停", self.enabled_check)

        self.id_edit = QLineEdit()
        form.addRow("步骤 ID", self.id_edit)

        self.script_edit = QLineEdit()
        form.addRow("脚本路径", self.script_edit)

        self.stage_combo = QComboBox()
        self.stage_combo.addItems(stage_names())
        form.addRow("阶段", self.stage_combo)

        self.order_edit = QLineEdit()
        form.addRow("排序", self.order_edit)

        self.name_override_edit = QLineEdit()
        self.name_override_edit.setPlaceholderText("可留空，默认使用脚本 STEP_SPEC.name")
        form.addRow("名称覆盖", self.name_override_edit)

        self.description_edit = QPlainTextEdit()
        self.description_edit.setFixedHeight(82)
        form.addRow("说明覆盖", self.description_edit)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._load(step_data)

    def _load(self, step_data: dict) -> None:
        self.enabled_check.setChecked(step_data.get("enabled", True))
        self.id_edit.setText(step_data.get("id", ""))
        self.script_edit.setText(step_data.get("script", ""))
        self.stage_combo.setCurrentText(step_data.get("stage", stage_names()[0]))
        self.order_edit.setText(str(step_data.get("order", 10)))
        self.name_override_edit.setText(step_data.get("name_override") or "")
        self.description_edit.setPlainText(step_data.get("description_override", ""))

    def accept(self) -> None:
        try:
            self.result_data = self._build_step_data()
        except ValueError as exc:
            QMessageBox.warning(self, "步骤配置无效", str(exc))
            return
        super().accept()

    def _build_step_data(self) -> dict:
        step_id = self.id_edit.text().strip()
        if not step_id:
            raise ValueError("步骤 ID 不能为空。")
        script_text = self.script_edit.text().strip()
        if not script_text:
            raise ValueError("脚本路径不能为空。")
        order_text = self.order_edit.text().strip()
        if not order_text:
            raise ValueError("排序不能为空。")
        try:
            order = int(order_text)
        except ValueError as exc:
            raise ValueError("排序必须是整数。") from exc
        return {
            "id": step_id,
            "script": script_text,
            "stage": self.stage_combo.currentText(),
            "enabled": self.enabled_check.isChecked(),
            "order": order,
            "name_override": self.name_override_edit.text().strip() or None,
            "description_override": self.description_edit.toPlainText().strip() or None,
        }


class PipelineManagerDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("流水线管理")
        self.resize(760, 560)
        document = {"version": PIPELINE_VERSION, "steps": list_pipeline_step_configs()}
        self.document = document

        root = QVBoxLayout(self)
        hint = QLabel("管理全部步骤。禁用步骤不会出现在主执行列表中。")
        hint.setWordWrap(True)
        root.addWidget(hint)

        content = QHBoxLayout()
        self.step_list = QListWidget()
        self.step_list.itemDoubleClicked.connect(lambda _: self._edit_step())
        content.addWidget(self.step_list, 2)

        controls = QVBoxLayout()
        controls.setSpacing(10)
        self.add_button = QPushButton("新增")
        self.edit_button = QPushButton("编辑")
        self.copy_button = QPushButton("复制")
        self.toggle_button = QPushButton("启用/停用")
        self.up_button = QPushButton("上移")
        self.down_button = QPushButton("下移")
        self.delete_button = QPushButton("删除")
        for button, handler in (
            (self.add_button, self._add_step),
            (self.edit_button, self._edit_step),
            (self.copy_button, self._copy_step),
            (self.toggle_button, self._toggle_step),
            (self.up_button, self._move_up),
            (self.down_button, self._move_down),
            (self.delete_button, self._delete_step),
        ):
            button.clicked.connect(handler)
            controls.addWidget(button)
        controls.addStretch(1)
        content.addLayout(controls, 1)
        root.addLayout(content, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        self._refresh_step_list(0)

    def accept(self) -> None:
        try:
            save_pipeline_document(self.document)
        except PipelineConfigError as exc:
            QMessageBox.warning(self, "保存失败", str(exc))
            return
        super().accept()

    def _refresh_step_list(self, target_index: int | None = None) -> None:
        self.step_list.clear()
        for step in self.document["steps"]:
            prefix = "启用" if step.get("enabled", True) else "停用"
            label = step.get("name_override") or Path(step["script"]).stem
            item = QListWidgetItem(f"[{prefix}] {step['stage']} | {label} ({step['id']})")
            self.step_list.addItem(item)
        if self.document["steps"]:
            if target_index is None:
                target_index = min(self.step_list.currentRow(), len(self.document["steps"]) - 1)
            target_index = max(0, min(target_index, len(self.document["steps"]) - 1))
            self.step_list.setCurrentRow(target_index)

    def _selected_index(self) -> int:
        return self.step_list.currentRow()

    def _selected_step(self) -> dict | None:
        index = self._selected_index()
        if index < 0 or index >= len(self.document["steps"]):
            return None
        return self.document["steps"][index]

    def _add_step(self) -> None:
        base_stage = self._selected_step()["stage"] if self._selected_step() else stage_names()[0]
        raw_step = {
            "id": self._make_unique_id("new_step"),
            "script": "code/待补充.py",
            "stage": base_stage,
            "enabled": True,
            "order": (len(self.document["steps"]) + 1) * 10,
            "name_override": None,
            "description_override": None,
        }
        dialog = StepEditorDialog(raw_step, self)
        if dialog.exec() != QDialog.Accepted or dialog.result_data is None:
            return
        self.document["steps"].append(dialog.result_data)
        self._renumber_orders()
        self._refresh_step_list(len(self.document["steps"]) - 1)

    def _edit_step(self) -> None:
        index = self._selected_index()
        step = self._selected_step()
        if step is None:
            return
        dialog = StepEditorDialog(deepcopy(step), self)
        if dialog.exec() != QDialog.Accepted or dialog.result_data is None:
            return
        self.document["steps"][index] = dialog.result_data
        self._renumber_orders()
        self._refresh_step_list(index)

    def _copy_step(self) -> None:
        index = self._selected_index()
        step = self._selected_step()
        if step is None:
            return
        copied = deepcopy(step)
        copied["id"] = self._make_unique_id(f"{step['id']}_copy")
        if copied.get("name_override"):
            copied["name_override"] = f"{copied['name_override']}（副本）"
        dialog = StepEditorDialog(copied, self)
        if dialog.exec() != QDialog.Accepted or dialog.result_data is None:
            return
        self.document["steps"].insert(index + 1, dialog.result_data)
        self._renumber_orders()
        self._refresh_step_list(index + 1)

    def _toggle_step(self) -> None:
        step = self._selected_step()
        if step is None:
            return
        step["enabled"] = not step.get("enabled", True)
        self._refresh_step_list(self._selected_index())

    def _move_up(self) -> None:
        index = self._selected_index()
        if index <= 0:
            return
        self.document["steps"][index - 1], self.document["steps"][index] = self.document["steps"][index], self.document["steps"][index - 1]
        self._renumber_orders()
        self._refresh_step_list(index - 1)

    def _move_down(self) -> None:
        index = self._selected_index()
        if index < 0 or index >= len(self.document["steps"]) - 1:
            return
        self.document["steps"][index + 1], self.document["steps"][index] = self.document["steps"][index], self.document["steps"][index + 1]
        self._renumber_orders()
        self._refresh_step_list(index + 1)

    def _delete_step(self) -> None:
        index = self._selected_index()
        step = self._selected_step()
        if step is None:
            return
        answer = QMessageBox.question(self, "确认删除", f"删除步骤：{step['name']} ({step['id']})？")
        if answer != QMessageBox.Yes:
            return
        self.document["steps"].pop(index)
        self._renumber_orders()
        self._refresh_step_list(index)

    def _make_unique_id(self, base_id: str) -> str:
        existing = {step["id"] for step in self.document["steps"]}
        if base_id not in existing:
            return base_id
        suffix = 2
        while f"{base_id}_{suffix}" in existing:
            suffix += 1
        return f"{base_id}_{suffix}"

    def _renumber_orders(self) -> None:
        for index, step in enumerate(self.document["steps"], start=1):
            step["order"] = index * 10


class MainWindow(QMainWindow):
    RENDER_EXISTING_OUTPUTS_KEY = "render_existing_outputs_without_run"
    BODY_SPLITTER_STATE_KEY = "main_window_body_splitter_state"
    LEFT_SPLITTER_STATE_KEY = "main_window_left_splitter_state"
    RIGHT_SPLITTER_STATE_KEY = "main_window_right_splitter_state"

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("光碳智绘：区域碳效时空分析平台")
        self.resize(1640, 980)
        self.setMinimumSize(QSize(1320, 840))

        self.steps = list(list_steps())
        self.statuses = {step.id: detect_status(step.id) for step in self.steps}
        self.current_step_index = 0
        self.current_table_index = 0
        self.current_image_index = 0
        self.current_artifacts = ArtifactBundle()
        self.running_step_id: str | None = None
        self._config_refreshing = False
        self.render_existing_outputs = bool(get_ui_setting(self.RENDER_EXISTING_OUTPUTS_KEY, False))

        self.process = QProcess(self)
        self.process.readyReadStandardOutput.connect(self._read_stdout)
        self.process.readyReadStandardError.connect(self._read_stderr)
        self.process.finished.connect(self._on_process_finished)

        self._build_ui()
        self._restore_splitter_states()
        self._populate_step_list()
        self.step_list.setCurrentRow(0)
        self._refresh_executable_summary()

    def _build_ui(self) -> None:
        central = QWidget()
        central.setStyleSheet(
            """
            QWidget {
                background: #f4f6f8;
                color: #18212b;
                font-family: "Times New Roman", "SimHei";
            }
            QListWidget, QLabel, QPushButton {
                font-family: "Times New Roman", "SimHei";
            }
            QPushButton {
                border: 1px solid #cfd6de;
                border-radius: 6px;
                background: #fbfcfd;
                font-size: 17px;
                font-weight: 700;
                padding: 0 16px;
                color: #18212b;
            }
            QPushButton:hover {
                background: #f0f4f7;
            }
            QPushButton:disabled {
                background: #e5e7eb;
                color: #90a1b2;
            }
            QScrollBar:vertical, QScrollBar:horizontal {
                background: #eaf0f6;
                border-radius: 5px;
                margin: 0px;
            }
            QScrollBar::handle:vertical, QScrollBar::handle:horizontal {
                background: #9db0c3;
                border-radius: 5px;
                min-height: 28px;
                min-width: 28px;
            }
            QSplitter::handle {
                background: #d8dee6;
            }
            QSplitter::handle:hover {
                background: #b9c6d3;
            }
            QSplitter::handle:horizontal {
                width: 8px;
                margin: 0 2px;
                border-radius: 4px;
            }
            QSplitter::handle:vertical {
                height: 8px;
                margin: 2px 0;
                border-radius: 4px;
            }
            """
        )
        self.setCentralWidget(central)

        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(18, 18, 18, 18)
        root_layout.setSpacing(14)

        root_layout.addWidget(self._build_header())

        self.body_splitter = QSplitter(Qt.Horizontal)
        self.body_splitter.setChildrenCollapsible(False)
        self.body_splitter.setHandleWidth(8)
        self.body_splitter.addWidget(self._build_left_column())
        self.body_splitter.addWidget(self._build_right_column())
        self.body_splitter.setStretchFactor(0, 3)
        self.body_splitter.setStretchFactor(1, 5)
        self.body_splitter.setSizes([520, 960])
        self.body_splitter.splitterMoved.connect(self._persist_splitter_states)
        root_layout.addWidget(self.body_splitter, 1)

    def _build_header(self) -> QWidget:
        frame = QFrame()
        frame.setStyleSheet("QFrame { background: #fbfcfd; border: 1px solid #d8dee6; border-radius: 8px; }")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(16)

        logo_label = QLabel()
        logo_label.setFixedSize(78, 78)
        if LOGO_PATH.exists():
            logo_label.setPixmap(QPixmap(str(LOGO_PATH)).scaled(78, 78, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        logo_label.setAlignment(Qt.AlignCenter)
        logo_label.setStyleSheet("border: none;")

        title_block = QWidget()
        title_block.setStyleSheet("border: none;")
        title_block_layout = QVBoxLayout(title_block)
        title_block_layout.setContentsMargins(0, 0, 0, 0)
        title_block_layout.setSpacing(4)

        title_label = QLabel("光碳智绘：区域碳效时空分析平台")
        title_label.setStyleSheet("border: none; font-size: 32px; font-weight: 800; color: #18212b;")
        title_label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)

        self.version_label = QLabel("GUI v0.2")
        self.version_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.version_label.setStyleSheet("border: none; color: #6b7785; font-size: 12px; font-weight: 600;")

        title_block_layout.addWidget(title_label)
        title_block_layout.addWidget(self.version_label)

        self.settings_button = QToolButton()
        self.settings_button.setText("设置")
        self.settings_button.setPopupMode(QToolButton.InstantPopup)
        self.settings_button.setStyleSheet(
            """
            QToolButton {
                border: 1px solid #cfd6de;
                border-radius: 6px;
                background: #fbfcfd;
                font-size: 15px;
                font-weight: 700;
                padding: 8px 14px;
                color: #18212b;
            }
            QToolButton::menu-indicator {
                image: none;
                width: 0px;
            }
            QToolButton:hover {
                background: #f0f4f7;
            }
            """
        )
        settings_menu = QMenu(self.settings_button)
        settings_menu.setStyleSheet(
            """
            QMenu {
                background: #fbfcfd;
                border: 1px solid #d8dee6;
                padding: 6px;
            }
            QMenu::item {
                padding: 8px 28px 8px 12px;
            }
            QMenu::item:selected {
                background: #e8eef3;
            }
            """
        )
        self.render_existing_outputs_action = QAction("渲染已存在输出（未点击运行也显示）", self)
        self.render_existing_outputs_action.setCheckable(True)
        self.render_existing_outputs_action.setChecked(self.render_existing_outputs)
        self.render_existing_outputs_action.toggled.connect(self._on_render_existing_outputs_toggled)
        settings_menu.addAction(self.render_existing_outputs_action)
        self.settings_button.setMenu(settings_menu)

        self.pipeline_button = QPushButton("流水线管理")
        self.pipeline_button.setMinimumHeight(42)
        self.pipeline_button.clicked.connect(self._open_pipeline_manager)

        layout.addWidget(logo_label, 0)
        layout.addWidget(title_block, 1)
        layout.addWidget(self.pipeline_button, 0, Qt.AlignTop)
        layout.addWidget(self.settings_button, 0, Qt.AlignTop)
        return frame

    def _build_left_column(self) -> QWidget:
        self.left_splitter = QSplitter(Qt.Vertical)
        self.left_splitter.setChildrenCollapsible(False)
        self.left_splitter.setHandleWidth(8)
        self.left_splitter.splitterMoved.connect(self._persist_splitter_states)

        self.step_list = QListWidget()
        self.step_list.setMinimumHeight(210)
        self.step_list.setStyleSheet(
            """
            QListWidget {
                border: 1px solid #d8dee6;
                border-radius: 8px;
                background: #fbfcfd;
                padding: 4px;
            }
            QListWidget::item {
                border-radius: 6px;
                margin: 2px 0px;
                padding: 6px 10px;
            }
            QListWidget::item:selected {
                background: #e8eef3;
                color: #18212b;
            }
            """
        )
        self.step_list.currentRowChanged.connect(self._on_step_changed)
        self.left_splitter.addWidget(self.step_list)

        execute_frame = QFrame()
        execute_frame.setMinimumHeight(150)
        execute_frame.setStyleSheet("QFrame { background: #fbfcfd; border: 1px solid #d8dee6; border-radius: 8px; }")
        execute_layout = QVBoxLayout(execute_frame)
        execute_layout.setContentsMargins(14, 10, 14, 12)
        execute_layout.setSpacing(10)

        self.current_step_label = QLabel("当前步骤")
        self.current_step_label.setAlignment(Qt.AlignCenter)
        self.current_step_label.setStyleSheet("border: none; font-size: 20px; font-weight: 800;")
        execute_layout.addWidget(self.current_step_label)

        config_row = QHBoxLayout()
        config_row.setSpacing(8)
        config_label = QLabel("阶段配置")
        config_label.setStyleSheet("border: none; color: #5b6b7a; font-size: 12px;")
        self.stage_config_combo = QComboBox()
        self.stage_config_combo.setStyleSheet(
            """
            QComboBox {
                border: 1px solid #cfd6de;
                border-radius: 6px;
                background: #fbfcfd;
                padding: 6px 10px;
                min-height: 32px;
            }
            """
        )
        self.stage_config_combo.currentTextChanged.connect(self._on_stage_config_changed)
        config_row.addWidget(config_label)
        config_row.addWidget(self.stage_config_combo, 1)
        execute_layout.addLayout(config_row)

        button_row = QHBoxLayout()
        button_row.setSpacing(10)
        self.check_button = QPushButton("检查")
        self.check_button.setFixedSize(74, 52)
        self.check_button.clicked.connect(self._run_check)

        self.run_button = QPushButton("执行")
        self.run_button.setMinimumHeight(52)
        self.run_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.run_button.clicked.connect(self._run_current_step)

        self.next_button = QPushButton("下一步")
        self.next_button.setFixedHeight(52)
        self.next_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.next_button.clicked.connect(self._go_to_next_step)

        button_row.addWidget(self.check_button)
        button_row.addWidget(self.run_button, 1)
        button_row.addWidget(self.next_button, 1)
        execute_layout.addLayout(button_row)

        self.step_hint_label = QLabel("")
        self.step_hint_label.setWordWrap(True)
        self.step_hint_label.setStyleSheet("border: none; color: #5b6b7a; font-size: 12px;")
        execute_layout.addWidget(self.step_hint_label)
        self.left_splitter.addWidget(execute_frame)

        self.console_panel = ConsolePanel()
        self.console_panel.setMinimumHeight(140)
        self.left_splitter.addWidget(self.console_panel)

        self.table_panel = TablePanel()
        self.table_panel.setMinimumHeight(160)
        self.table_panel.navigate_previous.connect(lambda: self._change_table(-1))
        self.table_panel.navigate_next.connect(lambda: self._change_table(1))
        self.left_splitter.addWidget(self.table_panel)

        self.left_splitter.setStretchFactor(0, 3)
        self.left_splitter.setStretchFactor(1, 2)
        self.left_splitter.setStretchFactor(2, 2)
        self.left_splitter.setStretchFactor(3, 3)
        self.left_splitter.setSizes([240, 190, 220, 280])
        return self.left_splitter

    def _build_right_column(self) -> QWidget:
        self.right_splitter = QSplitter(Qt.Vertical)
        self.right_splitter.setChildrenCollapsible(False)
        self.right_splitter.setHandleWidth(8)
        self.right_splitter.splitterMoved.connect(self._persist_splitter_states)

        self.image_panel = ImagePanel()
        self.image_panel.setMinimumHeight(260)
        self.image_panel.navigate_previous.connect(lambda: self._change_image(-1))
        self.image_panel.navigate_next.connect(lambda: self._change_image(1))
        self.image_panel.reset_requested.connect(self.image_panel.image_view.reset_view)
        self.right_splitter.addWidget(self.image_panel)

        self.markdown_panel = MarkdownPanel()
        self.markdown_panel.setMinimumHeight(200)
        self.right_splitter.addWidget(self.markdown_panel)
        self.right_splitter.setStretchFactor(0, 5)
        self.right_splitter.setStretchFactor(1, 4)
        self.right_splitter.setSizes([520, 360])
        return self.right_splitter

    def _populate_step_list(self) -> None:
        self.step_list.clear()
        for step in self.steps:
            status = self.statuses.get(step.id, StepStatus.IDLE)
            item = QListWidgetItem()
            item.setData(Qt.UserRole, step.id)
            item.setSizeHint(QSize(260, 68))
            self.step_list.addItem(item)
            self._refresh_step_item_widget(self.step_list.count() - 1)
        self._sync_step_item_selection()

    def _refresh_step_item(self, row: int) -> None:
        self._refresh_step_item_widget(row)
        self._sync_step_item_selection()

    def _refresh_step_item_widget(self, row: int) -> None:
        step = self.steps[row]
        item = self.step_list.item(row)
        status = self.statuses.get(step.id, StepStatus.IDLE)
        subtitle, subtitle_color = self._display_status(step, status)
        widget = self.step_list.itemWidget(item)
        title = f"{step.stage} | {step.name}"
        if widget is None:
            widget = StepListItemWidget(title, subtitle, subtitle_color)
            self.step_list.setItemWidget(item, widget)
        else:
            widget.set_title(title)
            widget.set_status(subtitle, subtitle_color)
        item.setBackground(Qt.transparent)

    def _sync_step_item_selection(self) -> None:
        current_row = self.step_list.currentRow()
        for row in range(self.step_list.count()):
            widget = self.step_list.itemWidget(self.step_list.item(row))
            if widget is not None:
                widget.set_selected(row == current_row)

    def _refresh_executable_summary(self) -> None:
        self.version_label.setText("GUI v0.3 | PySide6")

    def _restore_splitter_states(self) -> None:
        for splitter, key in (
            (self.body_splitter, self.BODY_SPLITTER_STATE_KEY),
            (self.left_splitter, self.LEFT_SPLITTER_STATE_KEY),
            (self.right_splitter, self.RIGHT_SPLITTER_STATE_KEY),
        ):
            encoded_state = get_ui_setting(key, "")
            if not isinstance(encoded_state, str) or not encoded_state:
                continue
            try:
                state = QByteArray.fromHex(encoded_state.encode("ascii"))
            except Exception:
                continue
            if state.isEmpty():
                continue
            splitter.restoreState(state)

    def _persist_splitter_states(self) -> None:
        for splitter, key in (
            (self.body_splitter, self.BODY_SPLITTER_STATE_KEY),
            (self.left_splitter, self.LEFT_SPLITTER_STATE_KEY),
            (self.right_splitter, self.RIGHT_SPLITTER_STATE_KEY),
        ):
            state = bytes(splitter.saveState()).hex()
            set_ui_setting(key, state)

    def closeEvent(self, event) -> None:
        self._persist_splitter_states()
        super().closeEvent(event)

    def _on_render_existing_outputs_toggled(self, checked: bool) -> None:
        self.render_existing_outputs = checked
        set_ui_setting(self.RENDER_EXISTING_OUTPUTS_KEY, checked)
        self._refresh_detail_views()

    def _open_pipeline_manager(self) -> None:
        current_step_id = self.steps[self.current_step_index].id if self.steps else None
        current_stage = self.steps[self.current_step_index].stage if self.steps else None
        dialog = PipelineManagerDialog(self)
        if dialog.exec() != QDialog.Accepted:
            return
        self._reload_steps(current_step_id, current_stage)

    def _reload_steps(self, preferred_step_id: str | None = None, preferred_stage: str | None = None) -> None:
        self.steps = list(list_steps())
        self.statuses = {step.id: detect_status(step.id) for step in self.steps}
        self._populate_step_list()
        if not self.steps:
            return
        target_index = next((idx for idx, step in enumerate(self.steps) if step.id == preferred_step_id), -1)
        if target_index < 0 and preferred_stage:
            target_index = next((idx for idx, step in enumerate(self.steps) if step.stage == preferred_stage), -1)
        if target_index < 0:
            target_index = 0
        self.step_list.setCurrentRow(target_index)

    def _sync_stage_config_combo(self, stage: str) -> None:
        self._config_refreshing = True
        try:
            names = available_stage_configs(stage)
            current = get_active_config_name(stage)
            self.stage_config_combo.blockSignals(True)
            self.stage_config_combo.clear()
            self.stage_config_combo.addItems(names)
            self.stage_config_combo.setCurrentText(current)
            self.stage_config_combo.blockSignals(False)
        finally:
            self._config_refreshing = False

    def _on_stage_config_changed(self, config_name: str) -> None:
        if self._config_refreshing or not config_name:
            return
        stage = self.steps[self.current_step_index].stage
        current_step_id = self.steps[self.current_step_index].id
        set_active_config_name(stage, config_name)
        self._reload_steps(current_step_id, stage)

    def _on_step_changed(self, row: int) -> None:
        if row < 0 or row >= len(self.steps):
            return
        self.current_step_index = row
        self.current_table_index = 0
        self.current_image_index = 0
        step = self.steps[row]
        self.current_step_label.setText(step.name)
        self.step_hint_label.setText(step.description)
        self._sync_stage_config_combo(step.stage)
        self.check_button.setVisible(step.precheck_mode != "none")
        self._sync_run_button(step)
        self._sync_step_item_selection()
        self._refresh_detail_views()

    def _sync_run_button(self, step: StepDefinition) -> None:
        status = self.statuses.get(step.id, StepStatus.IDLE)
        if step.runner_type == RunnerType.MANUAL:
            self.run_button.setText("打开 Dearun")
            self.run_button.setEnabled(bool(step.command))
        elif step.runner_type == RunnerType.HYBRID and status == StepStatus.MANUAL_PENDING:
            self.run_button.setText("引导执行")
            self.run_button.setEnabled(True)
        else:
            self.run_button.setText("执行")
            self.run_button.setEnabled(status in {StepStatus.IDLE, StepStatus.READY, StepStatus.SUCCESS, StepStatus.MANUAL_PENDING})

        if step.precheck_mode != "none" and status == StepStatus.BLOCKED:
            self.run_button.setEnabled(False)

        self.next_button.setEnabled(self.current_step_index < len(self.steps) - 1)

    def _status_text(self, status: StepStatus) -> str:
        mapping = {
            StepStatus.IDLE: "未检查",
            StepStatus.BLOCKED: "检查未通过",
            StepStatus.READY: "可执行",
            StepStatus.RUNNING: "运行中",
            StepStatus.SUCCESS: "已完成",
            StepStatus.FAILED: "失败",
            StepStatus.MANUAL_PENDING: "需人工处理",
        }
        return mapping[status]

    def _display_status(self, step: StepDefinition, status: StepStatus) -> tuple[str, str]:
        runtime_color = {
            StepStatus.RUNNING: "#4f46e5",
            StepStatus.FAILED: "#dc2626",
            StepStatus.MANUAL_PENDING: "#a21caf",
        }
        if status in runtime_color:
            return f"● {self._status_text(status)}", runtime_color[status]

        output_health = detect_output_health(step.id)
        color_map = {
            "missing": "#dc2626",
            "stale": "#d97706",
            "fresh": "#16a34a",
        }
        return output_health.text, color_map[output_health.state.value]

    def _run_check(self) -> None:
        step = self.steps[self.current_step_index]
        result = check_step(step.id)
        self.console_panel.append_text("\n".join(result.messages))
        self.statuses[step.id] = StepStatus.READY if result.success and step.runner_type != RunnerType.MANUAL else (
            StepStatus.SUCCESS if result.success and step.runner_type == RunnerType.MANUAL else StepStatus.BLOCKED
        )
        if step.runner_type == RunnerType.MANUAL and not result.success:
            self.statuses[step.id] = StepStatus.MANUAL_PENDING
        self._refresh_step_item(self.current_step_index)
        self._sync_run_button(step)
        self._refresh_detail_views()

    def _run_current_step(self) -> None:
        step = self.steps[self.current_step_index]
        if self.process.state() != QProcess.NotRunning:
            QMessageBox.information(self, "运行中", "当前已有步骤在运行，请等待结束。")
            return

        preparation = run_step(step.id)
        self.console_panel.append_text(preparation.message)
        self.statuses[step.id] = preparation.status
        self._refresh_step_item(self.current_step_index)
        self._sync_run_button(step)

        if not preparation.allowed:
            if preparation.status == StepStatus.MANUAL_PENDING:
                QMessageBox.information(self, "人工步骤提示", preparation.message)
            else:
                QMessageBox.warning(self, "无法执行", preparation.message)
            self._refresh_detail_views()
            return

        if preparation.program == "__shell_open__":
            try:
                open_external_path(preparation.arguments[0])
                self.statuses[step.id] = StepStatus.MANUAL_PENDING
                self.console_panel.append_text("已打开 Dearun 安装目录，请完成人工操作后点击“检查”。")
            except OSError as exc:
                self.statuses[step.id] = StepStatus.FAILED
                self.console_panel.append_text(f"[失败] 打开 Dearun 路径失败：{exc}")
            self._refresh_step_item(self.current_step_index)
            self._sync_run_button(step)
            self._refresh_detail_views()
            return

        self.statuses[step.id] = StepStatus.RUNNING
        self.running_step_id = step.id
        self._refresh_step_item(self.current_step_index)
        self._sync_run_button(step)

        self.process.setWorkingDirectory(str(preparation.working_dir or PROJECT_ROOT))
        if step.runner_type == RunnerType.PYTHON:
            process_env = QProcessEnvironment.systemEnvironment()
            code_root = str((PROJECT_ROOT / "code" / "流水线").resolve())
            current_pythonpath = process_env.value("PYTHONPATH", "")
            merged_pythonpath = code_root if not current_pythonpath else f"{code_root};{current_pythonpath}"
            process_env.insert("PYTHONPATH", merged_pythonpath)
            self.process.setProcessEnvironment(process_env)
        self.process.start(preparation.program, preparation.arguments)
        if not self.process.waitForStarted(3000):
            self.console_panel.append_text("进程启动失败。")
            self.statuses[step.id] = StepStatus.FAILED
            self.running_step_id = None
            self._refresh_step_item(self.current_step_index)
            self._sync_run_button(step)

    def _read_stdout(self) -> None:
        text = self._decode_process_bytes(bytes(self.process.readAllStandardOutput()))
        self.console_panel.append_text(text)

    def _read_stderr(self) -> None:
        text = self._decode_process_bytes(bytes(self.process.readAllStandardError()))
        self.console_panel.append_text(text)

    def _decode_process_bytes(self, raw: bytes) -> str:
        if not raw:
            return ""
        encodings = [
            "utf-8",
            locale.getpreferredencoding(False),
            "gbk",
            "cp936",
        ]
        seen: set[str] = set()
        for encoding in encodings:
            if not encoding or encoding.lower() in seen:
                continue
            seen.add(encoding.lower())
            try:
                return raw.decode(encoding)
            except UnicodeDecodeError:
                continue
        return raw.decode("utf-8", errors="replace")

    def _on_process_finished(self, exit_code: int, exit_status) -> None:
        if self.running_step_id is None:
            return
        running_index = next((idx for idx, step in enumerate(self.steps) if step.id == self.running_step_id), self.current_step_index)
        step = self.steps[running_index]
        if exit_code == 0:
            self.statuses[step.id] = StepStatus.SUCCESS
            self.console_panel.append_text(f"[完成] {step.name} 已退出，exit_code={exit_code}")
        else:
            self.statuses[step.id] = StepStatus.FAILED
            self.console_panel.append_text(f"[失败] {step.name} 退出异常，exit_code={exit_code}")
        self.running_step_id = None
        self._refresh_step_item(running_index)
        if running_index == self.current_step_index:
            self._sync_run_button(step)
        self._refresh_detail_views()

    def _refresh_detail_views(self) -> None:
        step = self.steps[self.current_step_index]
        current_status = self.statuses.get(step.id, StepStatus.IDLE)
        if not self._should_render_outputs(current_status):
            self.current_artifacts = ArtifactBundle()
            self.table_panel.set_table(None, None, 0, 0)
            self.image_panel.set_image_path(None, 0, 0)
            self.markdown_panel.set_markdown_text(
                f"# {step.name}\n\n当前步骤状态：{self._status_text(current_status)}\n\n该步骤尚未完成"
            )
            return

        self.current_artifacts = discover_artifacts(step.id)
        self._render_table()
        self._render_image()
        self.markdown_panel.set_markdown_text(load_markdown(step.id, current_status))

    def _should_render_outputs(self, status: StepStatus) -> bool:
        return status == StepStatus.SUCCESS or self.render_existing_outputs

    def _render_table(self) -> None:
        total = len(self.current_artifacts.table_files)
        if total == 0:
            self.table_panel.set_table(None, None, 0, 0)
            return
        self.current_table_index %= total
        path = self.current_artifacts.table_files[self.current_table_index]
        try:
            frame = load_primary_table(self.steps[self.current_step_index].id, self.current_table_index)
        except Exception as exc:
            self.console_panel.append_text(f"[失败] 读取表格失败：{path}\n{exc}")
            frame = None
        self.table_panel.set_table(path, frame, self.current_table_index, total)

    def _render_image(self) -> None:
        total = len(self.current_artifacts.image_files)
        if total == 0:
            self.image_panel.set_image_path(None, 0, 0)
            return
        self.current_image_index %= total
        path = self.current_artifacts.image_files[self.current_image_index]
        self.image_panel.set_image_path(path, self.current_image_index, total)

    def _change_table(self, delta: int) -> None:
        if not self.current_artifacts.table_files:
            return
        self.current_table_index = (self.current_table_index + delta) % len(self.current_artifacts.table_files)
        self._render_table()

    def _change_image(self, delta: int) -> None:
        if not self.current_artifacts.image_files:
            return
        self.current_image_index = (self.current_image_index + delta) % len(self.current_artifacts.image_files)
        self._render_image()

    def _go_to_next_step(self) -> None:
        if self.current_step_index >= len(self.steps) - 1:
            return
        self.step_list.setCurrentRow(self.current_step_index + 1)


def build_application() -> QApplication:
    app = QApplication.instance() or QApplication([])
    font = QFont("Times New Roman", 11)
    font.setFamilies(["Times New Roman", "SimHei"])
    font.setHintingPreference(QFont.PreferFullHinting)
    font.setStyleStrategy(QFont.PreferAntialias)
    font.setWeight(QFont.Medium)
    app.setFont(font)
    return app
