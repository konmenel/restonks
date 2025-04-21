#!/bin/env python3
from argparse import ArgumentParser
import pandas as pd

from . import lib


def create_cli() -> ArgumentParser:
    parser = ArgumentParser(
        "restonks",
        description=(
            "Given the target weights of any ETF or stocks and an investment amount "
            "finds the optimal investements values."
        ),
    )
    parser.add_argument(
        "investment_amount", type=float, help="The investment amount in USD."
    )
    parser.add_argument(
        "-w",
        "--weights",
        type=str,
        help="The TOML file with the target weights. Default: 'weights.toml'",
        default="weights.toml",
    )
    parser.add_argument(
        "-k",
        "--api-key",
        type=str,
        help=(
            "The INI file with the private and public keys for the Freedom24 API."
            " Default: 'tradernet.ini"
        ),
        default="tradernet.ini",
    )

    return parser


def display_results(
    positions: dict[str, dict[str, str | float]],
    rebalance_orders: dict[str, dict[str, str | float]],
    remaining_cash: float,
) -> None:
    # Current porfolio
    portfolio_eval = sum(p["market_value"] for p in positions.values())
    portfolio_df = pd.DataFrame.from_dict(positions, orient="index")
    print("==== Portfolio ====")
    print(
        portfolio_df.to_string(
            formatters={"weight": "{:.2%}".format, "target_weight": "{:.2%}".format}
        )
    )

    print(f"\nCurrent Evaluation: ${portfolio_eval:.2f}")
    print(f"Investment amount: ${lib.config.investment_amount:.2f}")

    print("\n==== Rebalancing Plan ====")
    rebalance_df = pd.DataFrame.from_dict(rebalance_orders, orient="index")
    if not rebalance_df.empty:
        print(
            rebalance_df[["action", "shares", "amount", "new_weight"]].to_string(
                formatters={"new_weight": "{:.2%}".format}
            )
        )

    # Post-rebalancing portfolio summary
    print("\n==== Updated Portfolio ====")
    new_positons = lib.apply_rebalancing(positions, rebalance_orders)
    new_portfolio_df = pd.DataFrame.from_dict(new_positons, orient="index")
    print(
        new_portfolio_df.to_string(
            formatters={"weight": "{:.2%}".format, "target_weight": "{:.2%}".format}
        )
    )

    future_portfolio_eval = (
        portfolio_eval + lib.config.investment_amount - remaining_cash
    )
    print(f"\nNew Evaluation: ${future_portfolio_eval:.2f}")
    print(f"Remaining cash: ${remaining_cash:.2f}")


def main() -> int:
    parser = create_cli()
    args = parser.parse_args()

    lib.config.initialise_from_files(
        api_key_file=args.api_key,
        weights_file=args.weights,
        investment_amount=args.investment_amount,
    )

    positions = lib.get_all_positions()
    rebalance_orders, remaining_cash = lib.find_rebalancing(positions)

    display_results(positions, rebalance_orders, remaining_cash)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
