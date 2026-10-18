"""
Browser management module for authenticated web automation.
Follows SRP by isolating browser lifecycle and configuration from business logic.
"""

import logging
from pathlib import Path
from typing import Optional

# Using local import to avoid hard dependency at module load time
try:
    import cloakbrowser
except ImportError:
    cloakbrowser = None

logger = logging.getLogger("twitter_scraper.browser")

class BrowserHandler:
    """
    Handles the lifecycle and configuration of the CloakBrowser instance.
    
    Attributes:
        session_file (Path): Path to the storage state (cookies/auth) JSON file.
        context: The active browser context once launched.
    """

    def __init__(self, session_file: Path):
        """
        Initializes the handler with a session path.
        
        Args:
            session_file (Path): Path to 'session.json' for authentication.
        """
        self.session_file = session_file
        self.context: Optional[object] = None

    def launch(self, headless: bool = False) -> object:
        """
        Launches an authenticated browser context using saved storage state.
        
        Args:
            headless (bool): Whether to run the browser without a GUI.
            
        Returns:
            object: The launched CloakBrowser context.
            
        Raises:
            FileNotFoundError: If the session file is missing.
            ImportError: If cloakbrowser is not installed in the environment.
        """
        if not cloakbrowser:
            logger.error("cloakbrowser package is missing from the environment.")
            raise ImportError("cloakbrowser not installed.")

        if not self.session_file.exists():
            logger.error(f"Authentication session missing at: {self.session_file}")
            raise FileNotFoundError(f"Session file {self.session_file} is required for login.")
        
        logger.info(f"Initializing browser (Headless: {headless}) with session: {self.session_file}")
        
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
            logger.exception("Critial failure during browser launch.")
            raise

    def close(self) -> None:
        """
        Gracefully terminates the browser context and releases resources.
        """
        if self.context:
            self.context.close()
            logger.info("Browser context successfully terminated.")
