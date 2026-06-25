# Contributing To KITE ASO

Thank you for helping make KITE ASO useful for mobile app developers.

## Contribution Principles

- Keep every data path free and legal.
- Prefer deterministic, testable logic over vague claims.
- Add provenance, confidence, and warnings when data is incomplete.
- Do not add paid APIs, authenticated scraping, private endpoints, CAPTCHA bypass, or anti-bot evasion.
- When in doubt, disable the source and document the uncertainty.

## Good First Contributions

- Add category keyword packs to the local taxonomy in `core/keywords.py`.
- Improve scoring tests in `tests/unit/test_keyword_input.py`.
- Add CLI contract tests in `tests/contract/test_cli_json.py`.
- Improve docs, examples, and report explanations.
- Add fixture-based tests that do not hit live sources.

## Source Governance

Every new data source must be added to `config/source_registry.json` with:

- purpose,
- cost,
- auth requirement,
- legal notes,
- compliance status,
- rate-limit strategy,
- cache TTL,
- fallback behavior.

Runtime code may only use sources that are:

- `cost = free`,
- `auth = none`,
- `enabled = true`,
- `compliance_status = approved`.

## Test Checklist

Before submitting changes, run:

```bash
python -m unittest discover -s tests -p "test_*.py"
python -m py_compile aso.py core/keywords.py src/aso_platform/cli.py
```

## Pull Request Checklist

- The change has tests or a clear reason tests are not needed.
- Reports include source provenance when new analysis is added.
- Estimates are labeled as estimates.
- No questionable scraping path was introduced.
- The README or docs are updated when user-facing behavior changes.
