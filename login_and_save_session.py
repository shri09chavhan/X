#!/usr/bin/env python3
"""
Interactive Twitter / X Login & Session Extractor
Uses CloakBrowser to launch a stealth Chromium window.
Allows the user to log in manually, then exports session cookies & storage to session.json.
"""

import json
import logging
import os
import sys
import time
from pathlib import Path

# Enable cloakbrowser download progress and info logs
logging.basicConfig(
    level=logging.INFO,
    format="[%(name)s] %(message)s"
)

try:
    import cloakbrowser
except ImportError:
    print("\n[!] cloakbrowser is not installed in this environment.")
    print("    Please run: source .venv/bin/activate && pip install cloakbrowser\n")
    sys.exit(1)


SESSION_FILE = Path("session.json")
LOGIN_URL = "https://x.com/i/flow/login"
HOME_URL_KEYWORDS = ["x.com/home", "twitter.com/home"]


def print_banner():
    print("=" * 65)
    print("        CloakBrowser - Twitter/X Session Generator")
    print("=" * 65)
    print("  1. A stealth Chromium browser window will open.")
    print("  2. Enter your Twitter/X credentials and complete login.")
    print("  3. Once you see the Home feed, press ENTER in this terminal")
    print("     (or wait for auto-detection).")
    print("  4. Your session will be safely exported to 'session.json'.")
    print("=" * 65)
    print()


def verify_session_saved(session_path: Path):
    if not session_path.exists():
        print(f"[✗] Error: {session_path} was not created.")
        return False

    try:
        with open(session_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        cookies = data.get("cookies", [])
        cookie_names = {c.get("name") for c in cookies}
        print(f"\n[✓] Session file saved: {session_path} ({session_path.stat().st_size} bytes)")
        print(f"[✓] Captured {len(cookies)} cookies across {len(data.get('origins', []))} storage origins.")

        # Check for core Twitter auth cookies
        has_auth = "auth_token" in cookie_names
        has_ct0 = "ct0" in cookie_names

        if has_auth and has_ct0:
            print("[★] Verified critical authentication tokens ('auth_token' & 'ct0') are present!")
            print("[★] You are fully authenticated and ready for automation.")
        elif has_auth:
            print("[✓] Found 'auth_token'. Session is likely valid.")
        else:
            print("[!] Warning: 'auth_token' not detected in cookies yet.")
            print("    Make sure you completed full login before finishing.")

        return True
    except Exception as e:
        print(f"[✗] Error reading session file: {e}")
        return False


def main():
    print_banner()

    print("[*] Launching stealth Chromium browser with CloakBrowser...")
    print("    (Note: On the first launch, CloakBrowser downloads its ~150MB stealth Chromium binary.")
    print("     Please wait a minute for download and extraction to complete)...")
    try:
        # Launch stealth browser context in headed mode
        # viewport=None uses natural window size
        context = cloakbrowser.launch_context(
            headless=False,
            viewport=None,
            humanize=True,
            args=[
                "--start-maximized",
                "--disable-blink-features=AutomationControlled",
            ]
        )
    except Exception as err:
        print(f"[✗] Failed to launch browser: {err}")
        print("\nIf browser binaries are missing, run:")
        print("    playwright install chromium\n")
        sys.exit(1)

    try:
        page = context.new_page()
        print(f"[*] Navigating to {LOGIN_URL}...")
        page.goto(LOGIN_URL, wait_until="domcontentloaded")

        print("\n" + "-" * 65)
        print(">>> BROWSER IS READY: Please log into your Twitter/X account now. <<<")
        print("-" * 65)

        # Polling loop: Wait for user input OR auto-detect home URL
        print("\nWaiting for login...")
        print("Hint: You can press ENTER right here in the terminal once logged in.\n")

        login_confirmed = False
        import select

        while not login_confirmed:
            # Check current URL
            current_url = page.url
            if any(kw in current_url for kw in HOME_URL_KEYWORDS):
                print(f"[✓] Detected Home Feed: {current_url}")
                # Give a 3-second grace period for all session cookies to set
                time.sleep(3)
                login_confirmed = True
                break

            # Check if user pressed ENTER in stdin without blocking completely
            if sys.stdin in select.select([sys.stdin], [], [], 1.0)[0]:
                sys.stdin.readline()
                login_confirmed = True
                break

        print("[*] Capturing storage state and session cookies...")
        context.storage_state(path=str(SESSION_FILE))

        verify_session_saved(SESSION_FILE)

    except KeyboardInterrupt:
        print("\n[*] Interrupted by user. Attempting to save current session state...")
        try:
            context.storage_state(path=str(SESSION_FILE))
            verify_session_saved(SESSION_FILE)
        except Exception:
            pass
    except Exception as ex:
        print(f"[✗] An unexpected error occurred: {ex}")
    finally:
        print("[*] Closing browser session...")
        try:
            context.close()
        except Exception:
            pass

    print("\n[Done] You can now run automation scripts using 'session.json'!")


if __name__ == "__main__":
    main()
