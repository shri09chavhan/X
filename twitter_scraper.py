#!/usr/bin/env python3
"""
X (formerly Twitter) Search Scraper & Automation using CloakBrowser.

Reuses authenticated session from session.json, inputs search query into X search box,
navigates to the Latest tab, extracts post details (post_id, text, author, metrics, etc.),
and scrolls with deduplication and incremental persistence.
"""

import argparse
import json
import logging
import random
import re
import sys
import time
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

# Enable cloakbrowser and scraper logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("twitter_scraper")

SESSION_FILE = Path("session.json")
DEFAULT_OUTPUT_FILE = Path("scraped_tweets.json")

# Verified DOM Selectors
SELECTOR_SEARCH_INPUT_LABEL = '[data-testid="SearchBox_Search_Input_label"]'
SELECTOR_SEARCH_INPUT = '[data-testid="SearchBox_Search_Input_label"] input, input[data-testid="SearchBox_Search_Input"]'
SELECTOR_POST_CONTAINER = 'article[data-testid="tweet"]'
SELECTOR_POST_TEXT = '[data-testid="tweetText"]'
SELECTOR_USER_NAME = '[data-testid="User-Name"]'
SELECTOR_REPLY = '[data-testid="reply"]'
SELECTOR_REPOST = '[data-testid="retweet"]'
SELECTOR_LIKE = '[data-testid="like"]'
SELECTOR_UNLIKE = '[data-testid="unlike"]'
SELECTOR_TEXT_TRANSITION = '[data-testid="app-text-transition-container"]'


def random_delay(min_sec: float = 1.0, max_sec: float = 2.5) -> None:
    """Humanized random delay interval."""
    time.sleep(random.uniform(min_sec, max_sec))


def check_session_file() -> None:
    """Ensure session.json exists with valid auth tokens."""
    if not SESSION_FILE.exists():
        logger.error(f"'{SESSION_FILE}' not found! Run 'python login_and_save_session.py' first.")
        sys.exit(1)


def launch_authenticated_browser(headless: bool = False):
    """Launch CloakBrowser initialized with saved storage_state."""
    check_session_file()
    try:
        import cloakbrowser
    except ImportError:
        logger.error("cloakbrowser is not installed in the active environment.")
        sys.exit(1)

    logger.info(f"Loading authenticated session from {SESSION_FILE} (headless={headless})...")
    context = cloakbrowser.launch_context(
        headless=headless,
        storage_state=str(SESSION_FILE),
        viewport=None,
        humanize=True,
        args=[
            "--start-maximized",
            "--disable-blink-features=AutomationControlled",
        ],
    )
    return context


def parse_metric_count(element, metric_name: str) -> Optional[int | str]:
    """
    Extract metric counts (reply, repost, like, view) from button elements,
    inner text transition containers, or aria-labels without fabricating values.
    Returns None if absent or unextractable.
    """
    if not element:
        return None

    try:
        # 1. Try text transition container
        ttc = element.query_selector(SELECTOR_TEXT_TRANSITION)
        if ttc:
            val = ttc.inner_text().strip()
            if val:
                return int(val) if val.isdigit() else val

        # 2. Try direct inner text
        btn_text = element.inner_text().strip()
        if btn_text:
            if btn_text.isdigit():
                return int(btn_text)
            if any(char.isdigit() for char in btn_text):
                return btn_text

        # 3. Try aria-label inspection
        aria = element.get_attribute("aria-label")
        if aria:
            # Pattern like "14 replies", "2 reposts", "102 likes", "1.5K views"
            pattern = rf"([\d,\.]+[KkMmBb]?)\s+(?:{metric_name})"
            match = re.search(pattern, aria, re.IGNORECASE)
            if match:
                raw_count = match.group(1).replace(",", "")
                return int(raw_count) if raw_count.isdigit() else raw_count

            # If aria-label is just "Reply" or "Like", count is 0
            single_terms = [m.rstrip("s") for m in metric_name.split("|")]
            if aria.strip().lower() in single_terms or aria.strip().lower() in [f"{s}s" for s in single_terms]:
                return 0
    except Exception as e:
        logger.debug(f"Error parsing metric {metric_name}: {e}")

    return None


