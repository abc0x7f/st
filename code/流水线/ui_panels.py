from __future__ import annotations

from pathlib import Path

import pandas as pd
from PySide6.QtCore import QEasingCurve, QEvent, QObject, QPoint, QPropertyAnimation, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPixmap, QTextOption
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
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


class FadeButton(QToolButton):
    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setText(text)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(44, 44)
        self.setStyleSheet(
            """
            QToolButton {
                border: 1px solid rgba(56, 69, 82, 0.18);
                border-radius: 22px;
                background: rgba(251, 252, 253, 0.9);
                color: #18212b;
                font-size: 22px;
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
        if hasattr(self.browser, "setMarkdown"):
            self.browser.setMarkdown(text)
        else:
            self.browser.setPlainText(text)


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
        button_y = self.height() - 56
        self.prev_button.move(18, button_y)
        self.next_button.move(self.width() - self.next_button.width() - 18, button_y)

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
        self.register_hover_target(self.table_view.viewport())

    def set_table(self, path: Path | None, frame: pd.DataFrame | None, index: int, total: int) -> None:
        self.model.set_frame(frame)
        self.path_label.setText(str(path) if path else "未发现 CSV")
        self.update_pager(index, total)
        self.table_view.resizeColumnsToContents()


class ZoomableImageView(QGraphicsView):
    scaleChanged = Signal(float)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.NoDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        self.setFrameShape(QFrame.NoFrame)
        self.setStyleSheet("background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 4px;")
        self.setStyleSheet("background: #f6f8fa; border: 1px solid #d4dce5; border-radius: 4px;")

        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self._pixmap_item = QGraphicsPixmapItem()
        self._scene.addItem(self._pixmap_item)
        self._dragging = False
        self._drag_origin = QPoint()
        self._current_scale = 1.0

    def set_image(self, image_path: Path | None) -> None:
        self.resetTransform()
        self._current_scale = 1.0
        if image_path is None or not image_path.exists():
            self._pixmap_item.setPixmap(QPixmap())
            self._scene.setSceneRect(0, 0, 1, 1)
            self.viewport().update()
            self.scaleChanged.emit(self._current_scale)
            return

        pixmap = QPixmap(str(image_path))
        self._pixmap_item.setPixmap(pixmap)
        self._scene.setSceneRect(pixmap.rect())
        self.fitInView(self._pixmap_item, Qt.KeepAspectRatio)
        self._current_scale = 1.0
        self.scaleChanged.emit(self._current_scale)

    def reset_view(self) -> None:
        self.resetTransform()
        self._current_scale = 1.0
        if not self._pixmap_item.pixmap().isNull():
            self.fitInView(self._pixmap_item, Qt.KeepAspectRatio)
        self.scaleChanged.emit(self._current_scale)

    def wheelEvent(self, event) -> None:
        if self._pixmap_item.pixmap().isNull():
            return
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.scale(factor, factor)
        self._current_scale *= factor
        self.scaleChanged.emit(self._current_scale)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._dragging = True
            self._drag_origin = event.pos()
            self.setCursor(Qt.ClosedHandCursor)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._dragging:
            delta = event.pos() - self._drag_origin
            self._drag_origin = event.pos()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._dragging = False
            self.setCursor(Qt.ArrowCursor)
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        self.reset_view()
        super().mouseDoubleClickEvent(event)


class ImagePanel(ArtifactNavigatorPanel):
    reset_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("图片渲染区", parent)
        self.path_label = QLabel("未发现图片")
        self.path_label.setStyleSheet("border: none; color: #5b6b7a;")
        self.outer_layout.addWidget(self.path_label)

        self.image_view = ZoomableImageView()
        self.outer_layout.addWidget(self.image_view, 1)

        footer = QHBoxLayout()
        footer.addStretch(1)
        footer.addWidget(self.page_label, 0)
        footer.addStretch(1)
        self.outer_layout.addLayout(footer)

        self.reset_button = FadeButton("⟳", self)
        self.reset_button.clicked.connect(self.reset_requested.emit)
        self.reset_button.raise_()

        self.register_hover_target(self.image_view.viewport())

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.reset_button.move((self.width() - self.reset_button.width()) // 2, self.height() - 56)

    def _set_overlay_visible(self, visible: bool) -> None:
        super()._set_overlay_visible(visible)
        self.reset_button.fade_to(visible and not self.image_view._pixmap_item.pixmap().isNull())

    def set_image_path(self, path: Path | None, index: int, total: int) -> None:
        self.path_label.setText(str(path) if path else "未发现图片")
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
