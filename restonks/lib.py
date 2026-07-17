import os
import time
import errno
import tomllib
import platform
import keyring as kr
from pathlib import Path
from tradernet import Tradernet
from functools import wraps
from copy import deepcopy


# TODO: Add sell action as option.
# TODO: Setup MYPY


class Config:
    """Manages the configuration of the script.

    Raises
    ------
    FileNotFoundError
        If weights file is not found.

    ValueError
        If investement amount is negative.
    """

    _api: Tradernet
    _weights: dict[str, float]
    _investment_amounts: dict[str, float]

    def __init__(self) -> None:
        self._api = None
        self._weights = {}
        self._investment_amounts = {"EUR": 0.0, "USD": 0.0}

    def initialise_from_files(
        self, api_key_file: str, weights_file: str, investment_amount: float
    ) -> None:
        if not os.path.exists(weights_file):
            raise FileNotFoundError(
                errno.ENOENT, os.strerror(errno.ENOENT), weights_file
            )
        if not os.path.exists(api_key_file):
            raise FileNotFoundError(
                errno.ENOENT, os.strerror(errno.ENOENT), api_key_file
            )
        if investment_amount < 0:
            ValueError("Investment amount cannot be negative!")

        self._investment_amounts["USD"] = investment_amount
        self.import_weights_from_file(weights_file)
        self.import_api_keys_from_file(api_key_file)

    def initialise_from_dicts(
        self,
        api_key: dict[str, str],
        weights: dict[str, float],
        investment_amount: float,
    ) -> None:
        if not isinstance(api_key, dict):
            raise TypeError("API key must be a dictionary!")
        if not isinstance(weights, dict):
            raise TypeError("Weights must be a dictionary!")
        if investment_amount < 0:
            raise ValueError("Investment amount cannot be negative!")

        self._api = Tradernet(api_key["public"], api_key["private"])
        self._weights = weights
        self._investment_amounts["USD"] = investment_amount

    @property
    def api(self) -> Tradernet:
        """Get the API object."""
        if self._api is None:
            raise ValueError("API not initialized!")
        return self._api

    @property
    def weights(self) -> dict[str, float]:
        """Get the weights."""
        return self._weights

    @property
    def investment_amounts(self) -> dict[str, float]:
        """Get the investment amount for each currency, e.g. {"USD": 500.0, "EUR": 200.0}."""
        return self._investment_amounts

    @property
    def investment_amount(self) -> float:
        """Get the investment amount in USD."""
        if not self._investment_amounts:
            return 0.0

        total = 0.0
        for currency, amount in self._investment_amounts.items():
            if amount <= 0.0:
                continue
            total += amount * get_exchange_rate(currency, "USD")
        return total

    def get_config_dir(self) -> Path:
        """Returns the configuration directory:
        - Linux: "$HOME/.config/restonks",
        - Windows: "%APPDATA%/restonks",
        - MacOS: "$HOME/Library/Application Support/restonks"
        """
        match platform.system():
            case "Linux":
                return Path(os.environ["HOME"], ".config", "restonks")
            case "Darwin":
                return Path(
                    os.environ["HOME"], "Library", "Application Support", "restonks"
                )
            case "Windows":
                return Path(os.environ["APPDATA"], "restonks")
            case _:
                raise Exception(f"Unsupported OS: {platform.system()}")

    def load(self) -> None:
        """Loads configuration from configuration directory and keyring"""
        config_dir = self.get_config_dir()
        if not config_dir.exists():
            return

        weights_file = config_dir / "weights.toml"
        if not self.weights and weights_file.exists() and weights_file.is_file():
            self.import_weights_from_file(weights_file)

        if not self.is_api_set():
            private = kr.get_password("tradernet", "private")
            public = kr.get_password("tradernet", "public")
            if public and private:
                self._api = Tradernet(public, private)

    def save(self, save_api: bool = True, save_weights=True) -> None:
        """Saves configuration to configuration directory and keyring"""
        config_dir = self.get_config_dir()
        if not config_dir.exists():
            os.makedirs(config_dir, exist_ok=True)

        if save_weights and self.weights:
            weights_file = config_dir / "weights.toml"
            self.export_weights_to_file(weights_file)

        if save_api and self.is_api_set():
            kr.set_password("tradernet", "public", self.api.public)
            kr.set_password("tradernet", "private", self.api._private)

    def set_api_keys(self, public: str, private: str) -> None:
        """Set the Freedom24 API keys directly, without touching the
        current weights or investment amounts."""
        self._api = Tradernet(public, private)

    def is_api_set(self) -> bool:
        """Check if the API is set."""
        return self._api is not None

    def import_api_keys_from_file(self, api_key_file: str) -> None:
        """Import the API keys from a file."""
        if not os.path.exists(api_key_file):
            raise FileNotFoundError(
                errno.ENOENT, os.strerror(errno.ENOENT), api_key_file
            )
        self._api = Tradernet.from_config(api_key_file)

    def set_investment_amount(self, amount: float, currency: str = "USD") -> None:
        """Set the investment amount."""
        if amount < 0:
            raise ValueError("Investment amount cannot be negative!")
        self._investment_amounts[currency] = amount

    def import_weights_from_file(self, weights_file: str) -> None:
        """Import the weights from a file."""
        with open(weights_file, "rb") as wfile:
            weights = tomllib.load(wfile)

        weights = {
            ticker["name"]: ticker["target_weight"] for ticker in weights["tickers"]
        }
        total_weight = sum(weights.values())
        if total_weight > 1:
            raise ValueError("The sum of the weights cannot be greater than 1!")
        self._weights = weights

    def export_weights_to_str(self) -> str:
        """Serialize the current weights dictionary into a TOML-formatted string."""
        lines = []
        for ticker, weight in self._weights.items():
            lines.append("[[tickers]]")
            lines.append(f'name = "{ticker}"')
            lines.append(f"target_weight = {weight}\n")
        return "\n".join(lines)

    def export_weights_to_file(self, weights_file: str) -> None:
        """Export the current weights directly to a local file path."""
        toml_content = self.export_weights_to_str()
        with open(weights_file, "w", encoding="utf-8") as wfile:
            wfile.write(toml_content)

    def set_weights(self, weights: dict[str, float]) -> None:
        """Import the weights from a dictionary."""
        if not isinstance(weights, dict):
            raise TypeError("Weights must be a dictionary!")

        total_weight = sum(weights.values())
        if total_weight > 1:
            raise ValueError("The sum of the weights cannot be greater than 1!")

        self._weights = weights

    def add_weight(self, ticker: str, weight: float) -> None:
        """Adds or Updates a weight to the weights dictionary."""
        if not isinstance(ticker, str):
            raise TypeError("Ticker must be a string!")
        if not isinstance(weight, float):
            raise TypeError("Weight must be a float!")

        if weight < 0:
            raise ValueError("Weight cannot be negative!")
        if weight > 1:
            raise ValueError("Weight cannot be greater than 1!")

        total_weight = sum(self._weights.values()) + weight
        if total_weight > 1:
            raise ValueError("The sum of the weights cannot be greater than 1!")

        self._weights[ticker] = weight

    def remove_weight(self, ticker: str) -> None:
        """Removes a weight from the weights dictionary."""
        if not isinstance(ticker, str):
            raise TypeError("Ticker must be a string!")
        if ticker in self._weights:
            del self._weights[ticker]
        else:
            raise KeyError(f"Ticker {ticker} not found in weights!")


