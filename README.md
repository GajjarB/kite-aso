```ansi

██╗  ██╗██╗████████╗███████╗
██║ ██╔╝██║╚══██╔══╝██╔════╝
█████╔╝ ██║   ██║   █████╗  
██╔═██╗ ██║   ██║   ██╔══╝  
██║  ██╗██║   ██║   ███████╗
╚═╝  ╚═╝╚═╝   ╚═╝   ╚══════╝

```

Formerly ASO PRO.

Kite now ships with **TerminalCore**, a premium hybrid CLI + TUI control plane for terminal-first workflows.

The repo still contains the ASO platform code under `src/aso_platform/`, but it now also includes a reusable Python-native terminal shell that can power:

- setup and onboarding flows
- environment-aware status checks
- log browsing
- task execution
- settings management
- full-screen keyboard-driven dashboards

This shell is generic by design, so the UI/UX and architecture are production-grade even when the underlying business logic is demo data.

## Why Python Instead Of Node

The original project already used a Python terminal stack, so TerminalCore was implemented natively in Python instead of forcing a new TypeScript runtime into the repo.

The result:

- `argparse + Rich` for clean command output
- `Textual` for the full-screen TUI
- reusable config and adapter layers
- console entrypoints for `terminalcore` and `tc`

## Features

### TerminalCore Shell

- direct CLI commands for power users
- interactive first-run setup wizard
- full-screen responsive dashboard
- warm Claude-inspired palette
- keyboard-first navigation
- clean config system under `~/.terminalcore/config.json`
- doctor checks
- logs, tasks, settings, and help screens
- reusable adapter layer for swapping in real backend logic later

### Existing Kite Platform

- app inspection by package ID
- keyword discovery from category + seed text
- keyword rank snapshots
- governed free/legal source registry
- workspace-based ASO baseline flow

## Installation

Install Python dependencies:

```bash
pip install -r requirements.txt
```

Optional: install local console entrypoints so `terminalcore` and `tc` work directly:

```bash
pip install -e .
```

## Quick Start

### TerminalCore

First run:

```bash
python terminalcore.py
```

Or, after editable install:

```bash
terminalcore
```

Run the setup wizard directly:

```bash
terminalcore init
```

Open the dashboard:

```bash
terminalcore dashboard
```

Check status:

```bash
terminalcore status
```

Run doctor:

```bash
terminalcore doctor
```

### Existing ASO Commands

```bash
python aso.py
python -m src.aso_platform.cli doctor
python -m src.aso_platform.cli keywords --category tools --seed "bmi calculator"
python -m src.aso_platform.cli workspace baseline calc-lab
```

Expanded local ASO intelligence commands:

```bash
python -m src.aso_platform.cli keywords build --category tools --seed "bmi calculator"
python -m src.aso_platform.cli keywords score "bmi calculator,loan calculator" --app-text "calculator finance tools"
python -m src.aso_platform.cli rank history "calculator" com.example.app
python -m src.aso_platform.cli rank delta "calculator" com.example.app
python -m src.aso_platform.cli share-of-voice "calculator,bmi calculator" com.example.app --competitors com.comp.one
python -m src.aso_platform.cli competitors add calc-lab com.comp.one,com.comp.two
python -m src.aso_platform.cli competitors gap calc-lab
python -m src.aso_platform.cli audit metadata com.example.app --keywords "calculator,bmi"
python -m src.aso_platform.cli reviews analyze com.example.app --count 50
python -m src.aso_platform.cli localization audit com.example.app --markets en-us,en-gb --keywords calculator
python -m src.aso_platform.cli ios inspect com.example.ios --country us
python -m src.aso_platform.cli reports export calc-lab --file reports/calc-lab.md --export-format md
python -m src.aso_platform.cli alerts check "calculator" com.example.app
python -m src.aso_platform.cli sources health
```

### SaaS MVP Web Console

Run the local SaaS-style dashboard:

```bash
python -m src.aso_platform.cli saas --port 8787
```

Open:

```text
http://127.0.0.1:8787
```

The web console provides local account/workspace creation, project tracking, baseline analysis, metadata audits, keyword scoring, saved analysis history, and source-governance status. Data is stored locally in `data/aso_saas.sqlite3`.

## Command Reference

### TerminalCore

