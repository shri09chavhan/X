"""
Trend provider module.
Provides interface for fetching trending keywords.
"""

import logging
from typing import List

logger = logging.getLogger("twitter_scraper.trend_provider")

class TrendProvider:
    """
    Interface for providing trending keywords to the scraper.
    """
    
    def get_trends(self) -> List[str]:
        """
        Fetches a list of trending keywords.
        
        Returns:
            List[str]: A list of trends to be processed.
        """
        # Simple stub: in reality, this would fetch from an API or a database
        logger.info("Fetching trends...")
        return ["Python", "ArtificialIntelligence", "WebScraping"]
