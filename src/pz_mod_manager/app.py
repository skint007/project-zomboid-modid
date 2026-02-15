import sys

from PySide6.QtWidgets import QApplication

from pz_mod_manager.views.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("PZ Mod Manager")
    app.setApplicationVersion("0.1.0")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())
