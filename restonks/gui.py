#!/bin/env python3
import os
import sys
from PySide6.QtUiTools import QUiLoader
from PySide6.QtWidgets import (
    QApplication,
    QTableWidgetItem,
    QFileDialog,
    QDialog,
    QDialogButtonBox,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QComboBox,
    QMessageBox,
    QLabel,
    QWidget,
)
from PySide6.QtCore import QFile, QSettings

try:
    from . import lib
except ImportError:  # TODO: Remove this when packaging
    import lib

# TODO: Create configuration directory (linux: ~/.config/restonks, windows: %APPDATA%/restonks, macOS: ~/Library/Application Support/restonks)
# TODO: Save last configuration of weights for next session
# TODO: Save location of API keys file
# TODO: Add a button to clear everything
# TODO: Add update weight button
# TODO: Settings menu to set the default weights file and API keys file
# TODO: Handle resizing of the window

# Directory that contains this file (works whether run as a script or as a
# package module). Used to reliably locate the bundled ui/*.ui and ui/*.qss
# files regardless of the current working directory.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
THEMES_DIR = os.path.join(BASE_DIR, "ui")
ICONS_DIR = os.path.join(THEMES_DIR, "icons")
DEFAULT_THEME = "DarkMidnight"

SETTINGS_ORG = "restonks"
SETTINGS_APP = "restonks-gui"


