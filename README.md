# Distribution Waterfall & Fee Calculator

A tool that calculates the distribution waterfall of a private equity fund including
carried interest, models the management fees over the life of the fund, and compares
two share classes of the same fund.

**The question it answers.** The same fund is often offered in several share classes:
one with a low management fee and a high carried interest, one with a high fee and a
low carry. The fee is paid regardless of performance, the carry only out of profits —
so which class is cheaper for an investor depends on how the fund performs. This tool
computes both classes across a range of scenarios and locates the point at which the
ranking flips.

## Installation

Python 3.10 or newer.

```bash
git clone <repository-url>
cd <repository>
pip install -r requirements.txt
```

The calculator itself uses only the standard library. `matplotlib` is required for the
chart, `pytest` for the test suite — nothing else.

## Usage

```bash
python cli.py                      # single scenario, defaults to test case 1
python cli.py --compare            # two share classes side by side
python cli.py --sweep              # across a range of scenarios, with the break-even
python cli.py --help               # all parameters
```

Every fund term is a parameter, so the tool is not limited to the test cases:

```bash
python cli.py --commitment 50000000 --lp-share 0.98 --hurdle 0.08 \
              --years 12 --investment-period 6 --tvpi 1.8
```

For the comparison, the second class is described by its own fee and carry options,
which default to class B of the test cases:

```bash
python cli.py --carry 0.15 --fee-investment 0.02 --fee-post 0.01 \
              --carry-b 0.25 --fee-investment-b 0.005 --fee-post-b 0.005 --compare
```

### Example

`python cli.py --compare` on the terms of the two test cases, at a gross TVPI of 2.5x:

```
                                           20% carry           10% carry
  Management fee, in / after           1.25% / 0.75%       2.50% / 1.50%
--------------------------------------------------------------------------
  Carried interest                      3,000,000.00        1,500,000.00
  Management fees                         950,000.00        1,900,000.00
  Total cost                            3,950,000.00        3,400,000.00
  Net to LP                            19,950,000.00       20,425,000.00
  Net TVPI                                     2.10x               2.15x
  Net IRR                                      7.70%               7.96%
--------------------------------------------------------------------------
  Cheaper for the investor in this scenario: 10% carry (by 550,000.00)
```

## How the waterfall works

Proceeds are distributed in four stages. Each stage is filled completely before
anything flows to the next one.

**Stage 1a — return of capital.** The contributed capital is paid back to all capital
providers pro rata, LP and GP equity alike.

**Stage 1b — preferred return.** A compounded minimum return on the *entire*
contributed capital, not only on the LP share:

```
preferred return = commitment x ((1 + hurdle) ^ years - 1)
```

**Stage 2 — GP catch-up.** The GP now receives 100% of further proceeds until its
carried interest equals the agreed share of the profit distributed so far. Solving
`x / (preferred return + x) = carry` gives:

```
catch-up = preferred return x carry / (1 - carry)
```

**Stage 3 — split.** Of the remainder, the carry percentage goes to the GP; the rest is
split between LP and GP equity in proportion to their commitments.

**Management fees run alongside the waterfall.** They do not reduce the amount
distributed; they are charged on the LP commitment and deducted from the LP's result.
The rate changes after the investment period.

**Reconciliation.** LP + GP equity + carried interest must equal the proceeds exactly.
This is checked explicitly in `run_waterfall`, which raises an error rather than
returning a figure that does not add up.

Each stage is capped by what is actually left, so proceeds below the contributed
capital, a hurdle of 0% and a GP equity share of 0% all produce correct results
without any special-case branching.

## Share class comparison

Two measures are reported, and they do not flip at the same point:

* **total cost** = management fees + carried interest, as defined in the assignment
* **net to LP** = what actually reaches the investor

The difference is the GP's own equity: a lower carry leaves more in the stage 3 split,
and the GP participates in that split as an investor. For the two test case classes the
ranking flips at a gross TVPI of **2.00x** measured by net proceeds and at **1.98x**
measured by total cost.

The break-even is found numerically by bisection rather than from a closed formula,
because in that range the catch-up is not yet fully paid — the carried interest does
not equal the agreed share of the profit there, so a simplified formula would
understate the point.

## Tests

```bash
pytest -v
```

34 tests in three groups:

* **case tests** — both share classes of the assignment, every waterfall position, the
  fees and the net figures, to the cent;
* **edge cases** — proceeds below contributed capital, a hurdle of 0%, GP equity of 0%,
  and a total loss;
* **property tests** — the reconciliation across nine scenarios from 0.0x to 5.0x, the
  rule that carried interest equals the agreed share of profit once the catch-up is
  complete, and that no party ever receives a negative amount;
* **input validation** — six invalid inputs that must be rejected.

`check_testcases.py` covers the same two test cases as a readable target-versus-actual
table. It exists alongside the test suite on purpose: `pytest` gives an automated
verdict, the script shows the figures side by side.

## Project structure

```
waterfall.py           fund terms, waterfall, management fees, net performance
comparison.py          comparison of two share classes, scenario sweep, break-even, chart
cli.py                 command line interface; input and output only
test_waterfall.py      test suite
check_testcases.py     target-versus-actual table for the two test cases
requirements.txt
```

## Design decisions

* **Only independent quantities are inputs.** Derived values such as the LP commitment
  and the preferred return are computed, so the model cannot be put into a
  contradictory state.
* **Edge cases are handled by capping each stage**, not by branching on special cases:
  proceeds below the contributed capital, a hurdle of 0% and a GP equity share of 0%
  need no separate code path.
* **Calculation and presentation are separate.** `waterfall.py` and `comparison.py`
  compute; `cli.py` only reads parameters and formats output.

## Approach

The domain logic was worked out first and without code: the waterfall stages were
derived from the two given test cases and rebuilt in a spreadsheet until every target
value matched to the cent. That spreadsheet has served as an independent reference for
every figure the code produces ever since, and the translation into Python came only
afterwards.

The implementation, the test suite and the command line interface were written with AI
assistance and then reviewed against that reference; the structural choices listed above
were taken deliberately. Verification was deliberately not done with AI, but against the
independently built spreadsheet and the two given test cases.

## Known limitations

* A single contribution and a single distribution date are assumed. The IRR therefore
  follows from the TVPI over the fund life rather than from an actual cash flow series.
* The European, whole-fund waterfall is implemented. A deal-by-deal variant with
  clawback is not included.
* Management fees are charged on the LP commitment throughout. Switching the basis to
  invested capital after the investment period is common in practice but was not
  required here.
* No real IRR exists for a net multiple of zero or below; the tool returns no value in
  that case, and this case is not covered by a test.
* Taxes, transaction costs and subscription lines are not modelled.
* Fund terms cannot be stored. Every run is independent: each invocation starts from
  the defaults and applies only the options given on that command line, so a fund that
  is analysed repeatedly has to be typed out each time. A small configuration file
  (`--fund my-fund.json`) would be the obvious next step for real use. The defaults
  deliberately reproduce test case 1, so the tool runs out of the box.
* There is no graphical interface. The command line covers the required operability;
  the remaining time was spent on tests and documentation instead.
* The tests cover the cases and properties listed above over the ranges stated; they are
  not a proof for every possible combination of parameters.
