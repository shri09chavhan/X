import logging
import random
import time
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Set, Optional
from .browser_handler import BrowserHandler
from .dom_extractor import DOMExtractor

logger = logging.getLogger("twitter_scraper.orchestrator")

class ScraperOrchestrator:
    def __init__(self, session_file: Path, config_path: Path):
        self.browser = BrowserHandler(session_file)
        self.extractor = DOMExtractor(config_path)
        self.selectors = self.extractor.selectors

    def _random_delay(self, min_sec: float = 1.0, max_sec: float = 2.5):
        time.sleep(random.uniform(min_sec, max_sec))

    def _open_search_results(self, page, query: str, select_latest: bool = True) -> bool:
        logger.info(f"Navigating to X search for: {query}")
        encoded_query = urllib.parse.quote(query)
        url = f"https://x.com/search?q={encoded_query}"
        if select_latest: url += "&f=live"
        
        page.goto(url, wait_until="domcontentloaded")
        try:
            page.wait_for_selector(self.selectors['post_container'], timeout=15000)
            return True
        except Exception as e:
            logger.warning(f"Timeout waiting for results: {e}")
            return False

    def scrape(self, query: str, limit: int = 5, headless: bool = False) -> List[Dict[str, Any]]:
        context = self.browser.launch(headless=headless)
        collected_posts: List[Dict[str, Any]] = []
        seen_ids: Set[str] = set()
        
        try:
            page = context.new_page()
            if not self._open_search_results(page, query):
                return []

            consecutive_empty = 0
            while len(collected_posts) < limit and consecutive_empty < 4:
                articles = page.query_selector_all(self.selectors['post_container'])
                new_found = 0
                for article in articles:
                    if len(collected_posts) >= limit: break
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
                
                page.mouse.wheel(0, random.randint(700, 1100))
                self._random_delay(1.5, 2.5)

        finally:
            self.browser.close()
        
        return collected_posts