class Add_popup(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Add Ticker")
        self.setGeometry(100, 100, 300, 200)

        # Create widgets
        self.add_ticker = QLineEdit()
        self.add_ticker.setPlaceholderText("Enter Ticker")
        self.add_weight = QLineEdit()
        self.add_weight.setPlaceholderText("Enter Weight (%)")
        button = QPushButton("Add position")

        # Add button signal to greetings slot
        button.clicked.connect(self.accept)

        # Create layout and add widgets
        layout = QVBoxLayout()
        layout.addWidget(self.add_ticker)
        layout.addWidget(self.add_weight)
        layout.addWidget(button)
        # Set dialog layout
        self.setLayout(layout)

    def get_values(self):
        return (self.add_ticker.text(), self.add_weight.text())


class RemovePopup(QDialog):
    def __init__(self, tickers_list):
        super().__init__()
        self.setWindowTitle("Remove Ticker")
        self.setGeometry(100, 100, 300, 150)
        self.selected_ticker = None  # Stores the ticker to remove

        # Dropdown list (QComboBox)
        self.combo_box = QComboBox()
        self.combo_box.addItems(tickers_list)

        # Remove button
        button_remove = QPushButton("Remove Selected Ticker")
        button_remove.clicked.connect(self.remove_ticker)

        # Layout
        layout = QVBoxLayout()
        layout.addWidget(QLabel("Select Ticker to Remove:"))
        layout.addWidget(self.combo_box)
        layout.addWidget(button_remove)
        self.setLayout(layout)

    def remove_ticker(self):
        self.selected_ticker = self.combo_box.currentText()
        if self.selected_ticker:
            confirm = QMessageBox.question(
                self,
                "Confirm Removal",
                f"Remove '{self.selected_ticker}'?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if confirm == QMessageBox.Yes:
                self.accept()  # Close dialog with "Accepted" status
            else:
                self.selected_ticker = None  # Reset if user cancels


class ThemePopup(QDialog):
    """Popup dialog that lets the user browse and preview installed
    themes live. Selecting a theme in the dropdown applies it to the
    whole application immediately, so the user can see it in context
    before committing. Cancelling restores whatever theme was active
    before the dialog was opened.
    """

    def __init__(self, app: QApplication, current_theme: str):
        super().__init__()
        self.app = app
        self.original_theme = current_theme

        self.setWindowTitle("Change Theme")
        self.setMinimumWidth(320)
        self.setGeometry(100, 100, 300, 150)

        self.themes = get_available_themes()

        layout = QVBoxLayout()
        layout.addWidget(QLabel("Pick a theme to preview it instantly:"))

        self.combo_box = QComboBox()
        self.combo_box.addItems(sorted(self.themes.keys()))
        if current_theme in self.themes:
            self.combo_box.setCurrentText(current_theme)
        self.combo_box.currentTextChanged.connect(self.preview_theme)
        layout.addWidget(self.combo_box)

        hint = QLabel("Click OK to keep it, or Cancel to revert.")
        hint.setStyleSheet("font-style: italic;")
        layout.addWidget(hint)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.setLayout(layout)

        # Show the currently selected theme applied right away, in case
        # the dropdown's initial selection differs from what's active.
        if self.combo_box.count() > 0:
            self.preview_theme(self.combo_box.currentText())

    def preview_theme(self, theme_name: str) -> None:
        if theme_name:
            apply_theme(self.app, theme_name)

    def reject(self) -> None:
        """Restore the original theme when the dialog is cancelled."""
        apply_theme(self.app, self.original_theme)
        super().reject()

    def selected_theme(self) -> str:
        return self.combo_box.currentText()


class RestonksWindow:
    """A class to represent the main window of the application.
    This class is responsible for loading the UI file, initializing the application,
    and handling user interactions.
    """

    ui: QWidget
    positions: dict[str, dict[str, str | float]]
    rebalance_orders: dict[str, dict[str, str | float]]

    def __init__(self, current_theme: str = DEFAULT_THEME):
        # Load the .ui file
        self.LoadUI()

        self.positions = {}
        self.rebalance_orders = {}
        self.current_theme = current_theme
        self.ui.setWindowTitle("Restonks")

        # Connect button callbacks
        self.ui.addButton.clicked.connect(self.handle_add)
        self.ui.removeButton.clicked.connect(self.handle_remove)
        self.ui.refreshButton.clicked.connect(self.handle_refresh)
        self.ui.rebalanceButton.clicked.connect(self.handle_rebalance)
        self.ui.actionImportWeights.triggered.connect(self.handle_import_weights)
        self.ui.actionExportWeights.triggered.connect(self.handle_export_weights)
        self.ui.actionImportAPIKey.triggered.connect(self.handle_import_api_keys)
        self.ui.actionChangeTheme.triggered.connect(self.handle_change_theme)

    def LoadUI(self) -> None:
        """Load the UI file and set up the main window."""
        ui_file_name = os.path.join(BASE_DIR, "ui", "main.ui")

        ui_file = QFile(ui_file_name)
        if not ui_file.open(QFile.ReadOnly):
            raise RuntimeError(f"Could not open UI file: {ui_file_name}")

        loader = QUiLoader()
        self.ui = loader.load(ui_file)
        ui_file.close()

        if self.ui is None:
            raise RuntimeError(f"Failed to load UI from: {ui_file_name}")

    def show(self) -> None:
        """Show the main window."""
        self.ui.show()

    # TODO: Check if ticker exists using Freedom 24 API
    def handle_add(self):
        popup = Add_popup()
        if popup.exec_() == QDialog.Accepted:  # Wait for dialog to close
            ticker, weight = popup.get_values()
            ticker = ticker.strip().upper()  # Clean up the ticker
            weight = weight.strip()
            try:
                weight = float(weight) / 100  # Convert to decimal
                if ticker in lib.config.weights:
                    self.ui.statusBar().showMessage(f"Ticker {ticker} already exists.")
                lib.config.add_weight(ticker, weight)
                self.update_weights_table()
                self.ui.statusBar().showMessage(
                    f"Added {ticker} with weight {weight:.2%}"
                )
            except ValueError:
                self.ui.statusBar().showMessage(f"Invalid weight: {weight}")
            except Exception as e:
                self.ui.statusBar().showMessage(f"Error adding weight: {e}")

    def handle_remove(self):
        popup = RemovePopup(lib.config.weights.keys())
        if popup.exec() == QDialog.Accepted:  # Wait for user action
            if popup.selected_ticker:  # Check if a ticker was selected
                lib.config.remove_weight(popup.selected_ticker)
                self.update_weights_table()
                self.ui.statusBar().showMessage(
                    f"Removed {popup.selected_ticker} from weights."
                )

    # Define callbacks
    def handle_refresh(self):
        """Handle the refresh button click event."""
        # Check if the API keys are set
        if not lib.config.is_api_set():
            self.handle_import_api_keys()
        self.positions = lib.get_all_positions()
        portfolio_eval = lib.get_portfolio_evaluation(self.positions)

        # Update textbxoxes with current portfolio evaluation and future portfolio
        # evaluation
        self.ui.curEvalAmountLabel.setText(f"${portfolio_eval:.2f}")

        # Update table with current portfolio
        portfolio_table = self.ui.portfolioTable
        portfolio_table.setRowCount(len(self.positions))
        portfolio_table.setColumnCount(6)
        portfolio_table.setHorizontalHeaderLabels(
            [
                "Ticker",
                "Market Price",
                "Shares",
                "Value",
                "Weight",
                "Target Weight",
            ]
        )

        for i, (ticker, position) in enumerate(self.positions.items()):
            portfolio_table.setItem(i, 0, QTableWidgetItem(ticker))
            portfolio_table.setItem(
                i, 1, QTableWidgetItem(f"${position['market_price']:.2f}")
            )
            portfolio_table.setItem(i, 2, QTableWidgetItem(f"{position['shares']:.0f}"))
            portfolio_table.setItem(
                i, 3, QTableWidgetItem(f"${position['market_value']:.2f}")
            )
            portfolio_table.setItem(i, 4, QTableWidgetItem(f"{position['weight']:.2%}"))
            portfolio_table.setItem(
                i, 5, QTableWidgetItem(f"{position['target_weight']:.2%}")
            )

    def handle_rebalance(self):
        lib.config.set_investment_amount(float(self.ui.amountBox.text()))
        rebalance_orders, remaining_cash = lib.find_rebalancing(self.positions)

        # Update table with rebalancing plan
        rebalance_table = self.ui.newPortfolioTable
        rebalance_table.setRowCount(len(rebalance_orders))

        for i, (ticker, order) in enumerate(rebalance_orders.items()):
            rebalance_table.setItem(i, 0, QTableWidgetItem(ticker))
            rebalance_table.setItem(i, 1, QTableWidgetItem(order["action"]))
            rebalance_table.setItem(i, 2, QTableWidgetItem(f"{order['shares']:.0f}"))
            rebalance_table.setItem(i, 3, QTableWidgetItem(f"${order['amount']:.2f}"))
            rebalance_table.setItem(
                i, 4, QTableWidgetItem(f"{order['new_weight']:.2%}")
            )

        future_portfolio_eval = (
            lib.get_portfolio_evaluation(self.positions)
            + lib.config.investment_amount
            - remaining_cash
        )

        self.ui.newEvalAmountLabel.setText(f"${future_portfolio_eval:.2f}")
        self.ui.remainingCashAmountLabel.setText(f"${remaining_cash:.2f}")

        # Update table with current portfolio
        updated_portfolio = lib.apply_rebalancing(self.positions, rebalance_orders)

        portfolio_table = self.ui.portfolioTable
        portfolio_table.setRowCount(len(updated_portfolio))
        portfolio_table.setColumnCount(9)
        portfolio_table.setHorizontalHeaderLabels(
            [
                "Ticker",
                "Market Price",
                "Shares",
                "Value",
                "Weight",
                "New Shares",
                "New Value",
                "New Weight",
                "Target Weight",
            ]
        )

        for i, ((ticker, pos), new_pos) in enumerate(
            zip(self.positions.items(), updated_portfolio.values())
        ):
            portfolio_table.setItem(i, 0, QTableWidgetItem(ticker))
            portfolio_table.setItem(
                i, 1, QTableWidgetItem(f"${pos['market_price']:.2f}")
            )
            portfolio_table.setItem(i, 2, QTableWidgetItem(f"{pos['shares']:.0f}"))
            portfolio_table.setItem(
                i, 3, QTableWidgetItem(f"${pos['market_value']:.2f}")
            )
            portfolio_table.setItem(i, 4, QTableWidgetItem(f"{pos['weight']:.2%}"))
            portfolio_table.setItem(i, 5, QTableWidgetItem(f"{new_pos['shares']:.0f}"))
            portfolio_table.setItem(
                i, 6, QTableWidgetItem(f"${new_pos['market_value']:.2f}")
            )
            portfolio_table.setItem(i, 7, QTableWidgetItem(f"{new_pos['weight']:.2%}"))
            portfolio_table.setItem(
                i, 8, QTableWidgetItem(f"{pos['target_weight']:.2%}")
            )

    def handle_import_weights(self):
        """Handle the import of weights from a toml file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self.ui, "Import Weights", "", "TOML Files (*.toml)"
        )
        if file_path:
            try:
                lib.config.import_weights_from_file(file_path)
                self.update_weights_table()
                self.ui.statusBar().showMessage(f"Imported weights from {file_path}")
            except Exception as e:
                self.ui.statusBar().showMessage(f"Error importing weights: {e}")

    def handle_import_api_keys(self):
        """Handle the import of API keys from a toml file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self.ui, "Import Freedom24 API Keys", "", "INI Files (*.ini)"
        )
        if file_path:
            try:
                lib.config.import_api_keys_from_file(file_path)
                self.ui.statusBar().showMessage(f"Imported API keys from {file_path}")
            except Exception as e:
                self.ui.statusBar().showMessage(f"Error importing API keys: {e}")

    def handle_export_weights(self):
        """Handle the export of weights to a toml file."""
        file_path, _ = QFileDialog.getSaveFileName(
            self.ui, "Export Weights TOML", "", "TOML Files (*.toml)"
        )
        if file_path:
            try:
                self.export_weights_to_file(file_path)
                self.ui.statusBar().showMessage(f"Exported weights to {file_path}")
            except Exception as e:
                self.ui.statusBar().showMessage(f"Error exporting weights: {e}")

    def export_weights_to_file(self, file_path: str) -> None:
        """Export the current weights to a TOML file."""
        with open(file_path, "w") as f:
            f.write("# Weights for the portfolio\n")
            f.write("ticker = [\n")
            for ticker, weight in lib.config.weights.items():
                f.write(f'    {{ name = "{ticker}", target_weight = {weight:f} }},\n')
            f.write("]\n")

    def handle_change_theme(self):
        """Open the theme picker popup. Themes are previewed live as the
        user browses; the choice is only kept (and persisted) if they
        click OK."""
        app = QApplication.instance()
        popup = ThemePopup(app, self.current_theme)
        if popup.exec() == QDialog.Accepted:
            self.current_theme = popup.selected_theme()
            apply_theme(app, self.current_theme)

            settings = QSettings(SETTINGS_ORG, SETTINGS_APP)
            settings.setValue("theme", self.current_theme)

            self.ui.statusBar().showMessage(f"Theme changed to {self.current_theme}")
        else:
            self.ui.statusBar().showMessage("Theme change cancelled")

    def update_weights_table(self):
        """Update the weights table with the current weights."""
        weights_table = self.ui.weightsTable
        weights_table.setRowCount(len(lib.config.weights))

        for i, (ticker, weight) in enumerate(lib.config.weights.items()):
            weights_table.setItem(i, 0, QTableWidgetItem(ticker))
            weights_table.setItem(i, 1, QTableWidgetItem(f"{weight:.2%}"))


def get_available_themes() -> dict[str, str]:
    """Scan the ui/ directory for *.qss files and return a mapping of
    {theme_name: absolute_path}. Theme name is the file name without the
    .qss extension, e.g. "ui/DarkMidnight.qss" -> "DarkMidnight". This
    means dropping a new .qss file into ui/ makes it available in the
    theme picker automatically, no code changes needed."""
    themes: dict[str, str] = {}
    if os.path.isdir(THEMES_DIR):
        for fname in sorted(os.listdir(THEMES_DIR)):
            if fname.lower().endswith(".qss"):
                name = os.path.splitext(fname)[0]
                themes[name] = os.path.join(THEMES_DIR, fname)
    return themes


def apply_theme(app: QApplication, theme: str) -> bool:
    """Apply a QSS theme (by name, case-insensitive) to the application.

    Returns True if the theme was found and applied, False otherwise. On
    failure the previously-applied stylesheet is left untouched rather
    than crashing, and a warning is printed.
    """
    themes = get_available_themes()
    match = next(
        (path for name, path in themes.items() if name.lower() == theme.lower()),
        None,
    )
    if match is None:
        available = ", ".join(themes) or "none found"
        print(f"[WARNING] Unknown theme '{theme}'. Available themes: {available}")
        return False

    try:
        with open(match, "r") as f:
            qss = f.read()
        # QSS url() paths for spinbox arrow icons are written as
        # "%ICONS_DIR%/..." placeholders in the theme files, since a
        # relative path would be resolved against the current working
        # directory (not the theme file's location) and break depending
        # on how/where the app is launched from. Substitute in the real
        # absolute path here. Qt's stylesheet engine wants forward
        # slashes even on Windows.
        icons_path = ICONS_DIR.replace(os.sep, "/")
        qss = qss.replace("%ICONS_DIR%", icons_path)
        app.setStyleSheet(qss)
        return True
    except OSError as e:
        print(f"[WARNING] Could not load theme '{theme}': {e}")
        return False


def main() -> int:
    app = QApplication(sys.argv)

    # Restore the last theme the user picked, falling back to the default
    # if nothing was saved yet or the saved theme no longer exists.
    settings = QSettings(SETTINGS_ORG, SETTINGS_APP)
    saved_theme = settings.value("theme", DEFAULT_THEME)

    available = get_available_themes()
    if saved_theme not in available:
        saved_theme = DEFAULT_THEME if DEFAULT_THEME in available else next(iter(available), "")

    if saved_theme:
        apply_theme(app, saved_theme)

    main_window = RestonksWindow(current_theme=saved_theme)
    main_window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