config = Config()


def get_portfolio_evaluation(
    positions: list[dict[str, str | float]] | dict[str, dict[str, str | float]],
) -> float:
    """Get the portfolio evaluation.

    Parameters
    ----------
    positions : dict[str, dict[str, str  |  float]]
        The dictionary containing the positions in the portfolio.

    Returns
    -------
    float
        The portfolio evaluation.
    """
    if isinstance(positions, dict):
        positions = positions.values()
    elif not isinstance(positions, list):
        raise TypeError("Positions must be a list or dictionary!")

    return sum(p["market_value"] for p in positions)


def ttl_cache(ttl_seconds: float):
    """A minimal memoizing decorator whose entries expire after
    `ttl_seconds`, unlike `functools.cache` which caches forever.

    Kept dependency-free (no `cachetools`) since this is the only place
    that needs TTL behavior. Swap in `cachetools.cached(TTLCache(...))`
    instead if more caches like this end up being needed.
    """

    def decorator(func):
        _cache: dict[tuple, tuple[float, object]] = {}

        @wraps(func)
        def wrapper(*args, **kwargs):
            key = (args, tuple(sorted(kwargs.items())))
            now = time.monotonic()
            cached = _cache.get(key)
            if cached is not None and now - cached[0] < ttl_seconds:
                return cached[1]
            value = func(*args, **kwargs)
            _cache[key] = (now, value)
            return value

        wrapper.cache_clear = _cache.clear
        return wrapper

    return decorator


