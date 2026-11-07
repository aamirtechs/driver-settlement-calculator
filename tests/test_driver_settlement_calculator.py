"""Tests for driver_settlement_calculator."""

import json
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from driver_settlement_calculator import (  # noqa: E402
    compute_settlement,
    format_text,
    main,
    validate_settlement,
)

ROOT = Path(__file__).resolve().parent.parent


def base(**overrides):
    data = {"driver": "Test Driver", "gross_revenue": 4000}
    data.update(overrides)
    return data


class TestPercentPay(unittest.TestCase):
    def test_percent_pay_math(self):
        result = compute_settlement(base(pay_percent=75))
        self.assertEqual(result["gross_pay"], 3000.00)

    def test_percent_pay_default_is_75(self):
        result = compute_settlement(base())
        self.assertEqual(result["gross_pay"], 3000.00)

    def test_percent_pay_100(self):
        result = compute_settlement(base(pay_percent=100))
        self.assertEqual(result["gross_pay"], 4000.00)

    def test_percent_pay_zero(self):
        result = compute_settlement(base(pay_percent=0))
        self.assertEqual(result["gross_pay"], 0.00)

    def test_gross_revenue_from_miles_and_rate(self):
        result = compute_settlement(
            base(miles=2000, rate_per_mile=2.00, pay_percent=50))
        self.assertEqual(result["gross_revenue"], 4000.00)
        self.assertEqual(result["gross_pay"], 2000.00)

    def test_gross_revenue_wins_over_miles(self):
        result = compute_settlement(
            base(miles=9999, rate_per_mile=9.99, pay_percent=50))
        self.assertEqual(result["gross_revenue"], 4000.00)


class TestPerMilePay(unittest.TestCase):
    def test_per_mile_math(self):
        result = compute_settlement(
            base(miles=2100, pay_basis="per_mile", pay_rate_per_mile=1.40))
        self.assertEqual(result["gross_pay"], 2940.00)

    def test_per_mile_needs_miles(self):
        with self.assertRaises(ValueError):
            validate_settlement(
                {"driver": "X", "pay_basis": "per_mile",
                 "pay_rate_per_mile": 1.40})

    def test_per_mile_needs_rate(self):
        with self.assertRaises(ValueError):
            validate_settlement(
                {"driver": "X", "pay_basis": "per_mile", "miles": 1000})

    def test_unknown_pay_basis_rejected(self):
        with self.assertRaises(ValueError):
            validate_settlement(base(pay_basis="flat"))


class TestDeductionsAndBalances(unittest.TestCase):
    def test_advances_and_deductions_subtracted(self):
        result = compute_settlement(base(
            pay_percent=100, advances=500,
            deductions=[{"name": "Fuel", "amount": 180},
                        {"name": "Insurance", "amount": 125}]))
        self.assertEqual(result["total_deductions"], 805.00)
        self.assertEqual(result["net_pay"], 3195.00)

    def test_escrow_percent_of_gross_pay(self):
        result = compute_settlement(
            base(pay_percent=100, escrow={"percent": 5}))
        self.assertEqual(result["escrow_withheld"], 200.00)
        self.assertEqual(result["net_pay"], 3800.00)

    def test_escrow_fixed_amount(self):
        result = compute_settlement(
            base(pay_percent=100, escrow={"amount": 100}))
        self.assertEqual(result["escrow_withheld"], 100.00)
        self.assertEqual(result["net_pay"], 3900.00)

    def test_escrow_percent_and_amount_together_rejected(self):
        with self.assertRaises(ValueError):
            validate_settlement(
                base(escrow={"percent": 5, "amount": 100}))

    def test_ending_balance_carry(self):
        result = compute_settlement(
            base(pay_percent=100, starting_balance=120.50))
        self.assertEqual(result["ending_balance"], 4120.50)

    def test_ending_balance_with_negative_net(self):
        result = compute_settlement(base(
            pay_percent=50, advances=2500, starting_balance=100))
        self.assertEqual(result["net_pay"], -500.00)
        self.assertEqual(result["ending_balance"], -400.00)

    def test_deductions_total_reported(self):
        result = compute_settlement(base(
            deductions=[{"name": "A", "amount": 10},
                        {"name": "B", "amount": 20.50}]))
        self.assertEqual(result["deductions_total"], 30.50)

    def test_rounding_to_cents(self):
        result = compute_settlement(
            base(gross_revenue=100.005, pay_percent=100))
        self.assertEqual(result["gross_pay"], 100.01)


