"""
Orchestration module.
Manages the main scraping workflow using pure in-browser GraphQL network interception.
Eliminates DOM extraction overhead completely and implements adaptive scroll retrying.
Maintains a persistent browser session and captures granular performance & resource benchmarks.
"""

import logging
import random
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from urllib.parse import quote

import yaml

from .browser_handler import BrowserHandler
from .network_extractor import GraphQLExtractor
from .utils.monitor import get_process_metrics

logger = logging.getLogger("twitter_scraper.orchestrator")


class ScraperOrchestrator:
    """
    High-performance scraping orchestrator powered purely by GraphQL network interception.
    Eliminates all DOM parsing overhead, delivering O(1) constant-time extraction.
    """

    def __init__(self, session_file: Path, config_path: Path):
        self.browser = BrowserHandler(session_file)
        self.network_extractor = GraphQLExtractor()
        
        # Load initial container selector for page-load readiness check
        with open(config_path, "r", encoding="utf-8") as f:
            self.selectors = yaml.safe_load(f)["selectors"]

        self.context = None
        self.page = None
        self.last_benchmark: Dict[str, Any] = {}

    def start(self, headless: bool = False) -> None:
        """Launches the persistent browser session and binds the GraphQL interceptor."""
        self.context = self.browser.launch(headless=headless)
        self.page = self.context.new_page()
        self.network_extractor.attach_to_page(self.page)

    def stop(self) -> None:
        """Terminates the browser session."""
        self.browser.close()

    def _open_search_results(self, query: str, select_latest: bool = True) -> bool:
        """Navigates to search page and waits for initial container readiness with retry recovery."""
        logger.info(f"Navigating to X search for: {query}")
        url = f"https://x.com/search?q={quote(query)}"
        if select_latest:
            url += "&f=live"

        try:
            self.page.goto(url, wait_until="domcontentloaded")
        except Exception as e:
            logger.error(f"Navigation to {url} failed: {e}")
            return False

        # Wait up to 20s, actively checking for intercepted posts, DOM articles, or Retry prompts
        deadline = time.perf_counter() + 20.0
        retry_clicked = False

        while time.perf_counter() < deadline:
            # 1. Success condition A: GraphQL interceptor already captured initial posts
            if self.network_extractor._captured_posts:
                return True

            # 2. Success condition B: DOM article container is present
            try:
                if self.page.query_selector(self.selectors["post_container"]):
                    return True
            except Exception:
                pass

            # 3. Recovery condition: X displayed a transient error boundary with a "Retry" button
            try:
                retry_btn = self.page.query_selector('button:has-text("Retry"), [role="button"]:has-text("Retry")')
                if retry_btn and retry_btn.is_visible() and not retry_clicked:
                    logger.warning("Detected X 'Retry' prompt. Clicking Retry button to recover...")
                    retry_btn.click()
                    retry_clicked = True
                    time.sleep(2.0)
                    continue
            except Exception:
                pass

            time.sleep(0.4)

        # Final check if posts arrived
        if self.network_extractor._captured_posts:
            return True

        logger.warning(f"Timeout waiting for search results on '{query}' (20s exceeded).")
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
        Scrapes data purely via GraphQL network interception with adaptive scroll retries.
        Zero DOM extraction overhead.
        """
        if not self.page:
            raise RuntimeError("Browser not started. Call .start() first.")

        # Clear benchmark to avoid reporting stale metrics if navigation fails
        self.last_benchmark = {}

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

        # Ensure initial GraphQL response is captured before entering scrolling loop
        self.network_extractor.wait_for_new_posts(timeout_sec=2.0)

        # 2. Pure GraphQL Interception & Adaptive Scrolling Loop
        json_processing_time = 0.0
        scroll_waiting_time = 0.0
        scroll_count = 0
        consecutive_empty = 0

        while (
            len(collected_posts) < limit
            and consecutive_empty < max_empty_scrolls
            and scroll_count < max_scrolls
        ):
            # Pure in-memory JSON parsing (takes ~0.001s, zero DOM calls)
            ext_start = time.perf_counter()
            needed = limit - len(collected_posts)
            intercepted_posts = self.network_extractor.get_new_posts(needed)
            new_found = 0

            for post in intercepted_posts:
                uid = post["post_id"]
                if uid not in seen_ids:
                    seen_ids.add(uid)
                    collected_posts.append(post)
                    new_found += 1

            json_processing_time += time.perf_counter() - ext_start

            if new_found > 0:
                consecutive_empty = 0
            else:
                consecutive_empty += 1
                logger.debug(
                    f"No new posts in network packet (retry {consecutive_empty}/{max_empty_scrolls})."
                )

            # Check stopping conditions
            if (
                len(collected_posts) >= limit
                or consecutive_empty >= max_empty_scrolls
                or scroll_count >= max_scrolls
            ):
                break

            # Adaptive scroll dispatch & network packet wait
            wait_start = time.perf_counter()
            scroll_count += 1

            # In-Page Sentinel Overdrive:
            # 1. Micro-pause to allow React virtual DOM to mount new bottom sentinel
            time.sleep(0.25)

            # 2. Prevent DOM tree bloat and V8 GC stalls by pruning off-screen nodes
            if scroll_count % 5 == 0:
                try:
                    self.page.evaluate("""() => {
                        const articles = document.querySelectorAll('article[data-testid="tweet"]');
                        if (articles.length > 120) {
                            for (let i = 0; i < articles.length - 60; i++) {
                                articles[i].remove();
                            }
                        }
                    }""")
                except Exception:
                    pass

            # 3. Micro-oscillate to trigger React IntersectionObserver exit/entry events
            if consecutive_empty > 0:
                # Deeper bounce if previous attempt was empty
                self.page.evaluate("window.scrollBy(0, -450); window.scrollTo(0, document.body.scrollHeight);")
                self.page.mouse.wheel(0, random.randint(2500, 4000))
            else:
                self.page.evaluate("window.scrollBy(0, -200); window.scrollTo(0, document.body.scrollHeight);")
                self.page.mouse.wheel(0, random.randint(1000, 1800))

            # 4. Pure event-driven network wait: resolves immediately when GraphQL response arrives (150-300ms)
            self.network_extractor.wait_for_new_posts(timeout_sec=2.2)

            scroll_waiting_time += time.perf_counter() - wait_start

        # Drain any remaining intercepted posts if limit not yet reached
        if len(collected_posts) < limit:
            ext_start = time.perf_counter()
            needed = limit - len(collected_posts)
            for post in self.network_extractor.get_new_posts(needed):
                uid = post["post_id"]
                if uid not in seen_ids:
                    seen_ids.add(uid)
                    collected_posts.append(post)
            json_processing_time += time.perf_counter() - ext_start

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
                "json_processing_sec": json_processing_time,
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
