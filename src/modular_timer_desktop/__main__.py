from __future__ import annotations

import sys
from pathlib import Path

# Allows running directly from source with:
# python src/modular_timer_desktop/__main__.py
SRC_DIR = Path(__file__).resolve().parents[1]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from modular_timer_desktop import __app_name__
from modular_timer_desktop.app import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(__app_name__)
    icon_path = Path(__file__).resolve().parents[2] / "assets" / "app.ico"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
