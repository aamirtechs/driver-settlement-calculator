#!/usr/bin/env python3
"""Weekly driver settlement breakdown for truck dispatching.

Input is a JSON file describing one settlement week:

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
        {"name": "Insurance", "amount": 125}
      ],
      "escrow": {"percent": 5},
      "starting_balance": 120.50
    }

Pay basis is "percent" (a percent of gross revenue) or "per_mile"
(a pay rate per mile). Gross revenue is either given directly as
"gross_revenue" or computed as miles times rate_per_mile. Escrow
withholding is a percent of gross pay or a fixed amount, given as
"escrow": {"percent": 5} or "escrow": {"amount": 100}. Sensible
defaults apply: percent pay at 75 percent, no advances, no
deductions, no escrow, and a zero starting balance, so a file with
only a driver name and a gross revenue already settles.

Only the Python standard library is used. Money is rounded to
cents with Decimal arithmetic.

Usage:

    python3 driver_settlement_calculator.py examples/week.json
    python3 driver_settlement_calculator.py examples/week.json --json
    python3 driver_settlement_calculator.py examples/week.json --check
"""

import argparse
import json
import sys
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

CENT = Decimal("0.01")
DEFAULT_PAY_PERCENT = Decimal("75")


def _money(value, field):
    """Convert a value to Decimal, raising ValueError if not a number."""
    if isinstance(value, bool):
        raise ValueError("%s must be a number, got %r" % (field, value))
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError("%s must be a number, got %r" % (field, value))
    if result.is_nan() or result.is_infinite():
        raise ValueError("%s must be a finite number, got %r" % (field, value))
    return result


def _non_negative(value, field):
    """Require a money or quantity value to be zero or positive."""
    if value < 0:
        raise ValueError("%s must not be negative, got %s" % (field, value))
    return value


def _percent(value, field):
    """Require a percent value to sit inside 0 to 100 inclusive."""
    if value < 0 or value > 100:
        raise ValueError(
            "%s must be between 0 and 100, got %s" % (field, value))
    return value


def _round(value):
    """Round a Decimal to cents, half up."""
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def _to_float(value):
    """Convert a Decimal to a JSON friendly float with two decimals."""
    return float(_round(value))


def load_settlement(path):
    """Load and validate a settlement JSON file, returning a dict."""
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    return validate_settlement(data)


def validate_settlement(data):
    """Validate raw settlement data and return a normalized dict.

    Raises ValueError on missing required fields, negative amounts,
    or percents outside 0 to 100. Normalization fills in the
    documented defaults so compute_settlement can work on the result
    directly. The returned dict is safe to pass to compute_settlement
    or to serialize, because all money values are Decimal.
    """
    if not isinstance(data, dict):
        raise ValueError("settlement file must contain a JSON object")
    driver = data.get("driver")
    if not driver or not isinstance(driver, str):
        raise ValueError("settlement needs a driver name (missing 'driver')")
    week_ending = data.get("week_ending")

    gross_revenue = None
    if data.get("gross_revenue") is not None:
        gross_revenue = _non_negative(
            _money(data["gross_revenue"], "gross_revenue"), "gross_revenue")
    miles = None
    if data.get("miles") is not None:
        miles = _non_negative(_money(data["miles"], "miles"), "miles")
    rate_per_mile = None
    if data.get("rate_per_mile") is not None:
        rate_per_mile = _non_negative(
            _money(data["rate_per_mile"], "rate_per_mile"), "rate_per_mile")

    pay_basis = data.get("pay_basis", "percent")
    if pay_basis not in ("percent", "per_mile"):
        raise ValueError(
            "pay_basis must be 'percent' or 'per_mile', got %r" % (pay_basis,))

    pay_percent = None
    if data.get("pay_percent") is not None:
        pay_percent = _percent(
            _money(data["pay_percent"], "pay_percent"), "pay_percent")
    pay_rate_per_mile = None
    if data.get("pay_rate_per_mile") is not None:
        pay_rate_per_mile = _non_negative(
            _money(data["pay_rate_per_mile"], "pay_rate_per_mile"),
            "pay_rate_per_mile")

    if pay_basis == "percent":
        if pay_percent is None:
            pay_percent = DEFAULT_PAY_PERCENT
        if gross_revenue is None and (miles is None or rate_per_mile is None):
            raise ValueError(
                "percent pay needs gross_revenue, or miles plus "
                "rate_per_mile to compute it")
    else:
        if miles is None:
            raise ValueError("per_mile pay needs miles")
        if pay_rate_per_mile is None:
            raise ValueError("per_mile pay needs pay_rate_per_mile")

    advances = _non_negative(
        _money(data.get("advances", 0), "advances"), "advances")

    deductions_raw = data.get("deductions", [])
    if not isinstance(deductions_raw, list):
        raise ValueError("deductions must be a list of name and amount pairs")
    deductions = []
    for index, item in enumerate(deductions_raw):
        if not isinstance(item, dict):
            raise ValueError("deduction %d must be an object" % index)
        name = item.get("name")
        if not name or not isinstance(name, str):
            raise ValueError("deduction %d is missing a name" % index)
        if item.get("amount") is None:
            raise ValueError("deduction %r is missing an amount" % name)
        amount = _non_negative(
            _money(item["amount"], "deduction %r amount" % name),
            "deduction %r amount" % name)
        deductions.append({"name": name, "amount": amount})

    escrow_percent = None
    escrow_amount = None
    escrow = data.get("escrow")
    if escrow is not None:
        if not isinstance(escrow, dict):
            raise ValueError("escrow must be an object with percent or amount")
        if escrow.get("percent") is not None:
            escrow_percent = _percent(
                _money(escrow["percent"], "escrow percent"), "escrow percent")
        if escrow.get("amount") is not None:
            escrow_amount = _non_negative(
                _money(escrow["amount"], "escrow amount"), "escrow amount")
        if escrow_percent is not None and escrow_amount is not None:
            raise ValueError("escrow must give percent or amount, not both")
    if data.get("escrow_percent") is not None:
        if escrow_percent is not None or escrow_amount is not None:
            raise ValueError("escrow is given twice")
        escrow_percent = _percent(
            _money(data["escrow_percent"], "escrow_percent"), "escrow_percent")
    if data.get("escrow_amount") is not None:
        if escrow_percent is not None or escrow_amount is not None:
            raise ValueError("escrow is given twice")
        escrow_amount = _non_negative(
            _money(data["escrow_amount"], "escrow_amount"), "escrow_amount")

    starting_balance = _money(
        data.get("starting_balance", 0), "starting_balance")

    return {
        "driver": driver,
        "week_ending": week_ending,
        "gross_revenue": gross_revenue,
        "miles": miles,
        "rate_per_mile": rate_per_mile,
        "pay_basis": pay_basis,
        "pay_percent": pay_percent,
        "pay_rate_per_mile": pay_rate_per_mile,
        "advances": advances,
        "deductions": deductions,
        "escrow_percent": escrow_percent,
        "escrow_amount": escrow_amount,
        "starting_balance": starting_balance,
    }