def extract_post_data(article) -> Dict[str, Any]:
    """
    Extract post fields from a single article[data-testid="tweet"] element.
    Returns structured dictionary matching the required schema. Missing fields are None.
    """
    # 1. Post text
    text: Optional[str] = None
    try:
        text_elem = article.query_selector(SELECTOR_POST_TEXT)
        if text_elem:
            text = text_elem.inner_text().strip()
    except Exception as e:
        logger.debug(f"Failed to extract tweetText: {e}")

    # 2. User info (author_name & author_handle)
    author_name: Optional[str] = None
    author_handle: Optional[str] = None
    try:
        user_elem = article.query_selector(SELECTOR_USER_NAME)
        if user_elem:
            user_text = user_elem.inner_text().strip()
            lines = [l.strip() for l in user_text.split("\n") if l.strip()]
            for idx, line in enumerate(lines):
                if line.startswith("@"):
                    author_handle = line
                    if idx > 0 and not author_name:
                        author_name = lines[idx - 1]
                    break
            if not author_name and lines:
                author_name = lines[0]
    except Exception as e:
        logger.debug(f"Failed to extract User-Name: {e}")

    # 3. Post URL, Post ID, and Creation Time
    created_at: Optional[str] = None
    post_url: Optional[str] = None
    post_id: Optional[str] = None
    try:
        time_elem = article.query_selector("time")
        if time_elem:
            created_at = time_elem.get_attribute("datetime")
            try:
                # Find enclosing anchor link
                anchor_href = time_elem.evaluate("el => el.closest('a')?.href")
                if anchor_href and "/status/" in anchor_href:
                    post_url = anchor_href
            except Exception:
                pass

        if not post_url:
            status_links = article.query_selector_all('a[href*="/status/"]')
            for link in status_links:
                href = link.get_attribute("href")
                if href and "/status/" in href and not any(x in href for x in ("/analytics", "/photo/", "/video/")):
                    post_url = href if href.startswith("http") else f"https://x.com{href}"
                    break

        if post_url:
            match = re.search(r"/status/(\d+)", post_url)
            if match:
                post_id = match.group(1)
    except Exception as e:
        logger.debug(f"Failed to extract post url/id/time: {e}")

    # 4. Interaction Metrics (reply, repost, like, view)
    reply_elem = article.query_selector(SELECTOR_REPLY)
    reply_count = parse_metric_count(reply_elem, "repl(?:y|ies)")

    repost_elem = article.query_selector(SELECTOR_REPOST)
    repost_count = parse_metric_count(repost_elem, "repost(?:s)?|retweet(?:s)?")

    like_elem = article.query_selector(SELECTOR_LIKE) or article.query_selector(SELECTOR_UNLIKE)
    like_count = parse_metric_count(like_elem, "like(?:s)?")

    # View count (analytics link or views aria-label)
    view_count: Optional[int | str] = None
    try:
        analytics_elem = article.query_selector('a[href*="/analytics"]') or article.query_selector(
            '[aria-label*="view" i]'
        )
        if analytics_elem:
            view_count = parse_metric_count(analytics_elem, "view(?:s)?")
    except Exception as e:
        logger.debug(f"Failed to extract view count: {e}")

    return {
        "post_id": post_id,
        "post_url": post_url,
        "author_name": author_name,
        "author_handle": author_handle,
        "text": text,
        "created_at": created_at,
        "reply_count": reply_count,
        "repost_count": repost_count,
        "like_count": like_count,
        "view_count": view_count,
    }


def open_search_results(page, query: str, select_latest: bool = True) -> bool:
    """
    Enters query into X search box, submits with Enter, waits for results,
    and switches to the Latest tab if configured.
    """
    logger.info(f"Navigating to X explore page to access search box...")
    page.goto("https://x.com/explore", wait_until="domcontentloaded")
    random_delay(1.5, 2.5)

    # Check for login redirection
    if "login" in page.url:
        logger.error("Redirected to login. Session might be invalid or expired.")
        return False

    search_input = None
    try:
        page.wait_for_selector(SELECTOR_SEARCH_INPUT, timeout=8000)
        search_input = page.locator(SELECTOR_SEARCH_INPUT).first
    except Exception:
        logger.warning(f"Search input selector not immediately found on /explore. Trying search box label...")
        try:
            page.wait_for_selector(SELECTOR_SEARCH_INPUT_LABEL, timeout=5000)
            search_input = page.locator(f"{SELECTOR_SEARCH_INPUT_LABEL} input").first
        except Exception:
            pass

    if search_input and search_input.is_visible():
        logger.info(f"Found search box. Entering query: '{query}'...")
        search_input.click()
        random_delay(0.3, 0.7)
        search_input.fill(query)
        random_delay(0.5, 1.0)
        logger.info("Submitting search query...")
        search_input.press("Enter")
    else:
        # Fallback to direct search URL
        logger.info("Directly opening search URL as fallback...")
        encoded_query = urllib.parse.quote(query)
        direct_url = f"https://x.com/search?q={encoded_query}&f=live" if select_latest else f"https://x.com/search?q={encoded_query}"
        page.goto(direct_url, wait_until="domcontentloaded")

    # Wait for search results container
    try:
        logger.info("Waiting for search results to load...")
        page.wait_for_selector(SELECTOR_POST_CONTAINER, timeout=15000)
        logger.info("Search results loaded successfully.")
    except Exception as e:
        logger.warning(f"Timed out waiting for initial posts: {e}")

    # Switch to "Latest" tab if requested and not already on it
    if select_latest and "f=live" not in page.url:
        logger.info("Selecting 'Latest' tab...")
        try:
            latest_tab = page.locator('a[role="tab"][href*="f=live"], a[role="tab"]:has-text("Latest")').first
            if latest_tab.is_visible():
                latest_tab.click()
                random_delay(1.5, 2.5)
                page.wait_for_selector(SELECTOR_POST_CONTAINER, timeout=12000)
                logger.info("Successfully switched to Latest tab.")
            else:
                logger.info("Latest tab selector not directly visible, staying on current view.")
        except Exception as e:
            logger.debug(f"Could not switch tab: {e}")

    return True


