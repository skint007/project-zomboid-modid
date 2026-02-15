import sys

from PySide6.QtWidgets import QApplication

from pz_mod_manager.views.main_window import MainWindow

try:
    from pz_mod_manager._version import __version__
except ImportError:
    __version__ = "0.0.0"


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("PZ Mod Manager")
    app.setApplicationVersion(__version__)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())
