from __future__ import annotations

from pathlib import Path

import pandas as pd
from PySide6.QtCore import QEasingCurve, QEvent, QObject, QPoint, QPropertyAnimation, Qt, Signal, QUrl
from PySide6.QtGui import QColor, QTextDocument, QTextOption
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QSizePolicy,
    QTableView,
    QTextBrowser,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from table_model import DataFrameTableModel

try:
    from PySide6.QtWebEngineWidgets import QWebEngineView
except ImportError:
    QWebEngineView = None


def format_display_path(path: Path | None) -> str:
    if path is None:
        return ""
    try:
        project_root = Path(__file__).resolve().parents[2]
        return str(path.resolve().relative_to(project_root.resolve()))
    except ValueError:
        return str(path)


class FadeButton(QToolButton):
    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setText(text)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(58, 58)
        self.setStyleSheet(
            """
            QToolButton {
                border: 1px solid rgba(56, 69, 82, 0.18);
                border-radius: 29px;
                background: rgba(251, 252, 253, 0.9);
                color: #18212b;
                font-size: 26px;
                font-weight: 700;
            }
            QToolButton:hover {
                background: rgba(244, 246, 248, 0.98);
            }
            """
        )
        self._effect = QGraphicsOpacityEffect(self)
        self._effect.setOpacity(0.0)
        self.setGraphicsEffect(self._effect)
        self._animation = QPropertyAnimation(self._effect, b"opacity", self)
        self._animation.setDuration(180)
        self._animation.setEasingCurve(QEasingCurve.OutCubic)
        self.hide()

    def fade_to(self, visible: bool) -> None:
        self.setVisible(True)
        self._animation.stop()
        self._animation.setStartValue(self._effect.opacity())
        self._animation.setEndValue(1.0 if visible else 0.0)
        self._animation.start()
        if not visible:
            self._animation.finished.connect(self._hide_when_invisible)

    def _hide_when_invisible(self) -> None:
        if self._effect.opacity() <= 0.01:
            self.hide()
        try:
            self._animation.finished.disconnect(self._hide_when_invisible)
        except RuntimeError:
            pass


class PanelFrame(QFrame):
    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet(
            """
            QFrame {
                background: #fbfcfd;
                border: 1px solid #d8dee6;
                border-radius: 8px;
            }
            """
        )
        self.outer_layout = QVBoxLayout(self)
        self.outer_layout.setContentsMargins(14, 12, 14, 12)
        self.outer_layout.setSpacing(10)

        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("border: none; font-size: 17px; font-weight: 700; color: #18212b;")
        self.outer_layout.addWidget(self.title_label)


