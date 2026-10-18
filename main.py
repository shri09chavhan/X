"""
Main entry point for X automation.
Orchestrates trend scraping with performance monitoring and Rich UI.
"""

import logging
import json
from pathlib import Path
from rich.console import Console
from rich.logging import RichHandler
from rich.table import Table

from scraper.orchestrator import ScraperOrchestrator
from scraper.trend_provider import TrendProvider
from scraper.utils.monitor import get_process_metrics

# Setup Rich Console and Logging
console = Console()
logging.basicConfig(
    level="INFO",
    format="%(message)s",
    handlers=[RichHandler(console=console, rich_tracebacks=True)]
)
logger = logging.getLogger("main")

def print_metrics_table(metrics: dict):
    table = Table(title="Resource Metrics", title_style="bold green")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="magenta")
    
    table.add_row("CPU Usage", f"{metrics['cpu_percent']}%")
    table.add_row("RAM Usage", f"{metrics['rss_mb']:.2f} MB")
    table.add_row("IO Read", f"{metrics['read_mb']:.2f} MB")
    table.add_row("IO Write", f"{metrics['write_mb']:.2f} MB")
    
    console.print(table)

def main():
    session_file = Path("session.json")
    config_path = Path("config/selectors.yaml")
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    
    console.print("[bold green]Initializing X Automation System...[/bold green]")
    
    # Initialize components
    orchestrator = ScraperOrchestrator(session_file, config_path)
    trend_provider = TrendProvider()
    
    trends = trend_provider.get_trends()
    logger.info(f"Retrieved trends: [bold yellow]{trends}[/bold yellow]")
    
    # Start persistent browser session (headless=False for prototyping)
    orchestrator.start(headless=False)
    
    try:
        for trend in trends:
            logger.info(f">>> Processing Trend: [bold blue]{trend}[/bold blue]")
            
            posts = orchestrator.scrape(query=trend, limit=3)
            
            # Print Resource Metrics
            metrics = get_process_metrics()
            print_metrics_table(metrics)
            
            # Save results for this trend
            if posts:
                out_file = output_dir / f"{trend}_posts.json"
                with open(out_file, "w") as f:
                    json.dump(posts, f, indent=2)
                logger.info(f"Saved [bold magenta]{len(posts)}[/bold magenta] posts to {out_file}")
            else:
                logger.warning(f"No posts collected for trend: [bold red]{trend}[/bold red]")
    finally:
        orchestrator.stop()
        console.print("[bold green]Automation finished.[/bold green]")

if __name__ == "__main__":
    main()
