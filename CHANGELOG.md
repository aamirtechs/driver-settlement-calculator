# Changelog

## 1.0.0 (2026-11-01)

- First release.
- Zero-dependency Python CLI and importable library: weekly driver
  settlement breakdown for truck dispatching.
- Percent of gross pay and per-mile pay, gross revenue given
  directly or computed from miles times rate per mile.
- Advances, named deductions, escrow as percent of gross pay or
  fixed amount, and ending balance carried from a starting balance.
- Decimal money math rounded to cents, half up.
- `--json` and `--check` flags; `--check` exits non-zero on invalid
  input (negative amounts, percent outside 0 to 100, missing
  required fields).
- 37 passing tests.
