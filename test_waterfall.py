"""Tests for the waterfall and fee calculator.

Two kinds of tests are used:

* case tests, which reproduce the two share classes of the case study and
  check every position against its target value;
* property tests, which check rules that must hold for *any* scenario, such as
  the reconciliation of the waterfall.
"""

import pytest

from waterfall import (
    FundTerms,
    fund_summary,
    management_fees,
    proceeds_from_tvpi,
    run_waterfall,
)

# --- Terms of the two share classes of the case study ------------------------

CLASS_A = FundTerms(
    commitment=10_000_000, lp_share=0.95, hurdle_rate=0.06, carry=0.20,
    years=10, investment_period=5,
    mgmt_fee_investment=0.0125, mgmt_fee_post=0.0075,
)
CLASS_B = FundTerms(
    commitment=10_000_000, lp_share=0.95, hurdle_rate=0.06, carry=0.10,
    years=10, investment_period=5,
    mgmt_fee_investment=0.0250, mgmt_fee_post=0.0150,
)

GROSS_TVPI = 2.5          # scenario of both test cases
CENT = 0.01               # tolerance: the target values are rounded to cents

TARGETS = {
    "A": {
        "terms": CLASS_A,
        "waterfall": {
            "preferred_return": 7_908_476.97,
            "stage_1_total": 17_908_476.97,
            "stage_2_catchup_paid": 1_977_119.24,
            "stage_3_lp": 3_886_946.88,
            "stage_3_gp_equity": 204_576.15,
            "stage_3_carry": 1_022_880.76,
            "lp_total": 20_900_000.00,
            "gp_equity_total": 1_100_000.00,
            "carry_total": 3_000_000.00,
        },
        "summary": {
            "total_fees": 950_000.00,
            "total_cost": 3_950_000.00,
            "net_to_lp": 19_950_000.00,
            "net_tvpi": 2.10,
        },
        "annual_fees": (118_750.00, 71_250.00),
    },
    "B": {
        "terms": CLASS_B,
        "waterfall": {
            "preferred_return": 7_908_476.97,
            "stage_1_total": 17_908_476.97,
            "stage_2_catchup_paid": 878_719.66,
            "stage_3_lp": 5_311_946.88,
            "stage_3_gp_equity": 279_576.15,
            "stage_3_carry": 621_280.34,
            "lp_total": 22_325_000.00,
            "gp_equity_total": 1_175_000.00,
            "carry_total": 1_500_000.00,
        },
        "summary": {
            "total_fees": 1_900_000.00,
            "total_cost": 3_400_000.00,
            "net_to_lp": 20_425_000.00,
            "net_tvpi": 2.15,
        },
        "annual_fees": (237_500.00, 142_500.00),
    },
}


# --- Case tests: the two test cases of the assignment -------------------------

@pytest.mark.parametrize("share_class", ["A", "B"])
def test_waterfall_matches_target_values(share_class):
    """Every waterfall position of the case study is reproduced to the cent."""
    case = TARGETS[share_class]
    result = run_waterfall(case["terms"], proceeds_from_tvpi(case["terms"], GROSS_TVPI))

    for position, target in case["waterfall"].items():
        assert result[position] == pytest.approx(target, abs=CENT), position


@pytest.mark.parametrize("share_class", ["A", "B"])
def test_fees_and_net_performance_match_target_values(share_class):
    """Management fees and the resulting net figures of the LP."""
    case = TARGETS[share_class]
    summary = fund_summary(case["terms"], proceeds_from_tvpi(case["terms"], GROSS_TVPI))

    for position, target in case["summary"].items():
        assert summary[position] == pytest.approx(target, abs=CENT), position


@pytest.mark.parametrize("share_class", ["A", "B"])
def test_fee_schedule_switches_after_the_investment_period(share_class):
    """The higher rate applies through year 5 and the lower one from year 6."""
    case = TARGETS[share_class]
    during, after = case["annual_fees"]
    schedule = management_fees(case["terms"])

    assert len(schedule) == case["terms"].years
    assert schedule[4]["fee"] == pytest.approx(during, abs=CENT)   # year 5
    assert schedule[5]["fee"] == pytest.approx(after, abs=CENT)    # year 6
    assert schedule[-1]["cumulative"] == pytest.approx(
        5 * during + 5 * after, abs=CENT
    )


# --- Edge cases required by the assignment -----------------------------------

