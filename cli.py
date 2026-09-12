"""Command line interface for the private equity waterfall and fee calculator.

Examples
--------
    python cli.py                          # test case 1 (share class A)
    python cli.py --carry 0.10 --fee-investment 0.025 --fee-post 0.015
    python cli.py --tvpi 1.5               # a weaker scenario
    python cli.py --compare                # class A against class B
    python cli.py --carry 0.15 --carry-b 0.25 --compare   # any other pair
"""

import argparse

from waterfall import FundTerms, fund_summary, proceeds_from_tvpi

# The defaults below describe share class A of the case study; the --*-b
# options describe the class it is compared against, defaulting to class B.
# Any other pair of terms can be passed instead.

WIDTH = 74


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Distribution waterfall, management fees and net performance "
                    "of a private equity fund.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--commitment", type=float, default=10_000_000,
                        help="total committed capital (LP + GP equity)")
    parser.add_argument("--lp-share", type=float, default=0.95,
                        help="LP share of the commitment, as a fraction")
    parser.add_argument("--hurdle", type=float, default=0.06,
                        help="preferred return per year, as a fraction")
    parser.add_argument("--carry", type=float, default=0.20,
                        help="carried interest rate, as a fraction")
    parser.add_argument("--years", type=int, default=10, help="fund life in years")
    parser.add_argument("--investment-period", type=int, default=5,
                        help="years charged at the higher management fee")
    parser.add_argument("--fee-investment", type=float, default=0.0125,
                        help="management fee during the investment period")
    parser.add_argument("--fee-post", type=float, default=0.0075,
                        help="management fee after the investment period")

    # The scenario can be given either as a multiple or as an absolute amount.
    scenario = parser.add_mutually_exclusive_group()
    scenario.add_argument("--tvpi", type=float, default=2.5,
                          help="gross TVPI on the total commitment")
    scenario.add_argument("--proceeds", type=float,
                          help="gross proceeds in currency units, overrides --tvpi")

    # Second set of fee terms, used only by --compare. Everything else
    # (commitment, hurdle, life) is by definition identical for two share
    # classes of the same fund.
    parser.add_argument("--carry-b", type=float, default=0.10,
                        help="carried interest of the comparison class")
    parser.add_argument("--fee-investment-b", type=float, default=0.0250,
                        help="management fee of the comparison class during the investment period")
    parser.add_argument("--fee-post-b", type=float, default=0.0150,
                        help="management fee of the comparison class afterwards")

    parser.add_argument("--compare", action="store_true",
                        help="compare the terms above against the comparison class")
    return parser.parse_args()


def terms_from_args(args: argparse.Namespace, overrides: dict | None = None) -> FundTerms:
    """Build FundTerms from the parsed arguments, optionally overriding the fee terms."""
    values = dict(
        commitment=args.commitment,
        lp_share=args.lp_share,
        hurdle_rate=args.hurdle,
        carry=args.carry,
        years=args.years,
        investment_period=args.investment_period,
        mgmt_fee_investment=args.fee_investment,
        mgmt_fee_post=args.fee_post,
    )
    values.update(overrides or {})
    return FundTerms(**values)


def money(value: float) -> str:
    return f"{value:>16,.2f}"


def line(label: str, value: str) -> None:
    print(f"  {label:<44}{value}")