@ttl_cache(ttl_seconds=1 * 60)
def get_exchange_rate(from_curr: str, to_curr: str) -> float:
    """Get the current exchange between two currencies.

    Parameters
    ----------
    from_curr : str
        The currencies you are exchanging from.
    to_curr : str
        The currencies you are exchanging to.

    Returns
    -------
    float
        The exchange rate.
    """
    if from_curr == to_curr:
        return 1

    res = config.api.authorized_request(
        "getCrossRatesForDate",
        dict(base_currency=from_curr, currencies=[to_curr]),
        # version=2,
    )
    return res["rates"][to_curr]


def filter_open_positions(
    open_positions: list[dict[str, str | float]],
) -> list[dict[str, str | float]]:
    """Filter the open_position list that you get from the
    Freedom24 API.

    The new list will contain dictionaries with key:
    - name: the ticker of the position.
    - market_price: the price of each piece.
    - shares: the number of pieces.
    - market_value: the total evaluation, i.e. market_price * shares.
    - weight: The current percentage of the stock in the portfolio.

    Parameters
    ----------
    open_positions : list[dict[str, str  |  float]]
        The list of the open positions that is returned from
        Freedom24.

    Returns
    -------
    list[dict[str, str | float]]
        The filtered positions.
    """

    open_pos: list[dict[str, str | float]] = []
    for pos in open_positions:
        new_pos = {
            "name": pos["i"],
            "market_price": pos["mkt_price"],
            "shares": pos["q"],
            "market_value": pos["market_value"],
            "currency": pos["curr"],
        }
        if pos["curr"] != "USD":
            currency_convert = get_exchange_rate(pos["curr"], "USD")
            new_pos["market_price"] *= currency_convert
            new_pos["market_value"] *= currency_convert
        
        
        open_pos.append(new_pos)
    
    portfolio_eval = get_portfolio_evaluation(open_pos)
    for pos in open_pos:
        pos["weight"] = pos["market_value"] / portfolio_eval
    return open_pos


def add_position(positions: dict[str, dict[str, str | float]], ticker: str) -> None:
    """Appends an empty position in the portfolio list.

    Parameters
    ----------
    positions : list[dict[str, str  |  float]]
        The list of the positions.
    ticker : str
        The ticker of the new position.
    """
    res = config.api.authorized_request("getStockQuotesJson", dict(tickers=ticker))
    price = res["result"]["q"][0]["ltp"]
    res = config.api.authorized_request("tickerFinder", dict(text=ticker))
    currency = res["found"][0]["x_curr"]
    currency_convert = get_exchange_rate(currency, "USD")

    positions[ticker] = {
        "market_price": price * currency_convert,
        "shares": 0,
        "market_value": 0.0,
        "weight": 0.0,
        "currency": currency,
    }


def get_open_positions() -> dict[str, dict[str, str | float]]:
    """Get the open positions in the portfolio.

    Returns
    -------
    dict[str, dict[str, str | float]]
        The dictionary containing the open positions in the portfolio.
        The keys are the tickers and the values are dictionaries with the
        following keys:
        - market_price: The price of the stock.
        - shares: The number of shares in the portfolio.
        - market_value: The total value of the stock in the portfolio.
        - weight: The current weight of the stock in the portfolio.

    """
    open_positions = config.api.account_summary()["result"]["ps"]["pos"]
    positions = filter_open_positions(open_positions)
    positions_dict = {}
    for pos in positions:
        ticker = pos.pop("name")
        positions_dict[ticker] = pos
    return positions_dict