class ConsolePanel(PanelFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("控制台区", parent)
        self.editor = QPlainTextEdit()
        self.editor.setReadOnly(True)
        self.editor.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.editor.setStyleSheet(
            """
            QPlainTextEdit {
                border: 1px solid #d4dce5;
                border-radius: 4px;
                background: #f6f8fa;
                padding: 8px;
                color: #18212b;
            }
            """
        )
        self.editor.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.editor.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.outer_layout.addWidget(self.editor, 1)

    def append_text(self, text: str) -> None:
        if not text:
            return
        self.editor.appendPlainText(text.rstrip())
        self.editor.verticalScrollBar().setValue(self.editor.verticalScrollBar().maximum())

    def clear(self) -> None:
        self.editor.clear()


class MarkdownPanel(PanelFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("结果说明区", parent)
        self.browser: QTextBrowser | None = None
        self.web_view: QWebEngineView | None = None

        if QWebEngineView is not None:
            self.web_view = QWebEngineView()
            self.web_view.setStyleSheet(
                """
                QWebEngineView {
                    border: 1px solid #dfd5a6;
                    border-radius: 4px;
                    background: #fff7d6;
                }
                """
            )
            self.outer_layout.addWidget(self.web_view, 1)
        else:
            self.browser = QTextBrowser()
            self.browser.setOpenExternalLinks(True)
            self.browser.document().setDefaultTextOption(QTextOption(Qt.AlignLeft))
            self.browser.setStyleSheet(
                """
                QTextBrowser {
                    border: 1px solid #dfd5a6;
                    border-radius: 4px;
                    background: #fff7d6;
                    padding: 10px;
                    color: #18212b;
                }
                """
            )
            self.outer_layout.addWidget(self.browser, 1)

    def set_markdown_text(self, text: str) -> None:
        if self.web_view is not None:
            self.web_view.setHtml(self._build_html(text))
            return

        if self.browser is None:
            return
        if hasattr(self.browser, "setMarkdown"):
            self.browser.setMarkdown(text)
        else:
            self.browser.setPlainText(text)

    @staticmethod
    def _build_html(markdown_text: str) -> str:
        document = QTextDocument()
        document.setMarkdown(markdown_text)
        body_html = document.toHtml()
        return f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <style>
    body {{
      margin: 0;
      padding: 12px;
      background: #fff7d6;
      color: #18212b;
      font-family: "Times New Roman", "SimSun";
      line-height: 1.65;
      font-size: 15px;
    }}
    h1, h2, h3, h4, h5, h6 {{
      color: #18212b;
      margin-top: 1.1em;
      margin-bottom: 0.55em;
    }}
    p, li {{
      margin: 0.45em 0;
    }}
    pre, code {{
      font-family: "Consolas", "Courier New", monospace;
    }}
    table {{
      border-collapse: collapse;
      width: 100%;
      margin: 0.9em 0;
      background: #fffdf3;
    }}
    th, td {{
      border: 1px solid #dfd5a6;
      padding: 6px 8px;
      text-align: left;
    }}
    th {{
      background: #f8efc6;
    }}
    blockquote {{
      margin: 0.8em 0;
      padding-left: 0.9em;
      border-left: 4px solid #d8c36e;
      color: #4a5560;
    }}
  </style>
  <script>
    window.MathJax = {{
      tex: {{
        inlineMath: [['$', '$']],
        displayMath: [['$$', '$$']],
        processEscapes: true
      }},
      options: {{
        skipHtmlTags: ['script', 'noscript', 'style', 'textarea', 'pre', 'code']
      }}
    }};
  </script>
  <script async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script>
</head>
<body>
{body_html}
</body>
</html>
"""


class ArtifactNavigatorPanel(PanelFrame):
    navigate_previous = Signal()
    navigate_next = Signal()

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(title, parent)
        self._hover_targets: list[QWidget] = []
        self.page_label = QLabel("0 / 0")
        self.page_label.setAlignment(Qt.AlignCenter)
        self.page_label.setStyleSheet("border: none; color: #5b6b7a; font-size: 12px;")

        self.prev_button = FadeButton("‹", self)
        self.next_button = FadeButton("›", self)
        self.prev_button.clicked.connect(self.navigate_previous.emit)
        self.next_button.clicked.connect(self.navigate_next.emit)

        self.prev_button.raise_()
        self.next_button.raise_()

    def register_hover_target(self, target: QWidget) -> None:
        target.installEventFilter(self)
        target.setMouseTracking(True)
        self._hover_targets.append(target)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched in self._hover_targets:
            if event.type() in (QEvent.Enter, QEvent.MouseMove):
                self._set_overlay_visible(True)
            elif event.type() == QEvent.Leave:
                self._set_overlay_visible(False)
        return super().eventFilter(watched, event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)

    def _set_overlay_visible(self, visible: bool) -> None:
        self.prev_button.fade_to(visible and self.prev_button.isEnabled())
        self.next_button.fade_to(visible and self.next_button.isEnabled())

    def update_pager(self, current_index: int, total: int) -> None:
        if total <= 0:
            self.page_label.setText("0 / 0")
            self.prev_button.setEnabled(False)
            self.next_button.setEnabled(False)
        else:
            self.page_label.setText(f"{current_index + 1} / {total}")
            enabled = total > 1
            self.prev_button.setEnabled(enabled)
            self.next_button.setEnabled(enabled)


class TablePanel(ArtifactNavigatorPanel):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("表格展示区", parent)
        self.path_label = QLabel("未发现 CSV")
        self.path_label.setStyleSheet("border: none; color: #5b6b7a;")
        self.outer_layout.addWidget(self.path_label)

        self.table_view = QTableView()
        self.table_view.setAlternatingRowColors(True)
        self.table_view.setShowGrid(True)
        self.table_view.verticalHeader().setVisible(False)
        self.table_view.setWordWrap(False)
        self.table_view.setStyleSheet(
            """
            QTableView {
                border: 1px solid #d4dce5;
                border-radius: 4px;
                gridline-color: #e3e8ee;
                background: #fdfefe;
                selection-background-color: #e7edf3;
            }
            QHeaderView::section {
                background: #eff3f6;
                border: 0;
                border-right: 1px solid #d8dee6;
                border-bottom: 1px solid #d8dee6;
                padding: 6px;
                font-weight: 700;
            }
            """
        )
        self.model = DataFrameTableModel()
        self.table_view.setModel(self.model)
        self.outer_layout.addWidget(self.table_view, 1)
        self.outer_layout.addWidget(self.page_label)
        self.prev_button.setParent(self)
        self.next_button.setParent(self)
        self.prev_button.raise_()
        self.next_button.raise_()
        self.register_hover_target(self.table_view.viewport())

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        table_geom = self.table_view.geometry()
        center_y = max(18, (table_geom.height() - self.prev_button.height()) // 2)
        self.prev_button.move(table_geom.left() + 14, table_geom.top() + center_y)
        self.next_button.move(
            table_geom.left() + max(14, table_geom.width() - self.next_button.width() - 14),
            table_geom.top() + center_y,
        )
        self.prev_button.raise_()
        self.next_button.raise_()

    def set_table(self, path: Path | None, frame: pd.DataFrame | None, index: int, total: int) -> None:
        self.model.set_frame(frame)
        self.path_label.setText(format_display_path(path) if path else "未发现 CSV")
        self.update_pager(index, total)
        self.table_view.resizeColumnsToContents()


if QWebEngineView is not None:
    class WebImageView(QWebEngineView):
        def __init__(self, parent: QWidget | None = None) -> None:
            super().__init__(parent)
            self.setStyleSheet("background: #f6f8fa; border: 1px solid #d4dce5; border-radius: 4px;")
            self._current_path: Path | None = None
            self._has_image = False
            self._set_empty_html()

        def set_image(self, image_path: Path | None) -> None:
            if image_path is None or not image_path.exists():
                self._current_path = None
                self._has_image = False
                self._set_empty_html()
                return
            self._current_path = image_path
            self._has_image = True
            self._render_current()

        def reset_view(self) -> None:
            if self._current_path is None:
                return
            self.setZoomFactor(1.0)
            self._render_current()

        def _render_current(self) -> None:
            if self._current_path is None:
                self._set_empty_html()
                return
            image_url = QUrl.fromLocalFile(str(self._current_path.resolve())).toString()
            base_url = QUrl.fromLocalFile(str(self._current_path.parent.resolve()) + "/")
            self.setHtml(
                f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <style>
    html, body {{
      margin: 0;
      width: 100%;
      height: 100%;
      background: #f6f8fa;
      overflow: hidden;
    }}
    body {{
      user-select: none;
      -webkit-user-select: none;
    }}
    #stage {{
      position: relative;
      width: 100%;
      height: 100%;
      overflow: hidden;
      cursor: grab;
    }}
    #stage.dragging {{
      cursor: grabbing;
    }}
    #image {{
      position: absolute;
      left: 50%;
      top: 50%;
      max-width: none;
      max-height: none;
      transform-origin: center center;
      image-rendering: auto;
    }}
  </style>
</head>
<body>
  <div id="stage">
    <img id="image" src="{image_url}" alt="preview" draggable="false">
  </div>
  <script>
    const stage = document.getElementById("stage");
    const image = document.getElementById("image");

    let scale = 1.0;
    let offsetX = 0.0;
    let offsetY = 0.0;
    let dragging = false;
    let lastX = 0.0;
    let lastY = 0.0;
    let fitted = false;

    function clampScale(value) {{
      return Math.min(12, Math.max(0.1, value));
    }}

    function applyTransform() {{
      image.style.transform = `translate(calc(-50% + ${{offsetX}}px), calc(-50% + ${{offsetY}}px)) scale(${{scale}})`;
    }}

    function fitImage() {{
      const stageRect = stage.getBoundingClientRect();
      const naturalWidth = image.naturalWidth || 1;
      const naturalHeight = image.naturalHeight || 1;
      const fitScale = Math.min(stageRect.width / naturalWidth, stageRect.height / naturalHeight, 1);
      scale = fitScale > 0 ? fitScale : 1;
      offsetX = 0;
      offsetY = 0;
      fitted = true;
      applyTransform();
    }}

    image.addEventListener("load", () => {{
      fitImage();
    }});

    image.addEventListener("dragstart", (event) => {{
      event.preventDefault();
    }});

    stage.addEventListener("wheel", (event) => {{
      event.preventDefault();
      if (!fitted) {{
        fitImage();
      }}
      const factor = event.deltaY < 0 ? 1.12 : 1 / 1.12;
      scale = clampScale(scale * factor);
      applyTransform();
    }}, {{ passive: false }});

    stage.addEventListener("mousedown", (event) => {{
      if (event.button !== 0) {{
        return;
      }}
      dragging = true;
      lastX = event.clientX;
      lastY = event.clientY;
      stage.classList.add("dragging");
    }});

    window.addEventListener("mousemove", (event) => {{
      if (!dragging) {{
        return;
      }}
      offsetX += event.clientX - lastX;
      offsetY += event.clientY - lastY;
      lastX = event.clientX;
      lastY = event.clientY;
      applyTransform();
    }});

    window.addEventListener("mouseup", () => {{
      dragging = false;
      stage.classList.remove("dragging");
    }});

    stage.addEventListener("dblclick", (event) => {{
      event.preventDefault();
      fitImage();
    }});

    window.addEventListener("resize", () => {{
      fitImage();
    }});
  </script>
</body>
</html>
""",
                base_url,
            )

        def _set_empty_html(self) -> None:
            self.setHtml(
                """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <style>
    html, body {
      margin: 0;
      width: 100%;
      height: 100%;
      background: #f6f8fa;
      color: #6b7785;
      font-family: "Times New Roman", "SimSun";
    }
    body {
      display: flex;
      align-items: center;
      justify-content: center;
    }
  </style>
</head>
<body>未发现图片</body>
</html>
"""
            )
else:
    class WebImageView(QTextBrowser):
        def __init__(self, parent: QWidget | None = None) -> None:
            super().__init__(parent)
            self.setReadOnly(True)
            self.setOpenExternalLinks(True)
            self.setStyleSheet(
                """
                QTextBrowser {
                    border: 1px solid #d4dce5;
                    border-radius: 4px;
                    background: #f6f8fa;
                    color: #6b7785;
                    font-family: "Times New Roman", "SimSun";
                    padding: 10px;
                }
                """
            )
            self._current_path: Path | None = None
            self._has_image = False
            self.setHtml("<div style='text-align:center;'>未安装 QtWebEngine，无法渲染图片。</div>")

        def set_image(self, image_path: Path | None) -> None:
            self._current_path = image_path if image_path and image_path.exists() else None
            self._has_image = self._current_path is not None
            if self._current_path is None:
                self.setHtml("<div style='text-align:center;'>未发现图片</div>")
                return
            self.setHtml(
                f"<div style='text-align:center;'><p>当前环境未安装 QtWebEngine。</p><p>{format_display_path(self._current_path)}</p></div>"
            )

        def reset_view(self) -> None:
            return


class ImagePanel(ArtifactNavigatorPanel):
    reset_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("图片渲染区", parent)
        self.path_label = QLabel("未发现图片")
        self.path_label.setStyleSheet("border: none; color: #5b6b7a;")
        self.outer_layout.addWidget(self.path_label)

        self.image_view = WebImageView()
        self.outer_layout.addWidget(self.image_view, 1)

        footer = QHBoxLayout()
        footer.addStretch(1)
        footer.addWidget(self.page_label, 0)
        footer.addStretch(1)
        self.outer_layout.addLayout(footer)

        self.prev_button.setParent(self)
        self.next_button.setParent(self)
        self.reset_button = FadeButton("⟳", self)
        self.reset_button.clicked.connect(self.reset_requested.emit)
        self.prev_button.raise_()
        self.next_button.raise_()
        self.reset_button.raise_()

        self.register_hover_target(self.image_view)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        image_geom = self.image_view.geometry()
        center_y = max(18, (image_geom.height() - self.prev_button.height()) // 2)
        self.prev_button.move(image_geom.left() + 14, image_geom.top() + center_y)
        self.next_button.move(
            image_geom.left() + max(14, image_geom.width() - self.next_button.width() - 14),
            image_geom.top() + center_y,
        )
        self.reset_button.move(
            image_geom.left() + (image_geom.width() - self.reset_button.width()) // 2,
            image_geom.top() + max(14, image_geom.height() - self.reset_button.height() - 14),
        )
        self.prev_button.raise_()
        self.next_button.raise_()
        self.reset_button.raise_()

    def _set_overlay_visible(self, visible: bool) -> None:
        super()._set_overlay_visible(visible)
        self.reset_button.fade_to(visible and self.image_view._has_image)

    def set_image_path(self, path: Path | None, index: int, total: int) -> None:
        self.path_label.setText(format_display_path(path) if path else "未发现图片")
        self.image_view.set_image(path)
        self.update_pager(index, total)


def status_color(status: str) -> QColor:
    color_map = {
        "idle": QColor("#d7dfe9"),
        "blocked": QColor("#fde68a"),
        "ready": QColor("#bfdbfe"),
        "running": QColor("#c7d2fe"),
        "success": QColor("#bbf7d0"),
        "failed": QColor("#fecaca"),
        "manual_pending": QColor("#f5d0fe"),
    }
    return color_map.get(status, QColor("#e5e7eb"))
