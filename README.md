# driver-settlement-calculator
**Live tool:** https://aamirtechs.github.io/driver-settlement-calculator/ (runs in your browser, no install)

Weekly driver settlement breakdown for truck dispatching. Give it
one settlement week as JSON and it returns a readable breakdown:
gross pay, each deduction, escrow withheld, total deductions, net
pay, and ending balance. No account, no upload, no dependencies.
Just Python 3 and the standard library.

## The problem it solves

A driver settlement week mixes several kinds of math at once: a
percent of gross or a per-mile rate, cash advances, a list of
deductions, and an escrow withholding. Doing it in a spreadsheet
invites a copied formula error, and the driver cannot check the
result. This tool computes every line from one JSON file, with the
same rounding every time, so the dispatcher and the driver see the
same numbers.

## Input format

A JSON file describing one settlement week:

```json
{
  "driver": "Maria Lopez",
  "week_ending": "2026-10-31",
  "miles": 2450,
  "rate_per_mile": 2.10,
  "pay_basis": "percent",
  "pay_percent": 75,
  "advances": 500,
  "deductions": [
    {"name": "Fuel", "amount": 180},
    {"name": "Insurance", "amount": 125},
    {"name": "Trailer rental", "amount": 75}
  ],
  "escrow": {"percent": 5},
  "starting_balance": 120.50
}
```

Rules, in plain terms:

- `driver` is required. `week_ending` is optional and shown only.
- Gross revenue is either `gross_revenue` directly, or computed as
  `miles` times `rate_per_mile`. If both are given, `gross_revenue`
  wins.
- `pay_basis` is `percent` or `per_mile`. Percent pay defaults to
  75 percent of gross revenue when `pay_percent` is omitted.
  Per-mile pay needs `miles` and `pay_rate_per_mile`, and gross pay
  is miles times that rate.
- `advances` defaults to 0. `deductions` defaults to an empty list.
  Each deduction needs a `name` and an `amount`.
- Escrow is a percent of gross pay (`"escrow": {"percent": 5}`) or
  a fixed amount (`"escrow": {"amount": 100}`), never both. It
  defaults to no escrow. Top level `escrow_percent` and
  `escrow_amount` fields are accepted as aliases.
- `starting_balance` defaults to 0. Ending balance is starting
  balance plus net pay, so a negative week carries forward instead
  of vanishing.
- Money is rounded to cents, half up, using Decimal arithmetic.

## Usage

```sh
python3 driver_settlement_calculator.py examples/week.json
python3 driver_settlement_calculator.py examples/week.json --json
python3 driver_settlement_calculator.py examples/week.json --check
python3 driver_settlement_calculator.py examples/minimal.json
python3 driver_settlement_calculator.py examples/per-mile.json
```

`--json` prints the breakdown as JSON. `--check` validates only:
it prints OK and exits 0 when the input is valid, and exits 2
with an error message when it is not, so it works as a gate in a
script or CI run. It prints no breakdown.

## Real output

Running the included week example (Maria Lopez, 2,450 miles at
$2.10 per mile, 75 percent pay, $500 advances, three deductions,
5 percent escrow, $120.50 starting balance) gives:

```text
Driver: Maria Lopez
Week ending: 2026-10-31
Gross revenue: $5145.00
Gross pay: $3858.75
Advances: $500.00
Deductions:
  - Fuel: $180.00
  - Insurance: $125.00
  - Trailer rental: $75.00
Deductions total: $380.00
Escrow withheld: $192.94
Total deductions: $1072.94
Net pay: $2785.81
Starting balance: $120.50
Ending balance: $2906.31
```

The minimal example needs only a driver name and a gross revenue.
Defaults fill in the rest (75 percent pay, no advances, no
deductions, no escrow, zero starting balance):

```text
Driver: Sam Reed
Gross revenue: $4000.00
Gross pay: $3000.00
Advances: $0.00
Deductions: none
Deductions total: $0.00
Escrow withheld: $0.00
Total deductions: $0.00
Net pay: $3000.00
Starting balance: $0.00
Ending balance: $3000.00
```

The per-mile example (Dana Cole, 2,100 miles at $1.40 per mile,
$200 advances, $90 fuel deduction, $100 fixed escrow) gives:

```text
Driver: Dana Cole
Week ending: 2026-10-31
Gross revenue: $2940.00
Gross pay: $2940.00
Advances: $200.00
Deductions:
  - Fuel: $90.00
Deductions total: $90.00
Escrow withheld: $100.00
Total deductions: $390.00
Net pay: $2550.00
Starting balance: $0.00
Ending balance: $2550.00
```

With `--json`, the week example prints:

```json
{
  "driver": "Maria Lopez",
  "week_ending": "2026-10-31",
  "pay_basis": "percent",
  "gross_revenue": 5145.0,
  "gross_pay": 3858.75,
  "advances": 500.0,
  "deductions": [
    {
      "name": "Fuel",
      "amount": 180.0
    },
    {
      "name": "Insurance",
      "amount": 125.0
    },
    {
      "name": "Trailer rental",
      "amount": 75.0
    }
  ],
  "deductions_total": 380.0,
  "escrow_withheld": 192.94,
  "total_deductions": 1072.94,
  "net_pay": 2785.81,
  "starting_balance": 120.5,
  "ending_balance": 2906.31
}
```

With `--check`, a valid file prints:

```text
OK: settlement for Maria Lopez is valid
```

and an invalid file (for example `pay_percent` of 150) exits 2
with:

```text
error: pay_percent must be between 0 and 100, got 150
```

## Library use

The calculator is importable, and it accepts raw JSON-style dicts
as well as validated data:

```python
from driver_settlement_calculator import compute_settlement

result = compute_settlement({
    "driver": "Sam Reed",
    "gross_revenue": 4000,
})
print(result["net_pay"])  # 3000.0
```

## Validity rules

Validation rejects missing required fields (driver name, and a
revenue source for percent pay, or miles plus a pay rate for
per-mile pay), negative amounts (gross revenue, miles, rates,
advances, deductions, fixed escrow), and any percent outside 0 to
100 (pay percent, escrow percent). Escrow must give percent or
amount, not both. `--check` applies exactly these rules.

## Tests

```sh
python3 -m unittest discover -s tests
```

37 tests pass, covering percent pay math, per-mile math, advances
and deductions subtraction, escrow percent and fixed, ending
balance carry, JSON output shape, --check failures on bad input,
and edge cases (zero revenue, zero deductions, zero miles).
