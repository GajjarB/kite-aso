# Quickstart: Enterprise ASO Platform Foundation

## Run the new CLI

```powershell
python -m src.aso_platform.cli inspect com.whatsapp --format json
```

## Run with a different locale

```powershell
python -m src.aso_platform.cli inspect com.whatsapp --lang en --country us --format text
```

## Run the automated tests

```powershell
python -m unittest discover -s tests -p "test_*.py"
```

## Review source policy

Inspect [config/source_registry.json](/B:/Tasks/aso_pro/aso_pro/config/source_registry.json)
before enabling or expanding providers.

## MVP validation checklist

1. Confirm `.specify/feature.json` points to `specs/001-enterprise-aso-platform`.
2. Run the unit and contract tests.
3. Execute the CLI inspect command with JSON output.
4. Verify the output contains `request_context`, `evidence`, `scores`, `warnings`, and
   `confidence`.
5. If source policy changes, update the registry and rerun tests before using live fetches.
