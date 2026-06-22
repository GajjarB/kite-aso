# Security And Compliance Policy

## Supported Scope

This project is in early platformization. Security and compliance reports are welcome for the current local CLI/TUI and source-governance logic.

## Reporting Issues

If you find a security or compliance issue, do not publish exploit details in a public issue. Open a private report through the project maintainer channel once one is configured, or temporarily file a minimal public issue that says a private security report is needed.

## Non-Negotiable Data Rules

ASO PRO must not include:

- credential collection,
- login bypass,
- paywall bypass,
- CAPTCHA circumvention,
- anti-bot evasion,
- fake account workflows,
- private or hidden endpoint scraping,
- bulk copyrighted content mirroring,
- paid-only source dependency for core features.

## Source Disable Rule

If a source becomes legally uncertain, technically blocked, or no longer free, it must be marked disabled or review-required in `config/source_registry.json`.

The product should degrade gracefully with warnings instead of continuing collection silently.

## Dependency Policy

Dependencies should be open-source, actively maintained, and avoid unnecessary network behavior. Optional integrations must not become required for core free/legal workflows.
