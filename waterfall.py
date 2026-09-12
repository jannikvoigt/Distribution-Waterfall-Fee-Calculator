"""Distribution waterfall, management fees and net performance of a private equity fund.

The model follows the standard waterfall:

    1. return of contributed capital to all capital providers, pro rata
    2. preferred return (compounded hurdle) on the contributed capital, pro rata
    3. GP catch-up: the GP receives 100% of further proceeds until its carried
       interest equals the agreed share of total profit
    4. split of the remainder: carry to the GP, the rest pro rata to LP and GP equity

Management fees run alongside the waterfall. They are charged on the LP
commitment and do not reduce the amount that is distributed.
"""

from dataclasses import dataclass


@dataclass
class FundTerms:
    """Economic terms of one share class of a fund."""

    commitment: float           # total committed capital (LP + GP equity)
    lp_share: float             # LP share of the commitment, e.g. 0.95
    hurdle_rate: float          # preferred return per year, e.g. 0.06
    carry: float                # carried interest rate, e.g. 0.20
    years: int                  # fund life in years
    investment_period: int      # years charged at the higher management fee
    mgmt_fee_investment: float  # management fee rate during the investment period
    mgmt_fee_post: float        # management fee rate afterwards

    def __post_init__(self) -> None:
        # Fail early on inputs that would silently produce meaningless numbers.
        if not 0.0 <= self.lp_share <= 1.0:
            raise ValueError("lp_share must be between 0 and 1")
        if not 0.0 <= self.carry < 1.0:
            raise ValueError("carry must be between 0 and 1 (1 would divide by zero)")
        if self.hurdle_rate < 0.0:
            raise ValueError("hurdle_rate must not be negative")
        if self.years <= 0:
            raise ValueError("years must be positive")
        if not 0 <= self.investment_period <= self.years:
            raise ValueError("investment_period must lie between 0 and years")
        if self.commitment <= 0:
            raise ValueError("commitment must be positive")

    # Everything below follows from the inputs above and is therefore derived,
    # never entered separately: a second input could contradict the first.

    @property
    def gp_share(self) -> float:
        return 1.0 - self.lp_share

    @property
    def lp_commitment(self) -> float:
        return self.commitment * self.lp_share

    @property
    def gp_commitment(self) -> float:
        return self.commitment * self.gp_share


def proceeds_from_tvpi(terms: FundTerms, gross_tvpi: float) -> float:
    """Gross proceeds implied by a gross TVPI on the total commitment."""
    return terms.commitment * gross_tvpi


def irr_from_multiple(multiple: float, years: int) -> float:
    """Annualised return of a single cash outflow returning `multiple` after `years`.

    Returns nan for a non-positive multiple, where no real IRR exists.
    """
    if multiple <= 0.0:
        return float("nan")
    return multiple ** (1.0 / years) - 1.0


def preferred_return(terms: FundTerms) -> float:
    """Compounded hurdle on the entire contributed capital, LP and GP equity alike."""
    return terms.commitment * ((1.0 + terms.hurdle_rate) ** terms.years - 1.0)


def run_waterfall(terms: FundTerms, proceeds: float) -> dict:
    """Allocate gross proceeds across the waterfall stages.

    Every stage is capped by what is actually left, so proceeds below the
    contributed capital, a hurdle of 0% and a GP equity share of 0% all yield a
    correct result without special cases.
    """
    if proceeds < 0.0:
        raise ValueError("proceeds must not be negative")

    pref = preferred_return(terms)

    # Stage 1a: capital back to everyone who contributed it
    capital_returned = min(proceeds, terms.commitment)

    # Stage 1b: preferred return, paid only from what is left after the capital
    pref_paid = min(max(proceeds - terms.commitment, 0.0), pref)
    stage_1 = capital_returned + pref_paid

    # Stage 2: the GP catches up to its share of the profit distributed so far.
    # Solving carry / (pref + carry) = c for carry gives pref * c / (1 - c).
    catchup_required = pref * terms.carry / (1.0 - terms.carry)
    catchup_paid = min(catchup_required, max(proceeds - stage_1, 0.0))

    # Stage 3: from here the agreed split applies to every further euro
    residual = max(proceeds - stage_1 - catchup_paid, 0.0)
    carry_stage_3 = residual * terms.carry
    lp_stage_3 = residual * (1.0 - terms.carry) * terms.lp_share
    gp_stage_3 = residual * (1.0 - terms.carry) * terms.gp_share

    # Stages 1a and 1b are shared pro rata between LP and GP equity
    lp_total = stage_1 * terms.lp_share + lp_stage_3
    gp_equity_total = stage_1 * terms.gp_share + gp_stage_3
    carry_total = catchup_paid + carry_stage_3

    result = {
        "proceeds": proceeds,
        "preferred_return": pref,
        "stage_1_capital": capital_returned,
        "stage_1_preferred": pref_paid,
        "stage_1_total": stage_1,
        "stage_2_catchup_required": catchup_required,
        "stage_2_catchup_paid": catchup_paid,
        "stage_3_residual": residual,
        "stage_3_carry": carry_stage_3,
        "stage_3_lp": lp_stage_3,
        "stage_3_gp_equity": gp_stage_3,
        "lp_total": lp_total,
        "gp_equity_total": gp_equity_total,
        "carry_total": carry_total,
        "lp_pct": lp_total / proceeds if proceeds else 0.0,
        "gp_equity_pct": gp_equity_total / proceeds if proceeds else 0.0,
        "carry_pct": carry_total / proceeds if proceeds else 0.0,
    }

    # Reconciliation: every euro of proceeds has to end up with someone.
    allocated = lp_total + gp_equity_total + carry_total
    if abs(allocated - proceeds) > 1e-6:
        raise AssertionError(f"waterfall does not reconcile: {allocated:.2f} vs {proceeds:.2f}")

    return result


def management_fees(terms: FundTerms) -> list[dict]:
    """Management fee per year on the LP commitment, with a running total."""
    schedule = []
    cumulative = 0.0
    for year in range(1, terms.years + 1):
        rate = terms.mgmt_fee_investment if year <= terms.investment_period else terms.mgmt_fee_post
        fee = terms.lp_commitment * rate
        cumulative += fee
        schedule.append({"year": year, "rate": rate, "fee": fee, "cumulative": cumulative})
    return schedule


def fund_summary(terms: FundTerms, proceeds: float) -> dict:
    """Waterfall, fees and the resulting gross and net performance of the LP."""
    waterfall = run_waterfall(terms, proceeds)
    fees = management_fees(terms)
    total_fees = sum(row["fee"] for row in fees)

    # Fees run alongside the waterfall, so they are deducted from the LP result.
    net_to_lp = waterfall["lp_total"] - total_fees

    gross_tvpi = proceeds / terms.commitment
    net_tvpi = net_to_lp / terms.lp_commitment

    return {
        "terms": terms,
        "waterfall": waterfall,
        "fee_schedule": fees,
        "total_fees": total_fees,
        "total_cost": total_fees + waterfall["carry_total"],
        "net_to_lp": net_to_lp,
        "gross_tvpi": gross_tvpi,
        "gross_irr": irr_from_multiple(gross_tvpi, terms.years),
        "net_tvpi": net_tvpi,
        "net_irr": irr_from_multiple(net_tvpi, terms.years),
    }
