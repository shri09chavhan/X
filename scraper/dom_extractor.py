import re
import logging
import yaml
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger("twitter_scraper.extractor")

class DOMExtractor:
    def __init__(self, config_path: Path):
        with open(config_path, 'r') as f:
            self.selectors = yaml.safe_load(f)['selectors']

    def parse_metric_count(self, element, metric_name: str) -> Optional[int | str]:
        if not element: return None
        try:
            ttc = element.query_selector(self.selectors['text_transition'])
            if ttc:
                val = ttc.inner_text().strip()
                if val: return int(val) if val.isdigit() else val
            btn_text = element.inner_text().strip()
            if btn_text and btn_text.isdigit(): return int(btn_text)
            aria = element.get_attribute("aria-label")
            if aria:
                pattern = rf"([\d,\.]+[KkMmBb]?)\s+(?:{metric_name})"
                match = re.search(pattern, aria, re.IGNORECASE)
                if match:
                    raw_count = match.group(1).replace(",", "")
                    return int(raw_count) if raw_count.isdigit() else raw_count
        except Exception as e:
            logger.debug(f"Error parsing metric {metric_name}: {e}")
        return None

    def extract_post_data(self, article) -> Dict[str, Any]:
        text = None
        try:
            text_elem = article.query_selector(self.selectors['post_text'])
            if text_elem: text = text_elem.inner_text().strip()
        except Exception as e:
            logger.debug(f"Failed to extract tweetText: {e}")

        author_name, author_handle = None, None
        try:
            user_elem = article.query_selector(self.selectors['user_name'])
            if user_elem:
                user_text = user_elem.inner_text().strip()
                lines = [l.strip() for l in user_text.split("\n") if l.strip()]
                for idx, line in enumerate(lines):
                    if line.startswith("@"):
                        author_handle = line
                        if idx > 0 and not author_name: author_name = lines[idx - 1]
                        break
                if not author_name and lines: author_name = lines[0]
        except Exception as e:
            logger.debug(f"Failed to extract User-Name: {e}")

        created_at, post_url, post_id = None, None, None
        try:
            time_elem = article.query_selector("time")
            if time_elem:
                created_at = time_elem.get_attribute("datetime")
                anchor_href = time_elem.evaluate("el => el.closest('a')?.href")
                if anchor_href and "/status/" in anchor_href: post_url = anchor_href
            if not post_url:
                status_links = article.query_selector_all('a[href*="/status/"]')
                for link in status_links:
                    href = link.get_attribute("href")
                    if href and "/status/" in href and not any(x in href for x in ("/analytics", "/photo/", "/video/")):
                        post_url = href if href.startswith("http") else f"https://x.com{href}"
                        break
            if post_url:
                match = re.search(r"/status/(\d+)", post_url)
                if match: post_id = match.group(1)
        except Exception as e:
            logger.debug(f"Failed to extract post url/id/time: {e}")

        reply_count = self.parse_metric_count(article.query_selector(self.selectors['reply']), "repl(?:y|ies)")
        repost_count = self.parse_metric_count(article.query_selector(self.selectors['repost']), "repost(?:s)?|retweet(?:s)?")
        like_count = self.parse_metric_count(article.query_selector(self.selectors['like']) or article.query_selector(self.selectors['unlike']), "like(?:s)?")
        
        view_count = None
        try:
            analytics_elem = article.query_selector(self.selectors['analytics']) or article.query_selector(self.selectors['view_aria'])
            if analytics_elem: view_count = self.parse_metric_count(analytics_elem, "view(?:s)?")
        except Exception as e:
            logger.debug(f"Failed to extract view count: {e}")

        return {
            "post_id": post_id, "post_url": post_url, "author_name": author_name,
            "author_handle": author_handle, "text": text, "created_at": created_at,
            "reply_count": reply_count, "repost_count": repost_count,
            "like_count": like_count, "view_count": view_count
        }
