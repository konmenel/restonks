import os
import errno
import tomllib
from tradernet import TraderNetAPI
from functools import cache


# TODO: Add sell action as option.
# TODO: ADD dockstrings
# TODO: Setup MYPY


class Config:
    api: TraderNetAPI
    weights_file: str
    investment_amount: float

    def __init__(self) -> None:
        self.api = None
        self.weights_file = None
        self.investment_amount = -1

    def initialise(
        self, api_key_file: str, weights_file: str, investment_amount: float
    ) -> None:
        if not os.path.exists(weights_file):
            raise FileNotFoundError(
                errno.ENOENT, os.strerror(errno.ENOENT), weights_file
            )

        if investment_amount < 0:
            ValueError("Investment amount cannot be negative!")

        self.api = TraderNetAPI.from_config(api_key_file)
        self.weights_file = weights_file
        self.investment_amount = investment_amount


config = Config()


@cache
def get_exchange_rate(from_curr: str, to_curr: str) -> float:
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
    portfolio_eval = sum(p["market_value"] for p in open_positions)

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


def append_position(positions: list[dict[str, str | float]], ticker: str) -> None:
    res = config.api.authorized_request("getStockQuotesJson", dict(tickers=ticker))
    price = res["result"]["q"][0]["ltp"]
    res = config.api.authorized_request("tickerFinder", dict(text=ticker))
    currency = res["found"][0]["x_curr"]
    currency_convert = get_exchange_rate(currency, "USD")

    positions.append(
        {
            "name": ticker,
            "market_price": price * currency_convert,
            "shares": 0,
            "market_value": 0.0,
            "weight": 0.0,
        }
    )


def get_all_positions() -> dict[str, dict[str, str | float]]:
    open_positions = config.api.account_summary()["result"]["ps"]["pos"]
    positions = filter_open_positions(open_positions)
    pos_names = [p["name"] for p in positions]
    portfolio_eval = sum(p["market_value"] for p in positions)
    future_portfolio_eval = portfolio_eval + config.investment_amount

    # Read target weights
    with open(config.weights_file, "rb") as wfile:
        weights = tomllib.load(wfile)
    weights = weights["tickers"]
    total_weight = sum(w["target_weight"] for w in weights)
    assert total_weight <= 1, "The sum of the weights cannot be greater than 1!"

    for weight in weights:
        if weight["name"] not in pos_names:
            append_position(positions, weight["name"])

        for i, pos in enumerate(positions):
            if weight["name"] in pos["name"]:
                positions[i]["target_weight"] = weight["target_weight"]
                positions[i]["target_value"] = (
                    weight["target_weight"] * future_portfolio_eval
                )

    # Merge items without weights
    index_to_remove: list[int] = []
    positions.append(
        {
            "name": "Misc",
            "market_price": 0.0,
            "shares": 1,
            "market_value": 0.0,
            "weight": 0.0,
            "target_weight": 0.0,
            "target_value": 0.0,
        }
    )
    for i, pos in enumerate(positions):
        if "target_weight" not in pos:
            index_to_remove.append(i - len(index_to_remove))  # DO NOT QUESTION!
            positions[-1]["market_value"] += pos["market_value"]
            positions[-1]["target_value"] += pos["market_value"]
            positions[-1]["market_price"] += pos["market_value"]
            positions[-1]["weight"] += pos["weight"]
    for i in index_to_remove:
        positions.pop(i)

    # Sort them from furthest to target to closest from target
    positions = sorted(positions, key=lambda x: x["market_value"] - x["target_value"])
    positions_dict = {}
    for pos in positions:
        ticker = pos.pop("name")
        positions_dict[ticker] = pos
    return positions_dict


def find_rebalancing(
    positions: dict[str, dict[str, str | float]],
) -> tuple[dict[str, dict[str, str | float]], float]:
    portfolio_eval = sum(p["market_value"] for p in positions.values())
    future_portfolio_eval = portfolio_eval + config.investment_amount

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
                    "new_weight": (pos["market_value"] + cost) / future_portfolio_eval,
                }
                remaining_cash -= cost

    # If cash remains, try to buy cheaper assets to minimize leftovers
    if remaining_cash > 0:
        for ticker, pos in positions.items():
            price = pos["market_price"]
            if price <= remaining_cash:
                shares_to_buy = int(remaining_cash // price)
                if shares_to_buy > 0:
                    cost = shares_to_buy * price
                    rebalance_orders[ticker] = rebalance_orders.get(
                        ticker, {"action": "BUY", "shares": 0, "amount": 0}
                    )
                    rebalance_orders[ticker]["shares"] += shares_to_buy
                    rebalance_orders[ticker]["amount"] += cost
                    rebalance_orders[ticker]["new_weight"] = (
                        pos["market_value"] + rebalance_orders[ticker]["amount"]
                    ) / future_portfolio_eval
                    remaining_cash -= cost
    return rebalance_orders, remaining_cash
