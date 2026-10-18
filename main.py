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
