import logging
import json
from pathlib import Path
from scraper.orchestrator import ScraperOrchestrator
from scraper.trend_provider import TrendProvider

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")
logger = logging.getLogger("main")

def main():
    session_file = Path("session.json")
    config_path = Path("config/selectors.yaml")
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    
    # Initialize components
    orchestrator = ScraperOrchestrator(session_file, config_path)
    trend_provider = TrendProvider()
    
    # Logic: Fetch trends and feed them into the scraper
    trends = trend_provider.get_trends()
    logger.info(f"Retrieved trends: {trends}")
    
    for trend in trends:
        logger.info(f">>> Processing Trend: {trend}")
        posts = orchestrator.scrape(query=trend, limit=3)
        
        # Save results for this trend
        if posts:
            out_file = output_dir / f"{trend}_posts.json"
            with open(out_file, "w") as f:
                json.dump(posts, f, indent=2)
            logger.info(f"Saved {len(posts)} posts to {out_file}")
        else:
            logger.warning(f"No posts collected for trend: {trend}")

if __name__ == "__main__":
    main()
