import logging
from pathlib import Path
import sys

# Assume cloakbrowser is installed in the venv
try:
    import cloakbrowser
except ImportError:
    pass

logger = logging.getLogger("twitter_scraper.browser")

class BrowserHandler:
    def __init__(self, session_file: Path):
        self.session_file = session_file
        self.context = None

    def launch(self, headless: bool = False):
        if not self.session_file.exists():
            logger.error(f"Session file not found: {self.session_file}")
            raise FileNotFoundError("Session file missing.")
        
        logger.info(f"Launching authenticated browser (headless={headless})...")
        try:
            self.context = cloakbrowser.launch_context(
                headless=headless,
                storage_state=str(self.session_file),
                viewport=None,
                humanize=True,
                args=[
                    "--start-maximized",
                    "--disable-blink-features=AutomationControlled",
                ],
            )
            return self.context
        except Exception as e:
            logger.error(f"Failed to launch browser: {e}")
            raise

    def close(self):
        if self.context:
            self.context.close()
            logger.info("Browser context closed.")
