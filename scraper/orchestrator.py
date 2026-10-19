"""
Orchestration module.
Manages the main scraping workflow, orchestrating the browser, network interceptor,
and fallback DOM extractor.
Maintains a persistent browser session and captures granular performance & resource benchmarks.
"""

import logging
import random
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from urllib.parse import quote

from .browser_handler import BrowserHandler
from .dom_extractor import DOMExtractor
from .network_extractor import GraphQLExtractor
from .utils.monitor import get_process_metrics

logger = logging.getLogger("twitter_scraper.orchestrator")


class ScraperOrchestrator:
    """
    Orchestrates the scraping process using GraphQL network interception with DOM fallback.
    Maintains a persistent browser session for optimized resource usage.
    """

    def __init__(self, session_file: Path, config_path: Path):
        self.browser = BrowserHandler(session_file)
        self.dom_extractor = DOMExtractor(config_path)
        self.selectors = self.dom_extractor.selectors
        self.network_extractor = GraphQLExtractor()
        self.context = None
        self.page = None
        self.last_benchmark: Dict[str, Any] = {}

    def start(self, headless: bool = False) -> None:
        """Launches the persistent browser session and binds network interceptors."""
        self.context = self.browser.launch(headless=headless)
        self.page = self.context.new_page()
        self.network_extractor.attach_to_page(self.page)

    def stop(self) -> None:
        """Terminates the browser session."""
        self.browser.close()

    def _open_search_results(self, query: str, select_latest: bool = True) -> bool:
        """Navigates to search page and waits for initial results container."""
        logger.info(f"Navigating to X search for: {query}")
        url = f"https://x.com/search?q={quote(query)}"
        if select_latest:
            url += "&f=live"

        self.page.goto(url, wait_until="domcontentloaded")
        try:
            self.page.wait_for_selector(self.selectors["post_container"], timeout=15000)
            return True
        except Exception as e:
            logger.warning(f"Timeout waiting for results: {e}")
            return False

    def scrape(
        self,
        query: str,
        limit: int = 5,
        max_scrolls: int = 15,
        max_empty_scrolls: int = 4,
        select_latest: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Scrapes data for a query with configurable limits and captures detailed benchmarks.
        Prioritizes high-speed GraphQL network interception, falling back to DOM extraction.
        """
        if not self.page:
            raise RuntimeError("Browser not started. Call .start() first.")

        start_time = time.perf_counter()
        initial_resources = get_process_metrics()

        collected_posts: List[Dict[str, Any]] = []
        seen_ids: Set[str] = set()

        # Reset interceptor buffers for fresh query
        self.network_extractor.reset()

        # 1. Navigation & Network Latency
        nav_start = time.perf_counter()
        if not self._open_search_results(query, select_latest=select_latest):
            return []
        network_nav_time = time.perf_counter() - nav_start

        # 2. Extraction & Scrolling Loop
        extraction_time = 0.0
        scroll_waiting_time = 0.0
        scroll_count = 0
        consecutive_empty = 0

        while (
            len(collected_posts) < limit
            and consecutive_empty < max_empty_scrolls
            and scroll_count < max_scrolls
        ):
            ext_start = time.perf_counter()
            new_found = 0

            # Priority 1: Pull from intercepted GraphQL network responses
            needed = limit - len(collected_posts)
            intercepted_posts = self.network_extractor.get_new_posts(needed)

            for post in intercepted_posts:
                uid = post["post_id"]
                if uid not in seen_ids:
                    seen_ids.add(uid)
                    collected_posts.append(post)
                    new_found += 1

            # Priority 2: Fallback to DOM extraction if network payload is pending or omitted
            if len(collected_posts) < limit and not intercepted_posts:
                articles = self.page.query_selector_all(self.selectors["post_container"])
                for article in articles:
                    if len(collected_posts) >= limit:
                        break
                    post = self.dom_extractor.extract_post_data(article)
                    uid = post.get("post_id") or post.get("post_url")
                    if uid and uid not in seen_ids:
                        seen_ids.add(uid)
                        collected_posts.append(post)
                        new_found += 1

            extraction_time += time.perf_counter() - ext_start

            if new_found > 0:
                consecutive_empty = 0
            else:
                consecutive_empty += 1

            # Check stopping conditions
            if (
                len(collected_posts) >= limit
                or consecutive_empty >= max_empty_scrolls
                or scroll_count >= max_scrolls
            ):
                break

            # Measure scroll dispatch and lazy-load wait time
            wait_start = time.perf_counter()
            scroll_count += 1

            try:
                current_article_count = len(self.page.query_selector_all(self.selectors["post_container"]))
            except Exception:
                current_article_count = 0

            # Native CloakBrowser big scroll
            self.page.mouse.wheel(0, random.randint(2500, 3800))

            # Smart Wait: resolves when new DOM nodes appear or timeout
            try:
                self.page.wait_for_function(
                    f"() => document.querySelectorAll('{self.selectors['post_container']}').length > {current_article_count}",
                    timeout=2500,
                )
            except Exception:
                pass

            scroll_waiting_time += time.perf_counter() - wait_start

        total_time = time.perf_counter() - start_time
        final_resources = get_process_metrics()

        ppm = (len(collected_posts) / total_time * 60) if total_time > 0 else 0
        sec_per_post = (total_time / len(collected_posts)) if collected_posts else 0

        self.last_benchmark = {
            "query": query,
            "posts_collected": len(collected_posts),
            "limit_target": limit,
            "scrolls_performed": scroll_count,
            "max_scrolls": max_scrolls,
            "time_breakdown": {
                "navigation_network_sec": network_nav_time,
                "dom_extraction_sec": extraction_time,
                "scroll_waiting_sec": scroll_waiting_time,
                "total_duration_sec": total_time,
            },
            "throughput": {
                "ppm": ppm,
                "seconds_per_post": sec_per_post,
            },
            "resources": {
                "cpu_percent": final_resources["cpu_percent"],
                "ram_current_mb": final_resources["rss_mb"],
                "ram_delta_mb": max(0.0, final_resources["rss_mb"] - initial_resources["rss_mb"]),
                "io_read_mb": final_resources["read_mb"],
                "io_write_mb": final_resources["write_mb"],
            },
        }

        return collected_posts
