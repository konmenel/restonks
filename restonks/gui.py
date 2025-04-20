#!/bin/env python3
import os
import sys
from PySide6.QtUiTools import QUiLoader
from PySide6.QtWidgets import QApplication, QTableWidgetItem
from PySide6.QtCore import QFile

try:
    from . import lib
except ImportError:  # TODO: Remove this when packaging
    import lib

# TODO: Add callbacks
# TODO: Add button to accept the API keys
# TODO: Add export weights into different file formats
# TODO: Save last configuration of weights for next session
# TODO: Create second tab/dock for results
# TODO: Pull list of securities on startup.


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
        self.window.refreshButton.clicked.connect(self.handle_refresh)

    # Define callbacks
    def handle_refresh(self):
        positions = lib.get_all_positions()
        print(positions)
        portfolio_table = self.window.portfolioTable
        portfolio_table.setRowCount(len(positions))

        for i, (ticker, position) in enumerate(positions.items()):
            portfolio_table.setItem(i, 0, QTableWidgetItem(ticker))
            portfolio_table.setItem(
                i, 1, QTableWidgetItem(f"{position['market_price']:.2f}")
            )
            portfolio_table.setItem(i, 2, QTableWidgetItem(f"{position['shares']:d}"))
            portfolio_table.setItem(
                i, 3, QTableWidgetItem(f"{position['market_value']:.2f}")
            )
            portfolio_table.setItem(i, 4, QTableWidgetItem(f"{position['weight']:.2%}"))
            portfolio_table.setItem(
                i, 5, QTableWidgetItem(f"{position['target_weight']:.2%}")
            )
        # self.window.portfolioTable.show()


def main() -> int:
    app = QApplication(sys.argv)

    # TODO: needs to be independent of current weights and api key file
    lib.config.initialise(
        api_key_file="tradernet.ini",
        weights_file="weights.toml",
        investment_amount=1000,
    )

    restonks = Restonks()
    restonks.window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
