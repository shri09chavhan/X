import logging
from typing import List

logger = logging.getLogger("twitter_scraper.trend_provider")

class TrendProvider:
    """Provides trending keywords to the scraper."""
    def get_trends(self) -> List[str]:
        # Simple stub: in reality, this would fetch from an API or a database
        logger.info("Fetching trends...")
        return ["Python", "ArtificialIntelligence", "WebScraping"]
