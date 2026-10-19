"""
GraphQL network response extractor for X (Twitter).
Intercepts SearchTimeline GraphQL responses directly from Chromium's network stream,
bypassing DOM rendering and selector parsing overhead.
"""

import json
import logging
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger("twitter_scraper.network_extractor")


class GraphQLExtractor:
    """
    Listens to incoming browser network responses, extracts structured post data
    from 'SearchTimeline' GraphQL endpoints, and blocks unnecessary media assets.
    """

    def __init__(self):
        self._page = None
        self._captured_posts: List[Dict[str, Any]] = []
        self._seen_ids: Set[str] = set()

    def attach_to_page(self, page) -> None:
        """
        Binds the network listener and route filters to a Playwright page instance.
        """
        self._page = page
        self._page.on("response", self._handle_network_response)
        self._setup_media_asset_blocking()
        logger.info("GraphQL network extractor successfully attached to page.")

    def _setup_media_asset_blocking(self) -> None:
        """
        Aborts requests for images, fonts, and video files to reduce network usage
        and eliminate rendering lag.
        """
        media_pattern = "**/*.{png,jpg,jpeg,gif,svg,webp,woff,woff2,ttf,otf,mp4,webm}"
        try:
            self._page.route(media_pattern, lambda route: route.abort())
            logger.debug("Media asset blocking route registered.")
        except Exception as err:
            logger.debug(f"Media blocking registration skipped or failed: {err}")

    def _handle_network_response(self, response) -> None:
        """
        Evaluates incoming responses and extracts tweet data from SearchTimeline calls.
        """
        url = response.url
        if "SearchTimeline" not in url:
            return

        try:
            content_type = response.headers.get("content-type", "")
            if "application/json" not in content_type:
                return

            payload = response.json()
            extracted_batch = self._extract_posts_from_timeline_payload(payload)

            new_count = 0
            for post in extracted_batch:
                post_id = post["post_id"]
                if post_id not in self._seen_ids:
                    self._seen_ids.add(post_id)
                    self._captured_posts.append(post)
                    new_count += 1

            if new_count > 0:
                logger.info(f"Intercepted {new_count} posts from SearchTimeline GraphQL response.")

        except Exception as err:
            logger.debug(f"Failed to process SearchTimeline response from {url}: {err}")

    def _extract_posts_from_timeline_payload(self, payload: dict) -> List[Dict[str, Any]]:
        """
        Traverses the SearchTimeline GraphQL response AST and returns parsed tweet models.
        """
        results: List[Dict[str, Any]] = []

        try:
            instructions = (
                payload.get("data", {})
                .get("search_by_raw_query", {})
                .get("search_timeline", {})
                .get("timeline", {})
                .get("instructions", [])
            )

            for instruction in instructions:
                inst_type = instruction.get("type", "")

                # Standard timeline entries
                if inst_type == "TimelineAddEntries":
                    entries = instruction.get("entries", [])
                    for entry in entries:
                        post = self._parse_timeline_entry(entry)
                        if post:
                            results.append(post)

                # Nested module entries
                elif inst_type == "TimelineAddToModule":
                    module_items = instruction.get("moduleItems", [])
                    for item in module_items:
                        post = self._parse_timeline_entry(item)
                        if post:
                            results.append(post)

        except Exception as err:
            logger.debug(f"Error parsing timeline AST instructions: {err}")

        # Fallback defensive deep scan if top-level instructions were modified by X
        if not results:
            results = self._fallback_deep_scan(payload)

        return results

    def _parse_timeline_entry(self, entry: dict) -> Optional[Dict[str, Any]]:
        """
        Extracts tweet information from a single timeline entry object.
        """
        content = entry.get("content", {})
        item_content = content.get("itemContent") or entry.get("itemContent", {})
        tweet_results = item_content.get("tweet_results", {})
        raw_result = tweet_results.get("result")

        if not raw_result:
            return None

        return self._normalize_tweet_result(raw_result)

    def _normalize_tweet_result(self, raw_result: dict) -> Optional[Dict[str, Any]]:
        """
        Converts a raw tweet result object (Tweet or TweetWithVisibilityResults)
        into a standardized post dictionary.
        """
        # Unwrap TweetWithVisibilityResults wrapper if present
        tweet_data = raw_result.get("tweet", raw_result)
        typename = tweet_data.get("__typename", "")

        # Skip deleted or unavailable tweets
        if typename == "TweetTombstone":
            return None

        tweet_id = tweet_data.get("rest_id") or tweet_data.get("id_str")
        if not tweet_id:
            return None

        legacy = tweet_data.get("legacy", {})

        # Extract author details
        user_result = (
            tweet_data.get("core", {})
            .get("user_results", {})
            .get("result", {})
        )
        user_legacy = user_result.get("legacy", {})

        author_name = user_legacy.get("name") or user_result.get("core", {}).get("name") or "Unknown"
        author_handle_raw = user_legacy.get("screen_name") or user_result.get("core", {}).get("screen_name") or "unknown"
        author_handle = f"@{author_handle_raw}" if not author_handle_raw.startswith("@") else author_handle_raw

        # Post text (always untruncated full_text)
        text = legacy.get("full_text") or tweet_data.get("full_text") or ""

        # Timestamps
        created_at = legacy.get("created_at") or tweet_data.get("created_at")

        # Interaction metrics
        reply_count = legacy.get("reply_count", 0)
        repost_count = legacy.get("retweet_count", 0)
        like_count = legacy.get("favorite_count", 0)

        # View count
        view_count_raw = tweet_data.get("views", {}).get("count")
        view_count = int(view_count_raw) if view_count_raw and str(view_count_raw).isdigit() else view_count_raw

        post_url = f"https://x.com/{author_handle_raw}/status/{tweet_id}"

        return {
            "post_id": str(tweet_id),
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

    def _fallback_deep_scan(self, payload: dict) -> List[Dict[str, Any]]:
        """
        Deep traversal fallback that detects tweet structures if X modifies instruction schemas.
        """
        found_posts: List[Dict[str, Any]] = []

        def search_dict(node: Any):
            if isinstance(node, dict):
                if "legacy" in node and ("full_text" in node["legacy"] or "id_str" in node["legacy"]):
                    post = self._normalize_tweet_result(node)
                    if post and post["post_id"] not in self._seen_ids:
                        found_posts.append(post)
                else:
                    for val in node.values():
                        search_dict(val)
            elif isinstance(node, list):
                for item in node:
                    search_dict(item)

        search_dict(payload)
        return found_posts

    def get_new_posts(self, limit: int) -> List[Dict[str, Any]]:
        """
        Pulls newly captured posts up to the requested limit.
        """
        if not self._captured_posts:
            return []

        pulled = self._captured_posts[:limit]
        self._captured_posts = self._captured_posts[limit:]
        return pulled

    def wait_for_new_posts(self, timeout_sec: float = 1.8, min_posts: int = 1) -> bool:
        """
        Polls with micro-intervals (25ms) until new GraphQL posts arrive or timeout expires.
        Resolves within ~150-300ms the millisecond network response packets are parsed.
        """
        import time
        deadline = time.perf_counter() + timeout_sec
        while time.perf_counter() < deadline:
            if len(self._captured_posts) >= min_posts:
                return True
            time.sleep(0.025)
        return len(self._captured_posts) >= min_posts

    def get_total_captured_count(self) -> int:
        """Returns the number of unique posts captured so far."""
        return len(self._seen_ids)

    def reset(self) -> None:
        """
        Resets buffers between query runs.
        """
        self._captured_posts.clear()
        self._seen_ids.clear()
