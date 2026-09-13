"""Comparison of two share classes of the same fund across a range of scenarios.

A share class with a lower management fee usually carries a higher carried
interest. The fee is paid regardless of performance, the carry only out of
profits, so which class is cheaper depends on how the fund performs. This
module answers that question: it evaluates both classes across a range of gross
TVPI and locates the point at which the ranking flips.

Two measures are reported:

* total cost   = management fees + carried interest, as defined by the task
* net to LP    = what actually reaches the investor

They differ slightly, because the GP's own equity participates in the residual
split: a lower carry leaves more in that split, part of which goes to the GP as
an investor. That difference is invisible in the cost measure.
"""

from waterfall import FundTerms, fund_summary, proceeds_from_tvpi

# Which measure decides the ranking. "net" is the investor's perspective and is
# used for the break-even; "cost" is the definition given in the task.
CRITERIA = ("net", "cost")


def compare_at(terms_a: FundTerms, terms_b: FundTerms, gross_tvpi: float) -> dict:
    """Evaluate both share classes in the same scenario."""
    # The scenario is a property of the fund, not of the share class, so the
    # gross proceeds are identical for both.
    proceeds = proceeds_from_tvpi(terms_a, gross_tvpi)
    a = fund_summary(terms_a, proceeds)
    b = fund_summary(terms_b, proceeds)

    return {
        "gross_tvpi": gross_tvpi,
        "proceeds": proceeds,
        "fees_a": a["total_fees"], "fees_b": b["total_fees"],
        "carry_a": a["waterfall"]["carry_total"], "carry_b": b["waterfall"]["carry_total"],
        "cost_a": a["total_cost"], "cost_b": b["total_cost"],
        "net_a": a["net_to_lp"], "net_b": b["net_to_lp"],
        "net_tvpi_a": a["net_tvpi"], "net_tvpi_b": b["net_tvpi"],
        # positive means class A is ahead on this measure
        "advantage_net": a["net_to_lp"] - b["net_to_lp"],
        "advantage_cost": b["total_cost"] - a["total_cost"],
    }


def advantage(terms_a: FundTerms, terms_b: FundTerms, gross_tvpi: float,
              criterion: str = "net") -> float:
    """Advantage of class A over class B; positive means A is better for the LP."""
    if criterion not in CRITERIA:
        raise ValueError(f"criterion must be one of {CRITERIA}")
    row = compare_at(terms_a, terms_b, gross_tvpi)
    return row["advantage_net"] if criterion == "net" else row["advantage_cost"]


def sweep(terms_a: FundTerms, terms_b: FundTerms,
          lower: float = 1.0, upper: float = 3.0, step: float = 0.05) -> list[dict]:
    """Evaluate both classes across a range of gross TVPI."""
    if step <= 0 or upper <= lower:
        raise ValueError("need a positive step and upper above lower")

    rows = []
    steps = round((upper - lower) / step)
    for i in range(steps + 1):
        # built from the index rather than by repeated addition, which would
        # accumulate rounding error across many steps
        rows.append(compare_at(terms_a, terms_b, lower + i * step))
    return rows


def find_break_even(terms_a: FundTerms, terms_b: FundTerms,
                    criterion: str = "net",
                    lower: float = 0.0, upper: float = 10.0,
                    tolerance: float = 1e-6) -> float | None:
    """Gross TVPI at which the ranking of the two classes flips.

    Uses bisection: the advantage of A over B falls monotonically as the fund
    performs better, so the interval containing the sign change can be halved
    until it is smaller than the tolerance. Returns None if no flip occurs
    inside the interval.
    """
    low_value = advantage(terms_a, terms_b, lower, criterion)
    high_value = advantage(terms_a, terms_b, upper, criterion)

    if low_value == 0.0:
        return lower
    if (low_value > 0) == (high_value > 0):
        return None  # same class is ahead at both ends, so no flip in between

    while upper - lower > tolerance:
        middle = (lower + upper) / 2.0
        if (advantage(terms_a, terms_b, middle, criterion) > 0) == (low_value > 0):
            lower = middle      # the sign change lies above the middle
        else:
            upper = middle      # it lies below
    return (lower + upper) / 2.0


def plot_break_even(terms_a: FundTerms, terms_b: FundTerms,
                    label_a: str = "Class A", label_b: str = "Class B",
                    lower: float = 1.0, upper: float = 3.0, step: float = 0.05,
                    path: str = "break_even.png") -> str:
    """Chart the net result of both classes across the scenario range.

    Requires matplotlib; every other part of the package runs without it.
    """
    import matplotlib
    matplotlib.use("Agg")           # no interactive window needed
    import matplotlib.pyplot as plt

    rows = sweep(terms_a, terms_b, lower, upper, step)
    x = [row["gross_tvpi"] for row in rows]
    net_a = [row["net_a"] / 1e6 for row in rows]
    net_b = [row["net_b"] / 1e6 for row in rows]
    crossing = find_break_even(terms_a, terms_b, "net", lower, upper)

    colour_a, colour_b = "#2A9D8F", "#C1571A"
    ink, muted = "#1A1A1A", "#6B6B6B"

    figure, axes = plt.subplots(figsize=(9, 5), dpi=200)
    figure.patch.set_facecolor("white")
    axes.set_facecolor("white")

    axes.plot(x, net_a, color=colour_a, linewidth=2.0, label=label_a)
    axes.plot(x, net_b, color=colour_b, linewidth=2.0, label=label_b)

    if crossing is not None:
        axes.axvline(crossing, color=muted, linewidth=1.0, linestyle="--")
        axes.annotate(f"Umschlagpunkt {crossing:.2f}x",
                      xy=(crossing, min(net_a)), xytext=(crossing + 0.06, min(net_a)),
                      color=ink, fontsize=10, va="bottom")

    axes.set_xlabel("Brutto-TVPI des Fonds", fontsize=10, color=muted)
    axes.set_ylabel("Netto an den LP in Mio. EUR", fontsize=10, color=muted)
    axes.set_title("Welche Anteilsklasse ist für den Investor günstiger?",
                   fontsize=13, color=ink, loc="left", pad=14)

    axes.grid(True, color="#E6E6E6", linewidth=0.8)
    axes.set_axisbelow(True)
    for side in ("top", "right"):
        axes.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        axes.spines[side].set_color("#D0D0D0")
    axes.tick_params(colors=muted, labelsize=9)

    # the legend carries the identity; the terms are spelled out in the labels,
    # so the chart never depends on colour alone
    axes.legend(frameon=False, loc="upper left", fontsize=10, labelcolor=ink)

    figure.tight_layout()
    figure.savefig(path, facecolor="white", bbox_inches="tight")
    plt.close(figure)
    return path