class TestEdgeCases(unittest.TestCase):
    def test_zero_revenue(self):
        result = compute_settlement(base(gross_revenue=0, pay_percent=75))
        self.assertEqual(result["gross_pay"], 0.00)
        self.assertEqual(result["net_pay"], 0.00)

    def test_zero_deductions(self):
        result = compute_settlement(base())
        self.assertEqual(result["deductions"], [])
        self.assertEqual(result["total_deductions"], 0.00)
        self.assertEqual(result["net_pay"], 3000.00)

    def test_zero_miles_per_mile(self):
        result = compute_settlement(
            base(pay_basis="per_mile", miles=0, pay_rate_per_mile=1.40))
        self.assertEqual(result["gross_pay"], 0.00)


class TestValidation(unittest.TestCase):
    def test_missing_driver_rejected(self):
        with self.assertRaises(ValueError):
            validate_settlement({"gross_revenue": 1000})

    def test_missing_revenue_source_rejected(self):
        with self.assertRaises(ValueError):
            validate_settlement({"driver": "X"})

    def test_negative_gross_rejected(self):
        with self.assertRaises(ValueError):
            validate_settlement(base(gross_revenue=-100))

    def test_negative_advance_rejected(self):
        with self.assertRaises(ValueError):
            validate_settlement(base(advances=-50))

    def test_negative_deduction_rejected(self):
        with self.assertRaises(ValueError):
            validate_settlement(
                base(deductions=[{"name": "Fuel", "amount": -10}]))

    def test_percent_above_100_rejected(self):
        with self.assertRaises(ValueError):
            validate_settlement(base(pay_percent=101))

    def test_percent_below_zero_rejected(self):
        with self.assertRaises(ValueError):
            validate_settlement(base(pay_percent=-1))

    def test_escrow_percent_above_100_rejected(self):
        with self.assertRaises(ValueError):
            validate_settlement(base(escrow={"percent": 150}))

    def test_negative_miles_rejected(self):
        with self.assertRaises(ValueError):
            validate_settlement(
                base(miles=-10, rate_per_mile=2.00))

    def test_deduction_missing_name_rejected(self):
        with self.assertRaises(ValueError):
            validate_settlement(base(deductions=[{"amount": 10}]))


class TestCli(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, str(ROOT / "driver_settlement_calculator.py")]
            + list(args),
            capture_output=True, text=True, cwd=str(ROOT))

    def test_json_output_shape(self):
        proc = self.run_cli(str(ROOT / "examples" / "week.json"), "--json")
        self.assertEqual(proc.returncode, 0)
        data = json.loads(proc.stdout)
        for key in ("driver", "gross_revenue", "gross_pay", "advances",
                    "deductions", "escrow_withheld", "total_deductions",
                    "net_pay", "starting_balance", "ending_balance"):
            self.assertIn(key, data)
        self.assertEqual(data["driver"], "Maria Lopez")
        self.assertEqual(data["net_pay"], 2785.81)
        self.assertEqual(data["ending_balance"], 2906.31)

    def test_text_output_contains_lines(self):
        proc = self.run_cli(str(ROOT / "examples" / "week.json"))
        self.assertEqual(proc.returncode, 0)
        self.assertIn("Gross pay: $3858.75", proc.stdout)
        self.assertIn("Net pay: $2785.81", proc.stdout)

    def test_check_passes_on_valid(self):
        proc = self.run_cli(str(ROOT / "examples" / "week.json"), "--check")
        self.assertEqual(proc.returncode, 0)
        self.assertIn("OK", proc.stdout)

    def test_check_fails_on_bad_input(self):
        bad = ROOT / "tests" / "_bad_tmp.json"
        bad.write_text(json.dumps(base(pay_percent=150)), encoding="utf-8")
        try:
            proc = self.run_cli(str(bad), "--check")
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("error", proc.stderr)
        finally:
            bad.unlink(missing_ok=True)

    def test_cli_fails_on_negative_amount(self):
        bad = ROOT / "tests" / "_bad2_tmp.json"
        bad.write_text(json.dumps(base(advances=-5)), encoding="utf-8")
        try:
            proc = self.run_cli(str(bad))
            self.assertNotEqual(proc.returncode, 0)
        finally:
            bad.unlink(missing_ok=True)

    def test_format_text_minimal(self):
        text = format_text(compute_settlement(base()))
        self.assertIn("Deductions: none", text)
        self.assertIn("Ending balance: $3000.00", text)


if __name__ == "__main__":
    unittest.main()
