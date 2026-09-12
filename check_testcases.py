"""Quick check of the two case study test cases against their target values."""

from waterfall import FundTerms, proceeds_from_tvpi, fund_summary

class_a = FundTerms(
    commitment=10_000_000, lp_share=0.95, hurdle_rate=0.06, carry=0.20,
    years=10, investment_period=5,
    mgmt_fee_investment=0.0125, mgmt_fee_post=0.0075,
)
class_b = FundTerms(
    commitment=10_000_000, lp_share=0.95, hurdle_rate=0.06, carry=0.10,
    years=10, investment_period=5,
    mgmt_fee_investment=0.0250, mgmt_fee_post=0.0150,
)

expected_a = {
    "preferred_return": 7_908_476.97, "stage_1_total": 17_908_476.97,
    "stage_2_catchup_paid": 1_977_119.24, "stage_3_lp": 3_886_946.88,
    "stage_3_gp_equity": 204_576.15, "stage_3_carry": 1_022_880.76,
    "lp_total": 20_900_000.00, "gp_equity_total": 1_100_000.00,
    "carry_total": 3_000_000.00, "total_fees": 950_000.00,
    "total_cost": 3_950_000.00, "net_to_lp": 19_950_000.00,
}
expected_b = {
    "preferred_return": 7_908_476.97, "stage_1_total": 17_908_476.97,
    "stage_2_catchup_paid": 878_719.66, "stage_3_lp": 5_311_946.88,
    "stage_3_gp_equity": 279_576.15, "stage_3_carry": 621_280.34,
    "lp_total": 22_325_000.00, "gp_equity_total": 1_175_000.00,
    "carry_total": 1_500_000.00, "total_fees": 1_900_000.00,
    "total_cost": 3_400_000.00, "net_to_lp": 20_425_000.00,
}


def check(name, terms, expected, gross_tvpi=2.5, tolerance=0.01):
    summary = fund_summary(terms, proceeds_from_tvpi(terms, gross_tvpi))
    values = {**summary["waterfall"], **summary}
    print(f"\n{name}")
    print(f"{'position':26}{'ist':>16}{'soll':>16}{'diff':>10}  ok")
    all_ok = True
    for key, target in expected.items():
        actual = values[key]
        diff = actual - target
        ok = abs(diff) <= tolerance
        all_ok &= ok
        print(f"{key:26}{actual:>16,.2f}{target:>16,.2f}{diff:>10.4f}  {'OK' if ok else 'FEHLER'}")
    print(f"{'net_tvpi':26}{summary['net_tvpi']:>16.4f}")
    print(f"{'net_irr':26}{summary['net_irr']:>16.4%}")
    print("ERGEBNIS:", "alle Werte getroffen" if all_ok else "ABWEICHUNG")
    return all_ok


check("TESTFALL 1 - Klasse A", class_a, expected_a)
check("TESTFALL 2 - Klasse B", class_b, expected_b)
