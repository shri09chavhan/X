"""
Orchestration module.
Manages the main scraping workflow, orchestrating the browser and extractor.
"""

import logging
import random
from pathlib import Path
from typing import Any, Dict, List, Set, Optional

from .browser_handler import BrowserHandler
from .dom_extractor import DOMExtractor
from .utils.metrics import timeit

logger = logging.getLogger("twitter_scraper.orchestrator")

class ScraperOrchestrator:
    """
    Orchestrates the scraping process, integrating browser and extractor modules.
    Maintains a persistent browser session for optimized resource usage.
    """

    def __init__(self, session_file: Path, config_path: Path):
        self.browser = BrowserHandler(session_file)
        self.extractor = DOMExtractor(config_path)
        self.selectors = self.extractor.selectors
        self.context = None
        self.page = None

    def start(self, headless: bool = False) -> None:
        """Launches the browser session."""
        self.context = self.browser.launch(headless=headless)
        self.page = self.context.new_page()

    def stop(self) -> None:
        """Terminates the browser session."""
        self.browser.close()

    def _open_search_results(self, query: str, select_latest: bool = True) -> bool:
        """Navigates to search page and waits for results."""
        logger.info(f"Navigating to X search for: {query}")
        # CloakBrowser's humanize=True handles navigation mechanics
        from urllib.parse import quote
        url = f"https://x.com/search?q={quote(query)}"
        if select_latest: 
            url += "&f=live"
        
        self.page.goto(url, wait_until="domcontentloaded")
        try:
            self.page.wait_for_selector(self.selectors['post_container'], timeout=15000)
            return True
        except Exception as e:
            logger.warning(f"Timeout waiting for results: {e}")
            return False

    @timeit
    def scrape(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Scrapes data for a query using the persistent page.
        """
        if not self.page:
            raise RuntimeError("Browser not started. Call .start() first.")

        collected_posts: List[Dict[str, Any]] = []
        seen_ids: Set[str] = set()
        
        if not self._open_search_results(query):
            return []

        consecutive_empty = 0
        while len(collected_posts) < limit and consecutive_empty < 4:
            articles = self.page.query_selector_all(self.selectors['post_container'])
            new_found = 0
            for article in articles:
                if len(collected_posts) >= limit: 
                    break
                
                post = self.extractor.extract_post_data(article)
                uid = post.get("post_id") or post.get("post_url")
                
                if uid and uid not in seen_ids:
                    seen_ids.add(uid)
                    collected_posts.append(post)
                    new_found += 1
            
            if new_found > 0:
                consecutive_empty = 0
            else:
                consecutive_empty += 1
            
            # Scrolling is necessary to trigger X's lazy loading; 
            # CloakBrowser's humanize=True makes this natural.
            self.page.mouse.wheel(0, random.randint(700, 1100))
        
        return collected_posts