def test_proceeds_below_contributed_capital():
    """Below the capital there is no profit, hence no preferred return and no carry."""
    result = run_waterfall(CLASS_A, 8_000_000)

    assert result["stage_1_capital"] == pytest.approx(8_000_000, abs=CENT)
    assert result["stage_1_preferred"] == 0.0
    assert result["carry_total"] == 0.0
    # the loss is shared pro rata between LP and GP equity
    assert result["lp_total"] == pytest.approx(8_000_000 * CLASS_A.lp_share, abs=CENT)
    assert result["gp_equity_total"] == pytest.approx(8_000_000 * CLASS_A.gp_share, abs=CENT)


def test_zero_hurdle_rate():
    """Without a hurdle there is no preferred return and no catch-up, but the
    GP still ends up with its agreed share of the profit."""
    terms = FundTerms(
        commitment=10_000_000, lp_share=0.95, hurdle_rate=0.0, carry=0.20,
        years=10, investment_period=5,
        mgmt_fee_investment=0.0125, mgmt_fee_post=0.0075,
    )
    result = run_waterfall(terms, 25_000_000)
    profit = 25_000_000 - terms.commitment

    assert result["preferred_return"] == 0.0
    assert result["stage_2_catchup_paid"] == 0.0
    assert result["carry_total"] == pytest.approx(terms.carry * profit, abs=CENT)


def test_no_gp_equity():
    """With an LP share of 100% the GP only earns carry, never equity proceeds."""
    terms = FundTerms(
        commitment=10_000_000, lp_share=1.0, hurdle_rate=0.06, carry=0.20,
        years=10, investment_period=5,
        mgmt_fee_investment=0.0125, mgmt_fee_post=0.0075,
    )
    result = run_waterfall(terms, 25_000_000)

    assert result["gp_equity_total"] == 0.0
    assert result["carry_total"] == pytest.approx(3_000_000, abs=CENT)
    assert result["lp_total"] == pytest.approx(22_000_000, abs=CENT)


def test_total_loss():
    """Zero proceeds must not break the percentage figures."""
    result = run_waterfall(CLASS_A, 0.0)

    assert result["lp_total"] == 0.0
    assert result["carry_total"] == 0.0
    assert result["lp_pct"] == 0.0


# --- Property tests: rules that hold for every scenario ----------------------

@pytest.mark.parametrize("gross_tvpi", [0.0, 0.5, 1.0, 1.25, 1.5, 1.9, 2.0, 2.5, 5.0])
def test_waterfall_reconciles_for_every_scenario(gross_tvpi):
    """Every euro of proceeds is allocated to LP, GP equity or carry."""
    proceeds = proceeds_from_tvpi(CLASS_A, gross_tvpi)
    result = run_waterfall(CLASS_A, proceeds)
    allocated = result["lp_total"] + result["gp_equity_total"] + result["carry_total"]

    assert allocated == pytest.approx(proceeds, abs=1e-6)


@pytest.mark.parametrize("gross_tvpi", [2.0, 2.5, 3.0, 5.0])
def test_carry_equals_agreed_share_of_profit_once_catchup_is_complete(gross_tvpi):
    """Above the catch-up the waterfall collapses into a plain profit split."""
    proceeds = proceeds_from_tvpi(CLASS_A, gross_tvpi)
    result = run_waterfall(CLASS_A, proceeds)
    profit = proceeds - CLASS_A.commitment

    # the catch-up has to be fully paid for this rule to apply
    assert result["stage_2_catchup_paid"] == pytest.approx(
        result["stage_2_catchup_required"], abs=CENT
    )
    assert result["carry_total"] == pytest.approx(CLASS_A.carry * profit, abs=CENT)


@pytest.mark.parametrize("gross_tvpi", [0.0, 1.0, 1.5, 2.5])
def test_no_party_ever_receives_a_negative_amount(gross_tvpi):
    result = run_waterfall(CLASS_A, proceeds_from_tvpi(CLASS_A, gross_tvpi))

    assert min(result["lp_total"], result["gp_equity_total"], result["carry_total"]) >= 0.0


# --- Input validation --------------------------------------------------------

@pytest.mark.parametrize(
    "field, value",
    [("lp_share", 1.5), ("carry", 1.0), ("hurdle_rate", -0.01),
     ("years", 0), ("investment_period", 11), ("commitment", 0)],
)
def test_invalid_terms_are_rejected(field, value):
    """Invalid input fails immediately instead of producing meaningless numbers."""
    values = dict(
        commitment=10_000_000, lp_share=0.95, hurdle_rate=0.06, carry=0.20,
        years=10, investment_period=5,
        mgmt_fee_investment=0.0125, mgmt_fee_post=0.0075,
    )
    values[field] = value

    with pytest.raises(ValueError):
        FundTerms(**values)


def test_negative_proceeds_are_rejected():
    with pytest.raises(ValueError):
        run_waterfall(CLASS_A, -1.0)
