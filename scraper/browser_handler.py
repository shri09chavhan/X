"""
Browser management module for authenticated web automation.
Optimized for high-throughput headless execution without humanisation overhead.
"""

import logging
from pathlib import Path
from typing import Optional

try:
    import cloakbrowser
except ImportError:
    cloakbrowser = None

logger = logging.getLogger("twitter_scraper.browser")

class BrowserHandler:
    """
    Handles the lifecycle and configuration of the CloakBrowser instance.
    Configured for headless execution and disabled humanization for maximum speed.
    """

    def __init__(self, session_file: Path):
        self.session_file = session_file
        self.context: Optional[object] = None

    def launch(self, headless: bool = True) -> object:
        """
        Launches an authenticated browser context using saved storage state.
        Default is headless=True and humanize=False for high-performance scraping.
        """
        if not cloakbrowser:
            logger.error("cloakbrowser package is missing from the environment.")
            raise ImportError("cloakbrowser not installed.")

        if not self.session_file.exists():
            logger.error(f"Authentication session missing at: {self.session_file}")
            raise FileNotFoundError(f"Session file {self.session_file} is required for login.")
        
        logger.info(f"Initializing high-performance browser (Headless: {headless}, Humanize: False) with session: {self.session_file}")
        
        try:
            self.context = cloakbrowser.launch_context(
                headless=headless,
                storage_state=str(self.session_file),
                viewport={"width": 1920, "height": 1080},
                humanize=False,  # Disabled for maximum scraping speed (~3x throughput boost)
                args=[
                    "--start-maximized",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-extensions",
                    "--disable-gpu",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                ],
            )
            return self.context
        except Exception as e:
            logger.exception("Critical failure during high-performance browser launch.")
            raise

    def close(self) -> None:
        """Gracefully terminates the browser context and releases resources."""
        if self.context and hasattr(self.context, "close"):
            try:
                self.context.close()
                logger.info("Browser context successfully terminated.")
            except Exception as e:
                logger.debug(f"Error closing browser context: {e}")
