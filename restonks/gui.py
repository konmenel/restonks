#!/bin/env python3
import os
import sys
from PySide6.QtUiTools import QUiLoader
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QFile

class Restonks:
    def __init__(self):
        # Load the .ui file
        base, _ = os.path.split(__file__)
        ui_file_name = os.path.join(base, "ui/main.ui")
        ui_file = QFile(ui_file_name)
        ui_file.open(QFile.ReadOnly)
        loader = QUiLoader()
        self.window = loader.load(ui_file)
        ui_file.close()

        # Connect button callbacks
        self.window.addButton.clicked.connect(self.handle_add_position)

    # Define callbacks
    def handle_add_position(self):
        print("Add Position button clicked!")


def main() -> int:
    app = QApplication(sys.argv)

    restonks = Restonks()
    restonks.window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
