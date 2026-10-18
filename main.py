"""
Main entry point for X automation.
Orchestrates trend scraping with performance monitoring and Rich UI.
"""

import json
import logging
import time
from pathlib import Path
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.table import Table

from scraper.orchestrator import ScraperOrchestrator
from scraper.trend_provider import TrendProvider
from scraper.utils.monitor import get_process_metrics

# Setup Rich Console
console = Console()

# Suppress noisy HTTP client logs from cloakbrowser and httpx that clutter the terminal
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

# Configure clean, unified logging with RichHandler
logging.basicConfig(
    level="INFO",
    format="%(message)s",
    datefmt="[%X]",
    handlers=[
        RichHandler(
            console=console,
            rich_tracebacks=True,
            markup=True,        # Enables Rich markup formatting ([bold yellow], etc.)
            show_path=False,     # Prevents right-margin overflow and broken line wraps
            show_time=True,
        )
    ]
)
logger = logging.getLogger("main")


def print_summary_table(summary_records: list, final_metrics: dict):
    """Prints a clean, comprehensive summary table at the end of the run."""
    table = Table(
        title="[bold green]Execution & Performance Summary[/bold green]",
        title_style="bold green",
        header_style="bold cyan",
        border_style="bright_blue",
    )
    table.add_column("Trend", style="bold cyan", no_wrap=True)
    table.add_column("Posts", justify="right", style="bold green")
    table.add_column("Duration", justify="right", style="yellow")
    table.add_column("Speed (PPM)", justify="right", style="blue")
    table.add_column("Output File", style="dim")

    total_posts = 0
    total_time = 0.0

    for rec in summary_records:
        table.add_row(
            rec["trend"],
            str(rec["posts"]),
            f"{rec['duration']:.2f}s",
            f"{rec['ppm']:.1f}",
            rec["file"]
        )
        total_posts += rec["posts"]
        total_time += rec["duration"]

    overall_ppm = (total_posts / total_time * 60) if total_time > 0 else 0
    table.add_section()
    table.add_row(
        "[bold]TOTAL[/bold]",
        f"[bold]{total_posts}[/bold]",
        f"[bold]{total_time:.2f}s[/bold]",
        f"[bold]{overall_ppm:.1f}[/bold]",
        "[dim]output/*.json[/dim]"
    )
    console.print()
    console.print(table)

    # Resource Metrics Panel
    resource_table = Table(
        title="[bold magenta]Final Resource Utilization[/bold magenta]",
        header_style="bold magenta",
        border_style="dim",
    )
    resource_table.add_column("CPU Usage", justify="center", style="cyan")
    resource_table.add_column("Memory (RSS)", justify="center", style="green")
    resource_table.add_column("Disk I/O Read", justify="center", style="yellow")
    resource_table.add_column("Disk I/O Write", justify="center", style="blue")

    resource_table.add_row(
        f"{final_metrics['cpu_percent']}%",
        f"{final_metrics['rss_mb']:.2f} MB",
        f"{final_metrics['read_mb']:.2f} MB",
        f"{final_metrics['write_mb']:.2f} MB"
    )
    console.print(resource_table)
    console.print()


def main():
    session_file = Path("session.json")
    config_path = Path("config/selectors.yaml")
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)

    console.print()
    console.print(
        Panel.fit(
            "[bold cyan]X (Twitter) Automation & Scraping Engine[/bold cyan]\n"
            "[dim]Authenticated CloakBrowser Session Active[/dim]",
            border_style="cyan"
        )
    )

    # Initialize components
    orchestrator = ScraperOrchestrator(session_file, config_path)
    trend_provider = TrendProvider()

    trends = trend_provider.get_trends()
    logger.info(f"Retrieved trends: [bold yellow]{trends}[/bold yellow]")

    # Start persistent browser session
    orchestrator.start(headless=False)

    summary_records = []

    try:
        for trend in trends:
            logger.info(f">>> Processing Trend: [bold blue]{trend}[/bold blue]")

            start_t = time.perf_counter()
            posts = orchestrator.scrape(query=trend, limit=3)
            elapsed = time.perf_counter() - start_t

            ppm = (len(posts) / elapsed * 60) if elapsed > 0 else 0

            # Save results for this trend
            if posts:
                out_file = output_dir / f"{trend}_posts.json"
                with open(out_file, "w", encoding="utf-8") as f:
                    json.dump(posts, f, indent=2, ensure_ascii=False)
                logger.info(f"Saved [bold magenta]{len(posts)}[/bold magenta] posts to [dim]{out_file}[/dim]")
                summary_records.append({
                    "trend": trend,
                    "posts": len(posts),
                    "duration": elapsed,
                    "ppm": ppm,
                    "file": str(out_file)
                })
            else:
                logger.warning(f"No posts collected for trend: [bold red]{trend}[/bold red]")
                summary_records.append({
                    "trend": trend,
                    "posts": 0,
                    "duration": elapsed,
                    "ppm": 0,
                    "file": "N/A"
                })

        # Display final aggregated performance and resource metrics
        final_metrics = get_process_metrics()
        print_summary_table(summary_records, final_metrics)

    finally:
        orchestrator.stop()
        console.print("[bold green]✔ Automation completed successfully.[/bold green]\n")


if __name__ == "__main__":
    main()
