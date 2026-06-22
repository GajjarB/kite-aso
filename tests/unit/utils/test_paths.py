from pathlib import Path
from unittest.mock import patch

from src.terminalcore.utils.paths import (
    APP_DIR,
    CONFIG_PATH,
    LOGS_PATH,
    STATE_PATH,
    ensure_app_dir,
)


def test_ensure_app_dir():
    """Test that ensure_app_dir creates the APP_DIR and returns it."""
    with patch.object(Path, "mkdir") as mock_mkdir:
        result = ensure_app_dir()

        # Should call mkdir with parents=True and exist_ok=True
        mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)

        # Should return APP_DIR
        assert result == APP_DIR


def test_paths_constants():
    """Test that path constants are relative to the user's home directory as expected."""
    assert APP_DIR == Path.home() / ".terminalcore"
    assert CONFIG_PATH == APP_DIR / "config.json"
    assert LOGS_PATH == APP_DIR / "logs.jsonl"
    assert STATE_PATH == APP_DIR / "state.json"
