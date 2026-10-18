#!/usr/bin/env bash
set -euo pipefail

# Configuration
VENV_DIR=".venv"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

echo "=========================================="
echo " Setting up CloakBrowser Automation Project"
echo "=========================================="

# 1. Detect Python 3
if command -v python3 &>/dev/null; then
    PYTHON_CMD="python3"
elif command -v python &>/dev/null; then
    PYTHON_CMD="python"
else
    echo "Error: Python is not installed. Please install Python 3 and try again." >&2
    exit 1
fi

echo "[1/5] Using $($PYTHON_CMD --version)..."

# 2. Create Virtual Environment
if [ ! -d "$VENV_DIR" ]; then
    echo "[2/5] Creating virtual environment in '$VENV_DIR'..."
    "$PYTHON_CMD" -m venv "$VENV_DIR"
else
    echo "[2/5] Virtual environment '$VENV_DIR' already exists."
fi

# Locate virtualenv binaries
VENV_PYTHON="$PROJECT_DIR/$VENV_DIR/bin/python"
VENV_PIP="$PROJECT_DIR/$VENV_DIR/bin/pip"

# 3. Upgrade pip and core packaging tools inside virtual environment
echo "[3/5] Upgrading pip and packaging tools..."
"$VENV_PIP" install --upgrade pip setuptools wheel --quiet

# 4. Generate requirements.txt & Install cloakbrowser
echo "[4/5] Installing cloakbrowser..."
if [ ! -f "requirements.txt" ]; then
    echo "cloakbrowser" > requirements.txt
    echo "  - Created requirements.txt with cloakbrowser"
else
    if ! grep -qi "^cloakbrowser" requirements.txt; then
        echo "cloakbrowser" >> requirements.txt
        echo "  - Added cloakbrowser to requirements.txt"
    fi
fi

"$VENV_PIP" install -r requirements.txt

echo "[4b/5] Installing Chromium browser for automation..."
"$PROJECT_DIR/$VENV_DIR/bin/playwright" install chromium

# 5. Create starter files if they don't already exist
echo "[5/5] Setting up project template files..."

# .gitignore
if [ ! -f ".gitignore" ]; then
    cat << 'EOF' > .gitignore
# Virtual environment
.venv/
venv/
env/

# Python bytecode
__pycache__/
*.py[cod]
*$py.class

# Environment variables & secrets
.env
.env.local

# Browser data & automation logs
*.log
screenshots/
downloads/
user_data/
EOF
    echo "  - Created .gitignore"
fi

# main.py starter script
if [ ! -f "main.py" ]; then
    cat << 'EOF' > main.py
"""Sample starter script for CloakBrowser automation."""

import sys

try:
    import cloakbrowser
    print(f"[✓] CloakBrowser loaded successfully (version: {getattr(cloakbrowser, '__version__', 'installed')})")
except ImportError as err:
    print(f"[✗] Error importing cloakbrowser: {err}", file=sys.stderr)
    print("Ensure you have activated the virtual environment: source .venv/bin/activate", file=sys.stderr)
    sys.exit(1)


def main():
    print("Ready to automate with CloakBrowser!")
    # Example:
    # browser = cloakbrowser.launch(headless=False)
    # page = browser.new_page()
    # page.goto("https://example.com")


if __name__ == "__main__":
    main()
EOF
    echo "  - Created starter main.py"
fi

echo ""
echo "=========================================="
echo " Setup finished successfully!"
echo "=========================================="
echo "To activate your virtual environment, run:"
echo "    source $VENV_DIR/bin/activate"
echo ""
echo "To run your script:"
echo "    python main.py"
echo "=========================================="
