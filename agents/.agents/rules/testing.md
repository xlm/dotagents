# Testing

## Coverage

1. Add a test for the primary success path. Done when the main workflow has a passing test covering its expected outputs.
2. Add an edge-case test for each non-trivial branch or error class. If a branch does not get a test, add a PR comment explaining why.
3. Place the test file to mirror the source layout.
4. Keep unit tests fast and external-free. Mock network, database, and external I/O.
5. Separate and gate integration and smoke tests.
6. Keep shared fixtures stable and focused.

Done when the changed code has a passing primary test, edge-case tests for every non-trivial branch, and matching integration tests when needed.

## Guard code

When adding or tightening a validator, guard, parser, or regex:

1. State the invariant in one sentence.
2. Add the attack matrix: tests for valid inputs, invalid inputs, and
   one bypass-coverage test per plausible bypass identified.

Plausible bypasses include punctuation, quoting, Unicode numerals and combining marks, case, spacing, and missing separators.

Done when the invariant is stated and every class of input has a passing test.
