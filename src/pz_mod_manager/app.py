import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from pz_mod_manager.views.main_window import MainWindow

try:
    from pz_mod_manager._version import __version__
except ImportError:
    __version__ = "0.0.0"

_ICON_PATH = Path(__file__).parent / "resources" / "icon.png"
_STYLE_PATH = Path(__file__).parent / "resources" / "style.qss"


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setApplicationName("PZ Mod Manager")
    app.setApplicationVersion(__version__)

    if _ICON_PATH.exists():
        app.setWindowIcon(QIcon(str(_ICON_PATH)))

    if _STYLE_PATH.exists():
        app.setStyleSheet(_STYLE_PATH.read_text(encoding="utf-8"))

    window = MainWindow()
    window.show()

    sys.exit(app.exec())