def print_summary(summary: dict) -> None:
    terms, w = summary["terms"], summary["waterfall"]

    print("=" * WIDTH)
    print("  FUND TERMS")
    print("-" * WIDTH)
    line("Committed capital", money(terms.commitment))
    line("  thereof LP", money(terms.lp_commitment))
    line("  thereof GP equity", money(terms.gp_commitment))
    line("Hurdle rate / carried interest",
         f"{terms.hurdle_rate:>10.2%} / {terms.carry:.2%}")
    line("Management fee, investment period / after",
         f"{terms.mgmt_fee_investment:>8.2%} / {terms.mgmt_fee_post:.2%}")
    line("Fund life / investment period",
         f"{terms.years:>10} / {terms.investment_period} years")

    print("=" * WIDTH)
    print("  DISTRIBUTION WATERFALL")
    print("-" * WIDTH)
    line("Gross proceeds", money(w["proceeds"]))
    line("Preferred return (hurdle, compounded)", money(w["preferred_return"]))
    line("Stage 1: capital + preferred return", money(w["stage_1_total"]))
    line("Stage 2: GP catch-up", money(w["stage_2_catchup_paid"]))
    line("Stage 3: to LP", money(w["stage_3_lp"]))
    line("Stage 3: to GP (equity)", money(w["stage_3_gp_equity"]))
    line("Stage 3: carried interest", money(w["stage_3_carry"]))
    print("-" * WIDTH)
    line("LP total", f"{money(w['lp_total'])}   ({w['lp_pct']:.1%})")
    line("GP (equity) total", f"{money(w['gp_equity_total'])}   ({w['gp_equity_pct']:.1%})")
    line("Carried interest total", f"{money(w['carry_total'])}   ({w['carry_pct']:.1%})")
    allocated = w["lp_total"] + w["gp_equity_total"] + w["carry_total"]
    line("Reconciliation (allocated - proceeds)",
         f"{allocated - w['proceeds']:>16.6f}")

    print("=" * WIDTH)
    print("  MANAGEMENT FEES")
    print("-" * WIDTH)
    print(f"  {'Year':<8}{'Rate':>10}{'Fee':>18}{'Cumulative':>20}")
    for row in summary["fee_schedule"]:
        print(f"  {row['year']:<8}{row['rate']:>10.2%}{row['fee']:>18,.2f}{row['cumulative']:>20,.2f}")

    print("=" * WIDTH)
    print("  LP PERSPECTIVE")
    print("-" * WIDTH)
    line("Management fees total", money(summary["total_fees"]))
    line("Carried interest", money(w["carry_total"]))
    line("Total cost (fees + carry)", money(summary["total_cost"]))
    line("Net to LP", money(summary["net_to_lp"]))
    line("Gross TVPI / IRR",
         f"{summary['gross_tvpi']:>9.2f}x / {summary['gross_irr']:.2%}")
    line("Net TVPI / IRR",
         f"{summary['net_tvpi']:>9.2f}x / {summary['net_irr']:.2%}")
    print("=" * WIDTH)


def print_comparison(args: argparse.Namespace) -> None:
    """Show both share classes next to each other for the same scenario."""
    a_terms = terms_from_args(args)
    b_terms = terms_from_args(args, {
        "carry": args.carry_b,
        "mgmt_fee_investment": args.fee_investment_b,
        "mgmt_fee_post": args.fee_post_b,
    })

    # The scenario is identical for both classes, so the gross proceeds are too.
    proceeds = args.proceeds if args.proceeds is not None else proceeds_from_tvpi(a_terms, args.tvpi)
    a = fund_summary(a_terms, proceeds)
    b = fund_summary(b_terms, proceeds)

    print("=" * WIDTH)
    print(f"  SHARE CLASS COMPARISON AT A GROSS TVPI OF {a['gross_tvpi']:.2f}x")
    print("-" * WIDTH)
    label_a = f"{a_terms.carry:.0%} carry"
    label_b = f"{b_terms.carry:.0%} carry"
    print(f"  {'':<30}{label_a:>20}{label_b:>20}")
    print(f"  {'Management fee, in / after':<30}"
          f"{f'{a_terms.mgmt_fee_investment:.2%} / {a_terms.mgmt_fee_post:.2%}':>20}"
          f"{f'{b_terms.mgmt_fee_investment:.2%} / {b_terms.mgmt_fee_post:.2%}':>20}")
    print("-" * WIDTH)
    print(f"  {'Carried interest':<30}{a['waterfall']['carry_total']:>20,.2f}{b['waterfall']['carry_total']:>20,.2f}")
    print(f"  {'Management fees':<30}{a['total_fees']:>20,.2f}{b['total_fees']:>20,.2f}")
    print(f"  {'Total cost':<30}{a['total_cost']:>20,.2f}{b['total_cost']:>20,.2f}")
    print(f"  {'Net to LP':<30}{a['net_to_lp']:>20,.2f}{b['net_to_lp']:>20,.2f}")
    print(f"  {'Net TVPI':<30}{a['net_tvpi']:>19.2f}x{b['net_tvpi']:>19.2f}x")
    print(f"  {'Net IRR':<30}{a['net_irr']:>20.2%}{b['net_irr']:>20.2%}")
    print("-" * WIDTH)

    # Lower total cost means more money stays with the investor.
    cheaper = label_a if a["total_cost"] < b["total_cost"] else label_b
    difference = abs(a["total_cost"] - b["total_cost"])
    print(f"  Cheaper for the investor in this scenario: {cheaper} (by {difference:,.2f})")
    print("=" * WIDTH)


def main() -> None:
    args = parse_args()
    if args.compare:
        print_comparison(args)
        return

    terms = terms_from_args(args)
    proceeds = args.proceeds if args.proceeds is not None else proceeds_from_tvpi(terms, args.tvpi)
    print_summary(fund_summary(terms, proceeds))


if __name__ == "__main__":
    main()