def save_posts_to_file(filepath: Path, posts: List[Dict[str, Any]]) -> None:
    """Save collected posts to JSON file."""
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(posts, f, indent=2, ensure_ascii=False)
        logger.debug(f"Saved {len(posts)} posts to {filepath}")
    except Exception as e:
        logger.error(f"Failed to save posts to {filepath}: {e}")


def run_search_scraper(
    query: str,
    limit: int = 10,
    max_empty_scrolls: int = 4,
    select_latest: bool = True,
    headless: bool = False,
    output_path: Path = DEFAULT_OUTPUT_FILE,
) -> List[Dict[str, Any]]:
    """
    Main orchestration loop:
    1. Launches authenticated CloakBrowser
    2. Opens search results
    3. Iteratively extracts posts, deduplicates by post_id / URL
    4. Scrolls and waits until limit or consecutive empty scrolls reached
    5. Saves structured output
    """
    logger.info("=" * 65)
    logger.info(f"Starting X Search Scraper: query='{query}', limit={limit}, latest={select_latest}")
    logger.info("=" * 65)

    context = launch_authenticated_browser(headless=headless)
    collected_posts: List[Dict[str, Any]] = []
    seen_ids: Set[str] = set()

    try:
        page = context.new_page()
        success = open_search_results(page, query=query, select_latest=select_latest)
        if not success:
            logger.error("Failed to load search results.")
            return []

        consecutive_empty = 0
        scroll_iteration = 0

        while len(collected_posts) < limit and consecutive_empty < max_empty_scrolls:
            scroll_iteration += 1
            articles = page.query_selector_all(SELECTOR_POST_CONTAINER)
            new_in_iteration = 0

            for article in articles:
                if len(collected_posts) >= limit:
                    break

                post = extract_post_data(article)
                unique_key = post.get("post_id") or post.get("post_url") or (post.get("text")[:50] if post.get("text") else None)

                if not unique_key or unique_key in seen_ids:
                    continue

                seen_ids.add(unique_key)
                collected_posts.append(post)
                new_in_iteration += 1

                logger.info(
                    f"[{len(collected_posts)}/{limit}] Post {post['post_id']} by {post['author_handle'] or 'unknown'}: "
                    f"\"{(post['text'] or '')[:60]}...\" (Likes: {post['like_count']}, Reposts: {post['repost_count']})"
                )

            # Log progress
            if new_in_iteration > 0:
                consecutive_empty = 0
                logger.info(f"Iteration #{scroll_iteration}: Collected {new_in_iteration} new posts (Total: {len(collected_posts)}/{limit}).")
                # Incremental persistence
                save_posts_to_file(output_path, collected_posts)
            else:
                consecutive_empty += 1
                logger.info(f"Iteration #{scroll_iteration}: No new posts found (Unsuccessful attempts: {consecutive_empty}/{max_empty_scrolls}).")

            if len(collected_posts) >= limit:
                logger.info(f"Target limit of {limit} posts reached!")
                break

            # Scroll down to load more results
            scroll_distance = random.randint(700, 1100)
            page.mouse.wheel(0, scroll_distance)
            random_delay(1.5, 2.8)

    except KeyboardInterrupt:
        logger.info("Scraping interrupted by user. Saving collected records...")
    except Exception as e:
        logger.error(f"Unexpected error during scraping: {e}", exc_info=True)
    finally:
        save_posts_to_file(output_path, collected_posts)
        context.close()
        logger.info(f"Finished scraping. Total unique posts collected: {len(collected_posts)}. Output: {output_path}")

    return collected_posts


def main():
    parser = argparse.ArgumentParser(description="X (Twitter) Search Scraper using CloakBrowser")
    parser.add_argument("-q", "--query", type=str, default="Python", help="Search query (default: 'Python')")
    parser.add_argument("-l", "--limit", type=int, default=5, help="Number of posts to collect (default: 5)")
    parser.add_argument("--tab", choices=["latest", "top"], default="latest", help="Search tab (default: latest)")
    parser.add_argument("--headless", action="store_true", help="Run browser in headless mode")
    parser.add_argument("-o", "--output", type=str, default="scraped_tweets.json", help="Output JSON path")
    parser.add_argument("--max-empty-scrolls", type=int, default=4, help="Stop after N consecutive scrolls with no new posts")

    args = parser.parse_args()

    run_search_scraper(
        query=args.query,
        limit=args.limit,
        max_empty_scrolls=args.max_empty_scrolls,
        select_latest=(args.tab == "latest"),
        headless=args.headless,
        output_path=Path(args.output),
    )


if __name__ == "__main__":
    main()