def get_all_positions() -> dict[str, dict[str, str | float]]:
    """Get all the positions in the portfolio.

    Returns
    -------
    dict[str, dict[str, str | float]]
        The dictionary containing the positions in the portfolio.
        The keys are the tickers and the values are dictionaries with the
        following keys:
        - market_price: The price of the stock.
        - shares: The number of shares in the portfolio.
        - market_value: The total value of the stock in the portfolio.
        - weight: The current weight of the stock in the portfolio.
        - target_weight: The target weight of the stock in the portfolio.
        - target_value: The target value of the stock in the portfolio.

    """
    positions = get_open_positions()

    # Read target weights
    for ticker, weight in config.weights.items():
        if ticker not in positions.keys():
            add_position(positions, ticker)

        for pos_ticker, pos in positions.items():
            if ticker in pos_ticker:
                positions[pos_ticker]["target_weight"] = weight

    # Merge items without weights
    keys_to_be_removed: list[str] = []
    positions["Misc"] = {
        "market_price": 0.0,
        "shares": 1,
        "market_value": 0.0,
        "weight": 0.0,
        "target_weight": 0.0,
        "currency": "USD",
    }

    for ticker, pos in positions.items():
        if "target_weight" not in pos:
            keys_to_be_removed.append(ticker)
            positions["Misc"]["market_value"] += pos["market_value"]
            positions["Misc"]["market_price"] += pos["market_value"]
            positions["Misc"]["weight"] += pos["weight"]
    for k in keys_to_be_removed:
        positions.pop(k)

    return positions


def recalculate_weights(
    positions: dict[str, dict[str, str | float]],
    weight_key="weight",
    market_value_key="market_value",
) -> None:
    """Recalculates the weights of the positions in the portfolio.

    Parameters
    ----------
    positions : dict[str, dict[str, str  |  float]]
        The dictionary containing the positions in the portfolio.
    weight_key : str, optional
        The key to use for the weight in the positions dictionary, by default "weight"
    market_value_key : str, optional
        The key to use for the market value in the positions dictionary, by default
        "market_value"
    """
    portfolio_eval = get_portfolio_evaluation(positions)

    for ticker in positions.keys():
        positions[ticker][weight_key] = (
            positions[ticker][market_value_key] / portfolio_eval
        )


def apply_rebalancing(
    positions: dict[str, dict[str, str | float]],
    rebalance_orders: dict[str, dict[str, str | float]],
) -> dict[str, dict[str, str | float]]:
    """Applies the rebalancing plan in the current positions.

    Parameters
    ----------
    positions : dict[str, dict[str, str  |  float]]
        The dictionary containing the current positions.
    rebalance_orders : dict[str, dict[str, str  |  float]]
        The rebalancing plan dictionary.

    Returns
    -------
    dict[str, dict[str, str | float]]
        The new positions after the rebalancing.
    """
    new_positions = deepcopy(positions)
    for ticker, actions in rebalance_orders.items():
        new_positions[ticker]["shares"] += actions["shares"]
        new_positions[ticker]["market_value"] += actions["amount"]

    recalculate_weights(new_positions)
    return new_positions


