#!/usr/bin/env python3
import os
import tempfile
from nicegui import ui, app

try:
    from . import lib
    from . import themes
except ImportError:
    import lib
    import themes


# --- Shared style fragments -------------------------------------------------
# Widgets reference theme colors through these CSS custom properties (see
# themes.py) instead of hardcoding Tailwind colors, so a single set of
# constants here is enough to keep every card/label/input in sync with
# whatever theme is active.
CARD = "rounded-xl shadow-md bg-secondary"
DIALOG_CARD = f"w-[450px] p-6 {CARD} shadow-2xl"
SECTION_TITLE = "text-lg font-bold border-b pb-2 mb-3 w-full"
FIELD_LABEL = "text-xs font-bold uppercase tracking-wide opacity-60"
MUTED_TEXT = "opacity-60"
UPLOAD_BOX = "w-full border border-dashed rounded-lg p-2 my-2"
ACTION_BUTTON = "w-full mt-6 py-3 font-bold text-base shadow-lg transition-transform hover:scale-[1.01]"


class RestonksApp:
    def __init__(self) -> None:
        """
        Manages UI-specific state. Core engine/config values live in the
        global `lib.config` instance.
        """
        self.positions: dict[str, dict[str, str | float]] = {}
        self.rebalance_orders: dict[str, dict[str, str | float]] = {}
        self.remaining_cash: float | None = None
        self.current_theme: str = themes.DEFAULT_THEME
        self.dark_mode = ui.dark_mode(themes.THEMES[themes.DEFAULT_THEME].dark)
        self.save_api = False

        self.load_theme_config()

    # --- Config-editing callbacks --------------------------------------

    def update_investment_amount(self, currency: str, val: float) -> None:
        try:
            lib.config.set_investment_amount(val if val is not None else 0.0, currency)
            self.render_summary.refresh()
        except ValueError as e:
            ui.notify(str(e), type="negative")

    def add_ticker(self) -> None:
        """Adds a new ticker row with a unique placeholder name."""
        placeholder = "TICK"
        counter = 1
        while placeholder in lib.config.weights:
            placeholder = f"TICK.{counter}"
            counter += 1

        try:
            lib.config.add_weight(placeholder, 0.0)
            self.refresh_weights_grid()
        except ValueError as e:
            ui.notify(str(e), type="negative")

    def update_ticker_name(self, old_name: str, new_name: str) -> None:
        if not new_name or old_name == new_name:
            return
        current_weights = lib.config.weights.copy()
        if old_name in current_weights:
            weight = current_weights.pop(old_name)
            current_weights[new_name] = weight
            try:
                lib.config.set_weights(current_weights)
            except ValueError as e:
                ui.notify(str(e), type="negative")
                self.refresh_weights_grid()

    def update_ticker_weight(self, ticker: str, new_weight: float) -> None:
        if new_weight is None:
            return
        current_weights = lib.config.weights.copy()
        current_weights[ticker] = new_weight
        try:
            lib.config.set_weights(current_weights)
        except ValueError as e:
            ui.notify(str(e), type="negative")
            self.refresh_weights_grid()  # revert on the client side

    def remove_ticker(self, ticker: str) -> None:
        try:
            lib.config.remove_weight(ticker)
            self.refresh_weights_grid()
        except KeyError as e:
            ui.notify(str(e), type="negative")

    def clear_inputs(self) -> None:
        try:
            lib.config.set_investment_amount(0.0)
            lib.config.set_weights({})
            self.refresh_weights_grid()
            ui.notify("Inputs cleared", type="info")
        except Exception as e:
            ui.notify(str(e), type="negative")

    def set_theme(self, theme_name: str) -> None:
        self.current_theme = theme_name
        themes.apply_theme(theme_name, self.dark_mode)
        self.save_theme_config()

    def set_save_api(self, value: bool) -> bool:
        self.save_api = value
        return self.save_api

    def save_theme_config(self) -> None:
        config_dir = lib.config.get_config_dir()

        if not config_dir.exists():
            os.makedirs(config_dir)

        with open(config_dir / "gui-theme", "w") as themefile:
            themefile.write(f"{self.current_theme}\n")

    def load_theme_config(self) -> None:
        config_dir = lib.config.get_config_dir()
        theme_filename = config_dir / "gui-theme"

        if theme_filename.exists() and theme_filename.is_file():
            with open(theme_filename, "r") as themefile:
                theme = themefile.readline().strip()
                self.current_theme = theme

        self.set_theme(self.current_theme)

    # --- Dialogs ---------------------------------------------------------

    def handle_api_config(self) -> None:
        """Dialog to set the Freedom24 API keys, either by uploading a
        `tradernet.ini` file or by typing them in directly."""
        with ui.dialog() as dialog, ui.card().classes(DIALOG_CARD).props("bordered"):
            ui.label("Freedom24 API Keys").classes("text-xl font-black mb-2")

            ui.label("Drag & Drop Configuration File").classes(f"{FIELD_LABEL} mt-2")

            async def handle_dropped_file(e):
                try:
                    with tempfile.NamedTemporaryFile(
                        delete=False, suffix=".ini"
                    ) as temp_file:
                        contents = await e.file.read()
                        temp_file.write(contents)
                        temp_file.flush()
                        file_path = temp_file.name

                    lib.config.import_api_keys_from_file(file_path)
                    if os.path.exists(file_path):
                        os.remove(file_path)

                    ui.notify(
                        f"Successfully imported API keys from {e.file.name}",
                        type="positive",
                    )
                    dialog.close()
                except Exception as ex:
                    ui.notify(
                        f"Failed to parse uploaded credentials file: {ex}",
                        type="negative",
                    )

            ui.upload(
                label="Drop your tradernet.ini here or click to browse",
                auto_upload=True,
                max_files=1,
                on_upload=handle_dropped_file,
            ).props("accept=.ini flat bordered").classes(UPLOAD_BOX)

            with ui.row().classes("w-full items-center my-4 justify-center gap-2"):
                ui.element("hr").classes("flex-grow")
                ui.label("OR").classes(
                    f"{MUTED_TEXT} text-xs font-bold tracking-widest"
                )
                ui.element("hr").classes("flex-grow")

            ui.label("Manual Key Entry").classes(f"{FIELD_LABEL} mb-2")
            public_input = (
                ui.input("Public Key").classes("w-full mb-2").props("outlined dense")
            )
            private_input = (
                ui.input("Private Key")
                .classes("w-full mb-4")
                .props("outlined dense password")
            )

            ui.checkbox(
                "Save Keys",
                value=self.save_api,
                on_change=lambda e: self.set_save_api(e.value),
            )

            with ui.row().classes("w-full justify-end gap-2 mt-2"):
                ui.button("Cancel", color="negative", on_click=dialog.close).props(
                    "flat dense"
                )

                def save_manual_keys():
                    if not public_input.value or not private_input.value:
                        ui.notify(
                            "Both Public and Private keys are required!",
                            type="warning",
                        )
                        return
                    try:
                        lib.config.initialise_from_dicts(
                            api_key={
                                "public": public_input.value,
                                "private": private_input.value,
                            },
                            weights=lib.config.weights,
                            investment_amount=lib.config.investment_amount,
                        )
                        ui.notify("API keys initialized successfully!", type="success")
                        dialog.close()
                    except Exception as ex:
                        ui.notify(f"Error setting credentials: {ex}", type="negative")

                ui.button("Save Keys", on_click=save_manual_keys).props(
                    "dense elevated color=primary"
                )

        dialog.open()

    def handle_import_weights(self) -> None:
        """Dialog to import target weights from a `weights.toml` file."""
        with ui.dialog() as dialog, ui.card().classes(DIALOG_CARD).props("bordered"):
            ui.label("Drag & Drop Weights File").classes(f"{FIELD_LABEL} mt-2")

            async def handle_dropped_file(e):
                try:
                    with tempfile.NamedTemporaryFile(
                        delete=False, suffix=".toml"
                    ) as temp_file:
                        contents = await e.file.read()
                        temp_file.write(contents)
                        temp_file.flush()
                        file_path = temp_file.name

                    lib.config.import_weights_from_file(file_path)
                    self.refresh_weights_grid()
                    if os.path.exists(file_path):
                        os.remove(file_path)

                    ui.notify(
                        f"Successfully imported weights from {e.file.name}",
                        type="positive",
                    )
                    dialog.close()
                except Exception as ex:
                    ui.notify(
                        f"Failed to parse uploaded weights file: {ex}",
                        type="negative",
                    )

            ui.upload(
                label="Drop your weights.toml here or click to browse",
                auto_upload=True,
                max_files=1,
                on_upload=handle_dropped_file,
            ).props("accept=.toml flat bordered").classes(UPLOAD_BOX)

        dialog.open()

    # --- Actions -----------------------------------------------------------

    def handle_shutdown(self) -> None:
        """Shutdowns the application."""
        lib.config.save(self.save_api)
        app.shutdown()

    def handle_export_weights(self) -> None:
        """Export weight to file."""
        try:
            toml_bytes = lib.config.export_weights_to_str().encode("utf-8")
            ui.download(toml_bytes, filename="weights.toml")
            ui.notify("Weights exported successfully!", type="positive")
        except Exception as e:
            ui.notify(f"Failed to export weights: {e}", type="negative")

    def handle_refresh_portfolio(self) -> None:
        """Refreshes the portfolio position from Freedom24."""
        if not lib.config.is_api_set():
            ui.notify(
                "API keys are missing. Please configure them first.",
                type="warning",
            )
            self.handle_api_config()
            return
        try:
            self.positions = lib.get_all_positions()
            self.remaining_cash = None
            self.rebalance_orders = {}
            self.render_portfolio_table.refresh()
            self.render_summary()
            ui.notify("Portfolio positions updated.", type="positive")
        except Exception as e:
            ui.notify(f"Failed to fetch portfolio: {e}", type="negative")

    def run_rebalancer_engine(self) -> None:
        if not self.positions:
            ui.notify(
                "Please fetch active portfolio positions before optimizing.",
                type="warning",
            )
            return
        try:
            orders, remaining_cash = lib.find_rebalancing(self.positions)
            self.rebalance_orders = orders
            self.remaining_cash = remaining_cash
            self.render_orders_table.refresh()
            self.render_summary.refresh()
            ui.notify(
                f"Rebalancing completed! Remaining cash: ${remaining_cash:.2f}",
                type="success",
            )
        except Exception as e:
            ui.notify(f"Execution error: {e}", type="negative")

    # --- Renderers -----------------------------------------------------------

    @ui.refreshable
    def render_weights_grid(self) -> None:
        weights_dict = lib.config.weights

        if not weights_dict:
            ui.label("No tickers added yet.").classes(
                f"{MUTED_TEXT} italic py-4 text-center w-full col-span-3"
            )
            return

        with ui.grid(columns=3).classes("w-full items-center gap-x-2 gap-y-3 mb-4"):
            ui.label("Ticker").classes(FIELD_LABEL)
            ui.label("Weight (Fraction)").classes(FIELD_LABEL)
            ui.label("")

            for ticker, weight in list(weights_dict.items()):
                ui.input(
                    value=ticker,
                    on_change=lambda e, t=ticker: self.update_ticker_name(t, e.value),
                ).props("dense outlined square").classes("text-sm font-bold")

                ui.number(
                    value=weight,
                    format="%.2f",
                    step=0.05,
                    on_change=lambda e, t=ticker: self.update_ticker_weight(t, e.value),
                ).props("dense outlined square")

                ui.button(
                    icon="delete",
                    color="negative",
                    on_click=lambda t=ticker: self.remove_ticker(t),
                ).props("flat dense")

    def refresh_weights_grid(self) -> None:
        self.render_weights_grid.refresh()

    @staticmethod
    def _format_currency(value: str | float) -> str:
        return f"${value:.2f}" if isinstance(value, (int, float)) else value

    @staticmethod
    def _format_percent(value: str | float) -> str:
        return f"{value:.1%}" if isinstance(value, (int, float)) else value

    @ui.refreshable
    def render_portfolio_table(self) -> None:
        rows = [
            {
                "ticker": ticker,
                "market_price": self._format_currency(data["market_price"]),
                "shares": data["shares"],
                "market_value": self._format_currency(data["market_value"]),
                "weight": self._format_percent(data["weight"]),
            }
            for ticker, data in self.positions.items()
        ]

        columns = [
            {"name": "ticker", "label": "Ticker", "field": "ticker", "align": "left"},
            {
                "name": "market_price",
                "label": "Price",
                "field": "market_price",
                "align": "right",
            },
            {
                "name": "shares",
                "label": "Shares Owned",
                "field": "shares",
                "align": "right",
            },
            {
                "name": "market_value",
                "label": "Market Value",
                "field": "market_value",
                "align": "right",
            },
            {
                "name": "weight",
                "label": "Fraction",
                "field": "weight",
                "align": "right",
            },
        ]
        ui.table(columns=columns, rows=rows, row_key="ticker").classes(
            "w-full bg-transparent shadow-none"
        ).props("flat")

    @ui.refreshable
    def render_orders_table(self) -> None:
        rows = [
            {
                "ticker": ticker,
                "action": data["action"],
                "shares": data["shares"],
                "amount": self._format_currency(data["amount"]),
                "new_weight": self._format_percent(data["new_weight"]),
            }
            for ticker, data in self.rebalance_orders.items()
        ]

        columns = [
            {"name": "ticker", "label": "Ticker", "field": "ticker", "align": "left"},
            {"name": "action", "label": "Action", "field": "action", "align": "center"},
            {
                "name": "shares",
                "label": "Target Shares",
                "field": "shares",
                "align": "right",
            },
            {
                "name": "amount",
                "label": "Total Cost",
                "field": "amount",
                "align": "right",
            },
            {
                "name": "new_weight",
                "label": "Projected Fraction",
                "field": "new_weight",
                "align": "right",
            },
        ]
        ui.table(columns=columns, rows=rows, row_key="ticker").classes(
            "w-full bg-transparent shadow-none"
        ).props("flat")

    @ui.refreshable
    def render_summary(self) -> None:
        current_eval = (
            lib.get_portfolio_evaluation(self.positions) if self.positions else 0.0
        )

        try:
            investment = lib.config.investment_amount
        except Exception:
            investment = 0.0

        if self.remaining_cash is None:
            new_eval_text = "—"
            remaining_cash_text = "—"
        else:
            new_eval = current_eval + investment - self.remaining_cash
            new_eval_text = f"${new_eval:,.2f}"
            remaining_cash_text = f"${self.remaining_cash:,.2f}"

        stats = [
            ("Current Evaluation", f"${current_eval:,.2f}"),
            ("Investment (USD equiv.)", f"${investment:,.2f}"),
            ("Projected Evaluation", new_eval_text),
            ("Remaining Cash", remaining_cash_text),
        ]
        with ui.grid(columns=4).classes("w-full gap-4"):
            for label, value in stats:
                with ui.column().classes("gap-1"):
                    ui.label(label).classes(FIELD_LABEL)
                    ui.label(value).classes("text-xl font-bold")

    # --- Layout -----------------------------------------------------------

    def build_header(self) -> None:
        with (
            ui.row()
            .classes(f"w-full justify-between items-center p-4 shadow-lg {CARD}")
            .props("bordered")
        ):
            with ui.row().classes("items-center gap-3"):
                ui.icon("account_balance_wallet", size="md").classes("text-primary")
                ui.label("restonks").classes("text-2xl font-black tracking-wide")
                ui.label("Portfolio Rebalancer").classes(f"{MUTED_TEXT} text-sm mt-1")

            with ui.row().classes("items-center"):
                ui.select(
                    themes.THEME_NAMES,
                    label="Theme",
                    value=self.current_theme,
                    on_change=lambda e: self.set_theme(e.value),
                ).classes("w-48")

                ui.button(
                    icon="power_settings_new",
                    color="negative",
                    on_click=app.shutdown,
                ).props("flat dense")

    def build_controls_ribbon(self) -> None:
        with ui.card().classes(f"w-full p-6 shadow-md {CARD}").props("bordered"):
            with ui.row().classes("w-full gap-6 items-center flex-wrap lg:flex-nowrap"):
                ui.number(
                    label="Investment (USD)",
                    value=lib.config.investment_amounts.get("USD", 0.0),
                    format="%.2f",
                    step=50,
                    on_change=lambda e: self.update_investment_amount("USD", e.value),
                ).classes("w-40 font-semibold").props("outlined dense")

                ui.number(
                    label="Investment (EUR)",
                    value=lib.config.investment_amounts.get("EUR", 0.0),
                    format="%.2f",
                    step=50,
                    on_change=lambda e: self.update_investment_amount("EUR", e.value),
                ).classes("w-40 font-semibold").props("outlined dense")

                with ui.row().classes("gap-2 flex-grow justify-start lg:justify-end"):
                    ui.button(
                        "Import Weights",
                        icon="file_upload",
                        on_click=self.handle_import_weights,
                    ).props("outline dense")
                    ui.button(
                        "Export Weights",
                        icon="file_download",
                        on_click=self.handle_export_weights,
                    ).props("outline dense")
                    ui.button(
                        "API Configuration",
                        icon="vpn_key",
                        on_click=self.handle_api_config,
                    ).props("outline dense")
                    ui.button(
                        "Clear All",
                        icon="delete_sweep",
                        color="negative",
                        on_click=self.clear_inputs,
                    ).props("flat dense")

    def build_ui(self) -> None:
        with ui.column().classes("w-full max-w-7xl mx-auto p-6 gap-6"):
            self.build_header()
            self.build_controls_ribbon()

            with ui.grid().classes(
                "grid-cols-1 lg:grid-cols-3 gap-6 w-full items-start"
            ):
                with (
                    ui.card()
                    .classes(f"col-span-1 p-5 flex flex-col {CARD}")
                    .props("bordered")
                ):
                    ui.label("Target Allocations").classes(f"{SECTION_TITLE}")
                    self.render_weights_grid()
                    ui.button(
                        "Add Ticker", icon="add", on_click=self.add_ticker
                    ).classes("w-full mt-6").props("outline dense")

                with ui.column().classes("col-span-1 lg:col-span-2 gap-6"):
                    with ui.card().classes(f"w-full p-5 {CARD}").props("bordered"):
                        ui.label("Current Portfolio State").classes(SECTION_TITLE)
                        self.render_portfolio_table()
                        ui.button(
                            "Refresh Portfolio",
                            icon="refresh",
                            on_click=self.handle_refresh_portfolio,
                        ).classes(ACTION_BUTTON)

                    with ui.card().classes(f"w-full p-5 {CARD}").props("bordered"):
                        ui.label("Calculated Rebalancing Actions").classes(
                            f"{SECTION_TITLE}"
                        )
                        self.render_orders_table()
                        ui.button(
                            "Calculate Rebalancing Plan",
                            icon="analytics",
                            on_click=self.run_rebalancer_engine,
                        ).classes(ACTION_BUTTON)

        themes.apply_theme(self.current_theme, self.dark_mode)


def main() -> int:
    lib.config.load()
    restonks_app = RestonksApp()
    app.on_shutdown(restonks_app.handle_shutdown)
    restonks_app.build_ui()
    ui.run(title="restonks - Portfolio Manager", reload=__name__ == "__main__")
    return 0


if __name__ in {"__main__", "__mp_main__"}:
    main()
