"""Short alias launcher for TerminalCore."""

import sys
from pathlib import Path

# Run straight from a source checkout without installing: put src/ first so the
# real package wins over this same-named launcher script.
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from terminalcore.cli.index import main


if __name__ == "__main__":
    raise SystemExit(main())
