import os
import errno
import tomllib
from tradernet import TraderNetAPI
from functools import cache
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

    _api: TraderNetAPI
    _weights: dict[str, float]
    _investment_amount: float

    def __init__(self) -> None:
        self._api = None
        self._weights = {}
        self._investment_amount = 0.0

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

        self._investment_amount = investment_amount
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

        self._api = TraderNetAPI(api_key["public"], api_key["private"])
        self._weights = weights
        self._investment_amount = investment_amount

    @property
    def api(self) -> TraderNetAPI:
        """Get the API object."""
        if self._api is None:
            raise ValueError("API not initialized!")
        return self._api

    @property
    def weights(self) -> dict[str, float]:
        """Get the weights."""
        return self._weights

    @property
    def investment_amount(self) -> float:
        """Get the investment amount."""
        if self._investment_amount is None:
            raise ValueError("Investment amount not initialized!")
        return self._investment_amount

    def is_api_set(self) -> bool:
        """Check if the API is set."""
        return self._api is not None

    def import_api_keys_from_file(self, api_key_file: str) -> None:
        """Import the API keys from a file."""
        if not os.path.exists(api_key_file):
            raise FileNotFoundError(
                errno.ENOENT, os.strerror(errno.ENOENT), api_key_file
            )
        self._api = TraderNetAPI.from_config(api_key_file)

    def set_investment_amount(self, amount: float) -> None:
        """Set the investment amount."""
        if amount < 0:
            raise ValueError("Investment amount cannot be negative!")
        self._investment_amount = amount

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


@cache
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
        version=1,
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
    portfolio_eval = get_portfolio_evaluation(open_positions)

    open_pos: list[dict[str, str | float]] = []
    for pos in open_positions:
        new_pos = {
            "name": pos["i"],
            "market_price": pos["mkt_price"],
            "shares": pos["q"],
            "market_value": pos["market_value"],
            "weight": pos["market_value"] / portfolio_eval,
        }
        if pos["curr"] != "USD":
            currency_convert = get_exchange_rate(pos["curr"], "USD")
            new_pos["market_price"] *= currency_convert
            new_pos["market_value"] *= currency_convert
        open_pos.append(new_pos)
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
