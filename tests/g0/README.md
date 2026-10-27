# G0 Tests

These are **executable tests**, not illustrative pseudocode.

## Automatic execution in GitHub
The workflow `.github/workflows/g0-structure.yml` runs the G0 tests automatically on relevant pull requests.

Open the pull request and select **Checks** to see the result.

## Local execution

From the repository root:

```bash
python -m pip install pytest
python -m pytest tests/g0 -q
```

On systems where the executable is `python3`:

```bash
python3 -m pip install pytest
python3 -m pytest tests/g0 -q
```

Expected result for the current baseline:

```text
2 passed
```

## What G0 tests validate
G0 does not yet contain production application code. These tests therefore validate architecture/repository invariants:
- mandatory governance documents exist;
- architecture documents exist;
- required bounded-module placeholders exist.

Functional, API, database, contract and end-to-end tests will be added gate by gate starting with G1.

## Important
Not every code block shown in project discussions is a command to execute. Only commands documented under a test/run section or stored as executable scripts/tests in the repository should be treated as executable instructions.
