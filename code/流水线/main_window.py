from __future__ import annotations

import locale

from PySide6.QtCore import QProcess, QProcessEnvironment, Qt, QSize
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from pipeline_config import LOGO_PATH, PROJECT_ROOT
from pipeline_service import (
    check_step,
    detect_status,
    discover_artifacts,
    list_steps,
    load_markdown,
    load_primary_table,
    open_external_path,
    run_step,
)
from step_types import ArtifactBundle, RunnerType, StepDefinition, StepStatus
from ui_panels import ConsolePanel, ImagePanel, MarkdownPanel, TablePanel, status_color


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("光碳智绘：省域碳排放效率可视分析")
        self.resize(1640, 980)
        self.setMinimumSize(QSize(1320, 840))

        self.steps = list(list_steps())
        self.statuses = {step.id: detect_status(step.id) for step in self.steps}
        self.current_step_index = 0
        self.current_table_index = 0
        self.current_image_index = 0
        self.current_artifacts = ArtifactBundle()
        self.running_step_id: str | None = None

        self.process = QProcess(self)
        self.process.readyReadStandardOutput.connect(self._read_stdout)
        self.process.readyReadStandardError.connect(self._read_stderr)
        self.process.finished.connect(self._on_process_finished)

        self._build_ui()
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
            """
        )
        self.setCentralWidget(central)

        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(18, 18, 18, 18)
        root_layout.setSpacing(14)

        root_layout.addWidget(self._build_header())

        body_splitter = QSplitter(Qt.Horizontal)
        body_splitter.setChildrenCollapsible(False)
        body_splitter.addWidget(self._build_left_column())
        body_splitter.addWidget(self._build_right_column())
        body_splitter.setStretchFactor(0, 3)
        body_splitter.setStretchFactor(1, 5)
        root_layout.addWidget(body_splitter, 1)

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

        title_label = QLabel("光碳智绘：省域碳排放效率可视分析")
        title_label.setStyleSheet("border: none; font-size: 32px; font-weight: 800; color: #18212b;")
        title_label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)

        self.version_label = QLabel("GUI v0.2")
        self.version_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.version_label.setStyleSheet("border: none; color: #6b7785; font-size: 12px; font-weight: 600;")

        title_block_layout.addWidget(title_label)
        title_block_layout.addWidget(self.version_label)

        layout.addWidget(logo_label, 0)
        layout.addWidget(title_block, 1)
        return frame

    def _build_left_column(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        self.step_list = QListWidget()
        self.step_list.setMinimumHeight(210)
        self.step_list.setStyleSheet(
            """
            QListWidget {
                border: 1px solid #d8dee6;
                border-radius: 8px;
                background: #fbfcfd;
                padding: 6px;
            }
            QListWidget::item {
                border-radius: 6px;
                margin: 3px 0px;
                padding: 10px 12px;
            }
            QListWidget::item:selected {
                background: #e8eef3;
                color: #18212b;
            }
            """
        )
        self.step_list.currentRowChanged.connect(self._on_step_changed)
        layout.addWidget(self.step_list)

        execute_frame = QFrame()
        execute_frame.setStyleSheet("QFrame { background: #fbfcfd; border: 1px solid #d8dee6; border-radius: 8px; }")
        execute_layout = QVBoxLayout(execute_frame)
        execute_layout.setContentsMargins(14, 10, 14, 12)
        execute_layout.setSpacing(10)

        self.current_step_label = QLabel("当前步骤")
        self.current_step_label.setAlignment(Qt.AlignCenter)
        self.current_step_label.setStyleSheet("border: none; font-size: 20px; font-weight: 800;")
        execute_layout.addWidget(self.current_step_label)

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
        layout.addWidget(execute_frame)

        self.console_panel = ConsolePanel()
        layout.addWidget(self.console_panel, 2)

        self.table_panel = TablePanel()
        self.table_panel.navigate_previous.connect(lambda: self._change_table(-1))
        self.table_panel.navigate_next.connect(lambda: self._change_table(1))
        layout.addWidget(self.table_panel, 3)
        return container

    def _build_right_column(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        self.image_panel = ImagePanel()
        self.image_panel.navigate_previous.connect(lambda: self._change_image(-1))
        self.image_panel.navigate_next.connect(lambda: self._change_image(1))
        self.image_panel.reset_requested.connect(self.image_panel.image_view.reset_view)
        layout.addWidget(self.image_panel, 5)

        self.markdown_panel = MarkdownPanel()
        layout.addWidget(self.markdown_panel, 4)
        return container

    def _populate_step_list(self) -> None:
        self.step_list.clear()
        for step in self.steps:
            status = self.statuses.get(step.id, StepStatus.IDLE)
            item = QListWidgetItem(f"{step.stage} | {step.name}\n{self._status_text(status)}")
            item.setData(Qt.UserRole, step.id)
            item.setBackground(status_color(status.value))
            self.step_list.addItem(item)

    def _refresh_step_item(self, row: int) -> None:
        step = self.steps[row]
        item = self.step_list.item(row)
        status = self.statuses.get(step.id, StepStatus.IDLE)
        item.setText(f"{step.stage} | {step.name}\n{self._status_text(status)}")
        item.setBackground(status_color(status.value))

    def _refresh_executable_summary(self) -> None:
        self.version_label.setText("GUI v0.2 | PySide6")

    def _on_step_changed(self, row: int) -> None:
        if row < 0 or row >= len(self.steps):
            return
        self.current_step_index = row
        self.current_table_index = 0
        self.current_image_index = 0
        step = self.steps[row]
        self.current_step_label.setText(step.name)
        self.step_hint_label.setText(step.description)
        self.check_button.setVisible(step.precheck_mode != "none")
        self._sync_run_button(step)
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
            process_env.insert("GUI_EXPORT_SVG", "1")
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
        return status == StepStatus.SUCCESS

    def _render_table(self) -> None:
        total = len(self.current_artifacts.csv_files)
        if total == 0:
            self.table_panel.set_table(None, None, 0, 0)
            return
        self.current_table_index %= total
        path = self.current_artifacts.csv_files[self.current_table_index]
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
        if not self.current_artifacts.csv_files:
            return
        self.current_table_index = (self.current_table_index + delta) % len(self.current_artifacts.csv_files)
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
