from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from main_window import MainWindow, build_application


def main() -> int:
    app = build_application()
    try:
        window = MainWindow()
    except Exception as exc:
        QMessageBox.critical(None, "启动失败", str(exc))
        return 1
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