def find_rebalancing(
    positions: dict[str, dict[str, str | float]],
) -> tuple[dict[str, dict[str, str | float]], float]:
    """Finds the rebalancing plan for the current portfolio.
    The function will try to buy the cheapest stocks first and then
    the more expensive ones.
    The function will also try to buy the stocks that are furthest
    from the target value first.

    Parameters
    ----------
    positions : dict[str, dict[str, str  |  float]]
        The dictionary containing the current positions.

    Returns
    -------
    tuple[dict[str, dict[str, str | float]], float]
        The rebalancing plan and the remaining cash after the
        rebalancing.
    """
    positions = deepcopy(positions)
    portfolio_eval = get_portfolio_evaluation(positions)
    future_portfolio_eval = portfolio_eval + config.investment_amount

    for ticker, pos in positions.items():
        positions[ticker]["target_value"] = pos["target_weight"] * future_portfolio_eval

    # Sort them from furthest to target to closest from target
    positions = {
        i[0]: i[1]
        for i in sorted(
            positions.items(), key=lambda x: x[1]["market_value"] - x[1]["target_value"]
        )
    }

    remaining_cash = config.investment_amount
    rebalance_orders = {}
    for ticker, pos in positions.items():
        if remaining_cash <= 0:
            break

        price = pos["market_price"]
        diff = pos["target_value"] - pos["market_value"]
        shares_needed = diff // price  # Whole shares to close gap

        if shares_needed > 0 and price <= remaining_cash:
            max_affordable_shares = int(remaining_cash // price)
            shares_to_buy = min(shares_needed, max_affordable_shares)

            if shares_to_buy > 0:
                cost = shares_to_buy * price
                rebalance_orders[ticker] = {
                    "action": "BUY",
                    "shares": shares_to_buy,
                    "amount": cost,
                }
                remaining_cash -= cost

    # If cash remains, try to buy cheaper assets to minimize leftovers
    if remaining_cash > 0:
        for ticker, pos in positions.items():
            price = pos["market_price"]

            price = pos["market_price"]
            diff = pos["target_value"] - pos["market_value"]
            shares_needed = diff // price  # Whole shares to close gap

            if shares_needed > 0 and price <= remaining_cash:
                shares_to_buy = int(remaining_cash // price)
                if shares_to_buy > 0:
                    cost = shares_to_buy * price
                    rebalance_orders[ticker] = rebalance_orders.get(
                        ticker, {"action": "BUY", "shares": 0, "amount": 0}
                    )
                    rebalance_orders[ticker]["shares"] += shares_to_buy
                    rebalance_orders[ticker]["amount"] += cost
                    remaining_cash -= cost

    portfolio_eval = get_portfolio_evaluation(positions)
    new_portfolio_eval = portfolio_eval + config.investment_amount - remaining_cash
    for ticker, action in rebalance_orders.items():
        rebalance_orders[ticker]["new_weight"] = (
            positions[ticker]["market_value"] + action["amount"]
        ) / new_portfolio_eval
    return rebalance_orders, remaining_cash


def get_currency_conversions(
    positions: dict[str, dict[str, str | float]],
    rebalance_orders: dict[str, dict[str, str | float]],
) -> list[dict[str, str | float]]:
    """Figures out which currency conversions you actually need to make.

    Compares how much of each currency the rebalancing plan requires
    against how much you entered as your investment amount in that same
    currency. Any shortfall has to come from converting another
    currency - e.g. if the plan needs $500 more USD than you put in,
    and you entered EUR, this reports "convert some EUR to USD".

    Any currency needed that isn't one of your investment currencies at
    all (e.g. a GBP-denominated ticker when you only invested USD/EUR)
    is assumed to be funded by converting from USD, since that's the
    currency all internal calculations are done in.

    Parameters
    ----------
    positions : dict[str, dict[str, str | float]]
        The current positions, each including a "currency" key.
    rebalance_orders : dict[str, dict[str, str | float]]
        The rebalancing plan, as returned by `find_rebalancing`.

    Returns
    -------
    list[dict[str, str | float]]
        One entry per required conversion:
        `{"from_currency": "EUR", "to_currency": "USD", "from_amount": 450.0, "to_amount": 500.0}`.
    """
    needs = get_currency_needs(positions, rebalance_orders)
    available = config.investment_amounts

    conversions = []
    for currency, amounts in needs.items():
        have_native = available.get(currency, 0.0)
        shortfall_native = amounts["native_amount"] - have_native
        if shortfall_native <= 0.01:
            continue

        source_currency = "EUR" if currency == "USD" else "USD"
        source_amount = shortfall_native * get_exchange_rate(currency, source_currency)
        conversions.append(
            {
                "from_currency": source_currency,
                "to_currency": currency,
                "from_amount": source_amount,
                "to_amount": shortfall_native,
            }
        )
    return conversions


def get_currency_needs(
    positions: dict[str, dict[str, str | float]],
    rebalance_orders: dict[str, dict[str, str | float]],
) -> dict[str, dict[str, float]]:
    """Approximates how much of each native currency needs to be bought
    to execute the rebalancing plan.

    Every `rebalance_orders["amount"]` is already expressed in USD (since
    positions are normalized to USD internally), so this converts each
    order back into the ticker's actual trading currency using the
    current exchange rate - the amount you'd really need to have
    available to place that order.

    Parameters
    ----------
    positions : dict[str, dict[str, str | float]]
        The current positions, each including a "currency" key.
    rebalance_orders : dict[str, dict[str, str | float]]
        The rebalancing plan, as returned by `find_rebalancing`.

    Returns
    -------
    dict[str, dict[str, float]]
        Mapping of currency code to `{"native_amount": ..., "usd_amount": ...}`,
        e.g. `{"GBP": {"native_amount": 950.32, "usd_amount": 1200.0}}`.
    """
    needs: dict[str, dict[str, float]] = {}
    for ticker, order in rebalance_orders.items():
        currency = positions.get(ticker, {}).get("currency", "USD")
        rate = get_exchange_rate("USD", currency)
        entry = needs.setdefault(currency, {"native_amount": 0.0, "usd_amount": 0.0})
        entry["native_amount"] += order["amount"] * rate
        entry["usd_amount"] += order["amount"]
    return needs
