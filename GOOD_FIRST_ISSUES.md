# Good first issues

Ideas for first-time contributors. Each one is small, tested, and
does not change the core settlement math.

1. Add a `--format csv` option that prints the breakdown as one CSV
   row with a header, so a dispatcher can append weekly settlements
   to a spreadsheet, with a test proving the header and row match.
2. Add an escrow cap option, for example `"escrow": {"percent": 5,
   "cap": 5000}`, that stops withholding once the cap is reached
   given a lifetime escrow balance field, with tests for below cap,
   at cap, and above cap.
3. Add a `--summary` flag that reads several settlement JSON files
   and prints one totals row per driver (weeks, gross pay, net pay,
   ending balance), with a test on two sample files.
4. Add optional per-deduction categories (fuel, insurance, other)
   in the input, and print a subtotal per category in the text
   output, with a test proving the subtotals add up to the
   deductions total.
