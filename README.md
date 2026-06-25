<div align="center">

```ansi

██╗  ██╗██╗████████╗███████╗
██║ ██╔╝██║╚══██╔══╝██╔════╝
█████╔╝ ██║   ██║   █████╗  
██╔═██╗ ██║   ██║   ██╔══╝  
██║  ██╗██║   ██║   ███████╗
╚═╝  ╚═╝╚═╝   ╚═╝   ╚══════╝

```

**Kite ASO** - a keyboard-first App Store Optimization platform with a hybrid CLI and TUI workspace.

[![PyPI version](https://img.shields.io/pypi/v/kite-aso?color=%23D97745&style=flat-square)](https://pypi.org/project/kite-aso/)
[![Python](https://img.shields.io/pypi/pyversions/kite-aso?style=flat-square)](https://pypi.org/project/kite-aso/)
[![License: MIT](https://img.shields.io/badge/license-MIT-brightgreen?style=flat-square)](LICENSE)
[![GitHub](https://img.shields.io/badge/github-GajjarB%2Fkite--aso-181717?style=flat-square&logo=github)](https://github.com/GajjarB/kite-aso)

</div>

---

## Installation

```bash
pip install kite-aso
```

No cloning, no setup scripts, no manual configuration required.

**Requires Python 3.11 or later.** Verify your version with `python --version`.

---

## Quick Start

```bash
kite            # open the full-screen TUI dashboard
kite init       # run the first-time setup wizard
kite status     # print a health summary
kite doctor     # diagnose environment and config issues
```

---

## Features

### Terminal Dashboard

- Full-screen keyboard-driven TUI interface
- Projects, tasks, logs, and settings screens
- Warm dark theme with graceful degradation on limited terminals
- Runs on macOS, Linux, and Windows

### ASO Intelligence

- **App inspection** - analyse any app by Google Play package ID
- **Keyword discovery** - find high-value keywords by category and seed text
- **Keyword ranking** - snapshot and track keyword positions over time
- **Competitor analysis** - gap analysis against competitor apps
- **Metadata auditing** - score your title, description, and keyword fields
- **Review analysis** - sentiment and topic extraction from user reviews
- **Localisation audit** - compare keyword performance across markets
- **iOS support** - inspect Apple App Store listings

### Web Console

A local SaaS-style browser dashboard at `http://127.0.0.1:8787` with workspace management, project tracking, saved analysis history, and source-governance status.

---

## Command Reference

### Dashboard and Shell

| Command | Description |
|---|---|
| `kite` | Open the full-screen TUI dashboard |
| `kite init` | Run the first-time setup wizard |
| `kite dashboard` | Open the TUI dashboard directly |
| `kite status` | Print a health summary |
| `kite run` | Execute the primary task |
| `kite doctor` | Run environment and config checks |
| `kite help` | Show all available commands |

### Logs

| Command | Description |
|---|---|
| `kite logs` | Show recent logs |
| `kite logs --tail` | Follow live log output |
| `kite logs --level error` | Filter by level: `info` `success` `warning` `error` |

### Config

| Command | Description |
|---|---|
| `kite config list` | Show all config values |
| `kite config get <key>` | Get a single config value |
| `kite config set <key> <value>` | Set a config value |
| `kite config reset` | Reset config to defaults |

### ASO Commands

```bash
# Keyword discovery
kite keywords build --category tools --seed "bmi calculator"
kite keywords score "bmi calculator,loan calculator" --app-text "calculator finance"

# App inspection
kite inspect com.example.app
kite ios inspect com.example.ios --country us

# Rank tracking
kite rank history "calculator" com.example.app
kite rank delta "calculator" com.example.app

# Competitor analysis
kite competitors add my-workspace com.comp.one,com.comp.two
kite competitors gap my-workspace
kite share-of-voice "calculator,bmi" com.example.app --competitors com.comp.one

# Metadata and reviews
kite audit metadata com.example.app --keywords "calculator,bmi"
kite reviews analyze com.example.app --count 50
kite localization audit com.example.app --markets en-us,en-gb --keywords calculator

# Reports and alerts
kite reports export my-workspace --file report.md --export-format md
kite alerts check "calculator" com.example.app
kite sources health
```

### Web Console

```bash
kite saas                    # start on default port 8787
kite saas --port 9000        # custom port
kite saas --host 0.0.0.0     # expose to local network
# Open: http://127.0.0.1:8787
```

---

## TUI Keyboard Shortcuts

| Key | Action |
|---|---|
| `Up` `Down` or `j` `k` | Navigate sidebar |
| `Enter` or `Right` | Open selected section |
| `Left` | Return to dashboard |
| `/` | Focus search |
| `?` | Open help screen |
| `r` | Refresh current screen |
| `d` | Run primary action |
| `l` | Open logs |
| `s` | Open settings |
| `Esc` | Close modal or go back |
| `q` or `Ctrl+C` | Quit |

---

## Configuration

Config is stored at `~/.terminalcore/config.json` and created automatically on first run.

```json
{
  "workspaceName": "Kite",
  "environment": "development",
  "theme": "claude-warm",
  "version": "1.0.0"
}
```

Reset to defaults at any time:

```bash
kite config reset
```

---

## Data Policy

Kite uses public data sources only:

- No login bypass, paywall bypass, or CAPTCHA circumvention
- No anti-bot evasion tactics
- Uncertain or legally ambiguous sources are disabled, not silently used

Source rules are defined in `config/source_registry.json`.

---

## Contributing

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

```bash
# Clone and install in development mode
git clone https://github.com/GajjarB/kite-aso.git
cd kite-aso
pip install -e ".[dev]"

# Run tests
python -m pytest tests/
```

---

## License

MIT - see [LICENSE](LICENSE) for details.
