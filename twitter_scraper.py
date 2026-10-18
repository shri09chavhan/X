#!/usr/bin/env python3
"""
Twitter / X Automation & Scraper using CloakBrowser and session.json.
Demonstrates automated navigation, clicking (like, bookmark, follow, scroll),
and extracting tweet data without re-logging in.
"""

import json
import logging
import random
import sys
import time
from pathlib import Path

# Enable cloakbrowser info logs
logging.basicConfig(
    level=logging.INFO,
    format="[%(name)s] %(message)s"
)

try:
    import cloakbrowser
except ImportError:
    print("[!] cloakbrowser is not installed in this environment.")
    print("    Run: source .venv/bin/activate && pip install cloakbrowser")
    sys.exit(1)

SESSION_FILE = Path("session.json")


def random_delay(min_sec: float = 1.0, max_sec: float = 3.0):
    """Humanized random sleep interval."""
    time.sleep(random.uniform(min_sec, max_sec))


def check_session_file():
    if not SESSION_FILE.exists():
        print(f"[✗] '{SESSION_FILE}' not found!")
        print("    Please run the login script first:")
        print("    python login_and_save_session.py\n")
        sys.exit(1)


def launch_authenticated_browser(headless: bool = False):
    """Launch CloakBrowser initialized with saved storage_state."""
    check_session_file()
    print(f"[*] Loading authenticated session from {SESSION_FILE}...")

    context = cloakbrowser.launch_context(
        headless=headless,
        storage_state=str(SESSION_FILE),
        viewport={"width": 1280, "height": 900},
        humanize=True,
        args=[
            "--disable-blink-features=AutomationControlled",
        ]
    )
    return context


def scrape_and_automate(page, target_url: str = "https://x.com/home", max_tweets: int = 5, click_likes: bool = False):
    """
    Navigates to target URL, scrolls, extracts tweet contents,
    and optionally performs click actions (e.g. like button).
    """
    print(f"[*] Navigating to: {target_url}...")
    page.goto(target_url, wait_until="domcontentloaded")
    random_delay(2.5, 4.0)

    # Verify authentication
    if "login" in page.url:
        print("[!] Warning: Redirected to login page. Session may have expired.")
        return []

    print("[✓] Session authenticated! Loaded feed successfully.")

    tweets_data = []
    scraped_ids = set()

    print(f"[*] Scanning feed for up to {max_tweets} tweets...")

    # Wait for the timeline container
    try:
        page.wait_for_selector('article[data-testid="tweet"]', timeout=12000)
    except Exception:
        print("[!] Timeout waiting for tweets to render. Page might still be loading.")

    scroll_attempts = 0
    while len(tweets_data) < max_tweets and scroll_attempts < 10:
        articles = page.query_selector_all('article[data-testid="tweet"]')

        for article in articles:
            if len(tweets_data) >= max_tweets:
                break

            try:
                # Extract text
                text_elem = article.query_selector('div[data-testid="tweetText"]')
                text_content = text_elem.inner_text().strip() if text_elem else ""

                # Extract author handle / name
                user_elem = article.query_selector('div[data-testid="User-Name"]')
                user_info = user_elem.inner_text().replace("\n", " | ") if user_elem else "Unknown"

                # Unique key for deduplication
                tweet_key = (user_info, text_content[:50])
                if tweet_key in scraped_ids or not text_content:
                    continue

                scraped_ids.add(tweet_key)
                tweet_record = {
                    "id": len(tweets_data) + 1,
                    "author": user_info,
                    "text": text_content,
                    "scraped_at": time.strftime("%Y-%m-%d %H:%M:%S")
                }
                tweets_data.append(tweet_record)
                print(f"\n[Tweet #{tweet_record['id']}] From: {user_info}")
                print(f"  Text: {text_content[:90]}..." if len(text_content) > 90 else f"  Text: {text_content}")

                # Optional: Automated Click Action (e.g. Like)
                if click_likes:
                    like_btn = article.query_selector('button[data-testid="like"]')
                    if like_btn:
                        print("  -> Automating click on Like button...")
                        random_delay(0.5, 1.2)
                        like_btn.scroll_into_view_if_needed()
                        like_btn.click()
                        random_delay(1.0, 2.0)

            except Exception as e:
                continue

        # Smooth humanized scroll
        page.mouse.wheel(0, random.randint(400, 700))
        random_delay(1.5, 3.0)
        scroll_attempts += 1

    return tweets_data


def main():
    print("=" * 60)
    print("       CloakBrowser - Twitter Automation & Scraper")
    print("=" * 60)

    # Launch browser (set headless=True for background running, False for visual observation)
    context = launch_authenticated_browser(headless=False)

    try:
        page = context.new_page()
        # Automate on home timeline or change to any profile or search URL
        tweets = scrape_and_automate(page, target_url="https://x.com/home", max_tweets=5, click_likes=False)

        # Save scraped results
        output_file = Path("scraped_tweets.json")
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(tweets, f, indent=2, ensure_ascii=False)

        print("\n" + "=" * 60)
        print(f"[✓] Scraped {len(tweets)} tweets. Saved to {output_file}")
        print("=" * 60)

        # Keep browser open briefly so user can see result
        random_delay(2.0, 4.0)

    finally:
        context.close()
        print("[*] Browser closed cleanly.")


if __name__ == "__main__":
    main()
