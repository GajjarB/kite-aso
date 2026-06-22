#!/usr/bin/env bash
# ASO Pro — Setup Script
# Run this once: bash setup.sh

set -e

echo ""
echo "  ◆ ASO Pro — Setup"
echo "  ─────────────────────────────"
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "  ✗ Python 3 not found. Install it first: https://python.org"
    exit 1
fi

PY_VER=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
echo "  ✓ Python $PY_VER found"

# Create venv
if [ ! -d ".venv" ]; then
    echo "  › Creating virtual environment..."
    python3 -m venv .venv
    echo "  ✓ Virtual environment created"
fi

# Activate and install
source .venv/bin/activate
echo "  › Installing dependencies..."
pip install -q --upgrade pip
pip install -q -r requirements.txt
echo "  ✓ All dependencies installed"

# Create __init__ files
touch core/__init__.py

echo ""
echo "  ─────────────────────────────"
echo "  ✓ Setup complete!"
echo ""
echo "  To launch ASO Pro:"
echo "    source .venv/bin/activate"
echo "    python3 aso.py"
echo ""