def compute_settlement(data):
    """Compute the settlement breakdown for validated or raw data.

    Accepts either validate_settlement output or a raw JSON style
    dict, which is validated first. Returns a dict with float money
    values rounded to cents, plus the deduction list.
    """
    if not isinstance(data.get("advances"), Decimal):
        data = validate_settlement(data)
    if data["gross_revenue"] is not None:
        gross_revenue = data["gross_revenue"]
    elif data["rate_per_mile"] is not None:
        gross_revenue = data["miles"] * data["rate_per_mile"]
    else:
        # Per-mile pay with no separate revenue rate: the revenue base
        # is the same miles times the pay rate, so gross pay below
        # equals gross revenue.
        gross_revenue = data["miles"] * data["pay_rate_per_mile"]
    if data["pay_basis"] == "percent":
        gross_pay = gross_revenue * data["pay_percent"] / Decimal("100")
    else:
        gross_pay = data["miles"] * data["pay_rate_per_mile"]
    gross_revenue = _round(gross_revenue)
    gross_pay = _round(gross_pay)
    if data["escrow_percent"] is not None:
        escrow_withheld = gross_pay * data["escrow_percent"] / Decimal("100")
    elif data["escrow_amount"] is not None:
        escrow_withheld = data["escrow_amount"]
    else:
        escrow_withheld = Decimal("0")
    escrow_withheld = _round(escrow_withheld)
    deductions = [
        {"name": item["name"], "amount": _to_float(item["amount"])}
        for item in data["deductions"]
    ]
    deductions_total = sum(
        (item["amount"] for item in data["deductions"]), Decimal("0"))
    advances = _round(data["advances"])
    total_deductions = _round(advances + deductions_total + escrow_withheld)
    net_pay = _round(gross_pay - total_deductions)
    starting_balance = _round(data["starting_balance"])
    ending_balance = _round(starting_balance + net_pay)
    return {
        "driver": data["driver"],
        "week_ending": data["week_ending"],
        "pay_basis": data["pay_basis"],
        "gross_revenue": _to_float(gross_revenue),
        "gross_pay": _to_float(gross_pay),
        "advances": _to_float(advances),
        "deductions": deductions,
        "deductions_total": _to_float(_round(deductions_total)),
        "escrow_withheld": _to_float(escrow_withheld),
        "total_deductions": _to_float(total_deductions),
        "net_pay": _to_float(net_pay),
        "starting_balance": _to_float(starting_balance),
        "ending_balance": _to_float(ending_balance),
    }


def format_text(result):
    """Render a settlement breakdown as readable plain text."""
    lines = []
    lines.append("Driver: %s" % result["driver"])
    if result["week_ending"]:
        lines.append("Week ending: %s" % result["week_ending"])
    lines.append("Gross revenue: $%.2f" % result["gross_revenue"])
    lines.append("Gross pay: $%.2f" % result["gross_pay"])
    lines.append("Advances: $%.2f" % result["advances"])
    if result["deductions"]:
        lines.append("Deductions:")
        for item in result["deductions"]:
            lines.append("  - %s: $%.2f" % (item["name"], item["amount"]))
    else:
        lines.append("Deductions: none")
    lines.append("Deductions total: $%.2f" % result["deductions_total"])
    lines.append("Escrow withheld: $%.2f" % result["escrow_withheld"])
    lines.append("Total deductions: $%.2f" % result["total_deductions"])
    lines.append("Net pay: $%.2f" % result["net_pay"])
    lines.append("Starting balance: $%.2f" % result["starting_balance"])
    lines.append("Ending balance: $%.2f" % result["ending_balance"])
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Compute a weekly driver settlement breakdown.")
    parser.add_argument("settlement", help="JSON settlement file")
    parser.add_argument("--json", action="store_true",
                        help="print the breakdown as JSON")
    parser.add_argument("--check", action="store_true",
                        help="validate only: exit 0 when valid, non-zero "
                        "when invalid, without printing a breakdown")
    args = parser.parse_args(argv)
    try:
        settlement = load_settlement(args.settlement)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print("error: %s" % error, file=sys.stderr)
        return 2
    if args.check:
        print("OK: settlement for %s is valid" % settlement["driver"])
        return 0
    result = compute_settlement(settlement)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(format_text(result), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