```bash
terminalcore
terminalcore init
terminalcore dashboard
terminalcore status
terminalcore run
terminalcore logs
terminalcore logs --tail
terminalcore logs --level error
terminalcore config list
terminalcore config get theme
terminalcore config set environment staging
terminalcore config reset
terminalcore doctor
terminalcore help
```

### Command Behavior

- `terminalcore`: opens the dashboard, and launches first-run setup when config is missing.
- `terminalcore init`: guided setup wizard.
- `terminalcore dashboard`: full-screen TUI.
- `terminalcore status`: clean CLI health summary.
- `terminalcore run`: demo task run with progress.
- `terminalcore logs`: filtered or tail logs.
- `terminalcore config`: inspect or mutate config.
- `terminalcore doctor`: environment and config checks.
- `terminalcore help`: command reference.

## TUI Navigation

Keyboard bindings:

- `q` quit
- `Ctrl+C` quit safely
- `Enter` open selected section
- `↑↓` or `j/k` move through the sidebar
- `←` return to dashboard
- `→` open selected section
- `/` focus search when available
- `?` open help
- `r` refresh current screen
- `d` run the primary action
- `l` open logs
- `s` open settings
- `Esc` close modal or return

## Theme

TerminalCore uses a warm terminal palette centered around:

- background `#1E1A17`
- surfaces `#2A241F`, `#332B25`, `#3B322B`
- primary text `#F4EFE7`
- muted text `#8F8175`
- accent `#D97745`
- success `#7FA66A`
- warning `#D0A24C`
- error `#C7655A`
- info `#7DA7C7`

If true color is unavailable, the shell degrades gracefully to the terminal's supported palette.

## Config

Location:

```text
~/.terminalcore/config.json
```

Example:

```json
{
  "workspaceName": "TerminalCore",
  "environment": "development",
  "theme": "claude-warm",
  "demoData": true,
  "createdAt": "2026-05-16T00:00:00+00:00",
  "version": "1.0.0"
}
```

If the config is missing or invalid:

- first-run opens the setup wizard
- CLI commands show friendly errors
- `terminalcore doctor` and `terminalcore config reset` are suggested fixes

## Text Mockups

### Dashboard

```text
+- TerminalCore --------------------------------------------------------------+
| TerminalCore    Env Development    Version 1.0.0    Status Running         |
+----------------------+------------------------------------------------------+
| Navigate             | Overview                                             |
| > Dashboard          | +-----------+ +-----------+ +----------------------+ |
|   Projects           | | Status    | | Env       | | Health               | |
|   Tasks              | | Running   | | Dev       | | 4/4 checks passed    | |
|   Logs               | +-----------+ +-----------+ +----------------------+ |
|   Settings           | Recent Activity                                      |
|   Help               | Workspace loaded successfully                        |
+----------------------+------------------------------------------------------+
| Overview loaded.                                                        |
| ↑↓ Navigate   Enter Select   / Search   ? Help   q Quit                |
+-------------------------------------------------------------------------+
```

### Status

```text
TerminalCore Status

System       Running
Environment  Development
Version      1.0.0
Config       Valid
Last Check   Just now
```

## Folder Structure

```text
src/
  aso_platform/
  terminalcore/
    cli/
      commands/
    core/
      adapters/
      config/
      services/
    tui/
      components/
      screens/
      theme/
    utils/
    wizard/
tests/
  contract/
  unit/
terminalcore.py
tc.py
pyproject.toml
```

## Development

Run tests:

```bash
python -m unittest discover -s tests -p "test_*.py"
```

Compile key modules:

```bash
python -m py_compile terminalcore.py tc.py src/terminalcore/__main__.py src/terminalcore/cli/index.py src/terminalcore/tui/app.py
```

Launch the shell locally without editable install:

```bash
python terminalcore.py
python tc.py status
```

## Customization Guide

TerminalCore is designed to be replaceable behind the adapter boundary:

- swap `DemoSystemAdapter` with a real adapter
- keep `ConfigStore` for local state
- reuse the same CLI and TUI shell
- add domain-specific cards, tables, and doctor checks
- preserve the warm theme or provide additional theme modules

## Free And Legal ASO Policy

The Kite ASO subsystem remains intentionally conservative:

- public data only
- approved free public access patterns only
- no login bypass, paywall bypass, CAPTCHA circumvention, or anti-bot evasion
- uncertain sources are disabled instead of used silently

The source policy lives in `config/source_registry.json`.
