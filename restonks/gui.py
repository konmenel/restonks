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

# TODO: Add new values and weights to the table

# TODO: Add callbacks
# TODO: Add button to accept the API keys
# TODO: Add export weights into different file formats
# TODO: Save last configuration of weights for next session
# TODO: Create second tab/dock for results
# TODO: Pull list of securities on startup.


class Restonks:
    positions: dict[str, dict[str, str | float]]
    rebalance_orders: dict[str, dict[str, str | float]]

    def __init__(self):
        # Load the .ui file
        base, _ = os.path.split(__file__)
        ui_file_name = os.path.join(base, "ui/main.ui")
        ui_file = QFile(ui_file_name)
        ui_file.open(QFile.ReadOnly)
        loader = QUiLoader()
        self.window = loader.load(ui_file)
        ui_file.close()

        self.positions = {}
        self.rebalance_orders = {}

        # Connect button callbacks
        self.window.refreshButton.clicked.connect(self.handle_refresh)
        self.window.rebalanceButton.clicked.connect(self.handle_rebalance)

    # Define callbacks
    def handle_refresh(self):
        lib.config.set_investment_amount(float(self.window.amountBox.text()))
        self.positions = lib.get_all_positions()
        portfolio_eval = lib.get_portfolio_evaluation(self.positions)
        future_portfolio_eval = portfolio_eval + lib.config.investment_amount

        # Update textbxoxes with current portfolio evaluation and future portfolio evaluation
        self.window.curEvalAmountLabel.setText(f"${portfolio_eval:.2f}")
        self.window.newEvalAmountLabel.setText(f"${future_portfolio_eval:.2f}")

        # Update table with current portfolio
        portfolio_table = self.window.portfolioTable
        portfolio_table.setRowCount(len(self.positions))

        for i, (ticker, position) in enumerate(self.positions.items()):
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

    def handle_rebalance(self):
        rebalance_orders, remaining_cash = lib.find_rebalancing(self.positions)

        # Update table with rebalancing plan
        rebalance_table = self.window.newPortfolioTable
        rebalance_table.setRowCount(len(rebalance_orders))

        for i, (ticker, order) in enumerate(rebalance_orders.items()):
            rebalance_table.setItem(i, 0, QTableWidgetItem(ticker))
            rebalance_table.setItem(i, 1, QTableWidgetItem(order["action"]))
            rebalance_table.setItem(i, 2, QTableWidgetItem(f"{order['shares']:d}"))
            rebalance_table.setItem(i, 3, QTableWidgetItem(f"${order['amount']:.2f}"))
            rebalance_table.setItem(
                i, 4, QTableWidgetItem(f"{order['new_weight']:.2%}")
            )

        # Update remaining cash label
        # self.window.remainingCashLabel.setText(f"${remaining_cash:.2f}")


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
