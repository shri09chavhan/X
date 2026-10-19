"""
Main entry point for X automation.
Orchestrates trend scraping with configurable CLI parameters, granular benchmarks,
resource monitoring, and a state-of-the-art Rich UI.
"""

import argparse
import json
import logging
from pathlib import Path
from typing import List

from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.table import Table

from scraper.orchestrator import ScraperOrchestrator
from scraper.trend_provider import TrendProvider
from scraper.utils.monitor import get_process_metrics

console = Console()
METRICS_FILE = Path("output/metrics.json")

# Suppress noisy HTTP client logs from cloakbrowser and httpx
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

# Configure clean logging with RichHandler
logging.basicConfig(
    level="INFO",
    format="%(message)s",
    datefmt="[%X]",
    handlers=[
        RichHandler(
            console=console,
            rich_tracebacks=True,
            markup=True,
            show_path=False,
            show_time=True,
        )
    ],
)
logger = logging.getLogger("main")


def print_benchmark_card(bm: dict):
    """Prints a detailed, visual benchmark card for a single scraping operation."""
    tb = bm["time_breakdown"]
    res = bm["resources"]
    tp = bm["throughput"]
    total_t = max(tb["total_duration_sec"], 0.001)

    nav_pct = (tb["navigation_network_sec"] / total_t) * 100
    json_proc = tb.get("json_processing_sec", tb.get("dom_extraction_sec", 0.0))
    proc_pct = (json_proc / total_t) * 100
    wait_pct = (tb["scroll_waiting_sec"] / total_t) * 100

    content = (
        f"[bold cyan]Query:[/bold cyan] [yellow]'{bm['query']}'[/yellow]  │  "
        f"[bold green]Posts Collected:[/bold green] [bold]{bm['posts_collected']}/{bm['limit_target']}[/bold]  │  "
        f"[bold magenta]Scrolls:[/bold magenta] [bold]{bm['scrolls_performed']}/{bm['max_scrolls']}[/bold]\n\n"
        f"[bold underline]Time Breakdown:[/bold underline]\n"
        f"  • [blue]Network & Navigation[/blue]  : [bold]{tb['navigation_network_sec']:.2f}s[/bold] ({nav_pct:.1f}%)\n"
        f"  • [yellow]Scroll & Lazy-Wait[/yellow]    : [bold]{tb['scroll_waiting_sec']:.2f}s[/bold] ({wait_pct:.1f}%)\n"
        f"  • [green]JSON Processing (0 DOM)[/green]: [bold]{json_proc:.3f}s[/bold] ({proc_pct:.1f}%)\n"
        f"  • [white]Total Elapsed[/white]         : [bold white]{tb['total_duration_sec']:.2f}s[/bold white] "
        f"([cyan]{tp['ppm']:.1f} PPM[/cyan] │ [dim]{tp['seconds_per_post']:.2f}s per post[/dim])\n\n"
        f"[bold underline]Resource Consumption:[/bold underline]\n"
        f"  • CPU: [bold]{res['cpu_percent']}%[/bold]  │  "
        f"RAM: [bold]{res['ram_current_mb']:.1f} MB[/bold] ([dim]+{res['ram_delta_mb']:.2f} MB[/dim])  │  "
        f"Disk I/O: [dim]Read {res['io_read_mb']:.2f} MB / Write {res['io_write_mb']:.2f} MB[/dim]"
    )

    console.print(
        Panel(
            content,
            title=f"[bold green]📊 Benchmark Analysis: '{bm['query']}'[/bold green]",
            border_style="cyan",
            expand=False,
        )
    )


def print_summary_table(summary_records: list, final_metrics: dict):
    """Prints a clean, comprehensive summary table at the end of the entire run."""
    table = Table(
        title="[bold green]Execution & Performance Summary[/bold green]",
        title_style="bold green",
        header_style="bold cyan",
        border_style="bright_blue",
    )
    table.add_column("Query / Trend", style="bold cyan", no_wrap=True)
    table.add_column("Posts", justify="right", style="bold green")
    table.add_column("Scrolls", justify="right", style="magenta")
    table.add_column("Duration", justify="right", style="yellow")
    table.add_column("Speed (PPM)", justify="right", style="blue")
    table.add_column("Output File", style="dim")

    total_posts = 0
    total_time = 0.0
    total_scrolls = 0

    for rec in summary_records:
        table.add_row(
            rec["query"],
            str(rec["posts"]),
            str(rec["scrolls"]),
            f"{rec['duration']:.2f}s",
            f"{rec['ppm']:.1f}",
            rec["file"],
        )
        total_posts += rec["posts"]
        total_time += rec["duration"]
        total_scrolls += rec["scrolls"]

    overall_ppm = (total_posts / total_time * 60) if total_time > 0 else 0
    table.add_section()
    table.add_row(
        "[bold]TOTAL[/bold]",
        f"[bold]{total_posts}[/bold]",
        f"[bold]{total_scrolls}[/bold]",
        f"[bold]{total_time:.2f}s[/bold]",
        f"[bold]{overall_ppm:.1f}[/bold]",
        "[dim]output/*.json[/dim]",
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
        f"{final_metrics['write_mb']:.2f} MB",
    )
    console.print(resource_table)
    console.print()


def save_benchmark_to_disk(benchmark: dict) -> None:
    """Appends benchmark data to output/metrics.json."""
    try:
        metrics = []
        if METRICS_FILE.exists():
            with open(METRICS_FILE, "r", encoding="utf-8") as f:
                try:
                    metrics = json.load(f)
                except json.JSONDecodeError:
                    metrics = []
        metrics.append(benchmark)
        METRICS_FILE.parent.mkdir(exist_ok=True)
        with open(METRICS_FILE, "w", encoding="utf-8") as f:
            json.dump(metrics, f, indent=2)
    except Exception as e:
        logger.warning(f"Could not save benchmark to disk: {e}")


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="X (Twitter) Scraper & Automation Prototyping Engine",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "-q",
        "--query",
        "--search",
        type=str,
        default=None,
        help="Search query or comma-separated queries (e.g. 'Python' or 'AI, ML, Robotics'). If omitted, defaults to TrendProvider.",
    )
    parser.add_argument(
        "-l",
        "--limit",
        type=int,
        default=5,
        help="Target number of posts to collect per query.",
    )
    parser.add_argument(
        "-s",
        "--max-scrolls",
        type=int,
        default=15,
        help="Maximum scroll operations allowed per query.",
    )
    parser.add_argument(
        "--max-empty-scrolls",
        type=int,
        default=4,
        help="Stop if N consecutive scrolls yield no new posts.",
    )
    parser.add_argument(
        "--tab",
        choices=["latest", "top"],
        default="latest",
        help="Search tab to target ('latest' or 'top').",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        default=False,
        help="Run browser in headless mode (default: False for visual observation).",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=str,
        default="output",
        help="Directory to save scraped posts JSON files.",
    )
    return parser.parse_args()


def main():
    args = parse_arguments()

    session_file = Path("session.json")
    config_path = Path("config/selectors.yaml")
    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True)

    console.print()
    console.print(
        Panel.fit(
            "[bold cyan]X (Twitter) Automation & Scraping Engine[/bold cyan]\n"
            f"[dim]Mode: {'Headless' if args.headless else 'Headed (Visual)'} │ "
            f"Tab: {args.tab.title()} │ Limit: {args.limit} posts │ Max Scrolls: {args.max_scrolls}[/dim]",
            border_style="cyan",
        )
    )

    # Determine query list
    if args.query:
        queries: List[str] = [q.strip() for q in args.query.split(",") if q.strip()]
        logger.info(f"Targeting custom queries from CLI: [bold yellow]{queries}[/bold yellow]")
    else:
        trend_provider = TrendProvider()
        queries = trend_provider.get_trends()
        logger.info(f"No query passed. Using TrendProvider defaults: [bold yellow]{queries}[/bold yellow]")

    # Initialize components
    orchestrator = ScraperOrchestrator(session_file, config_path)

    # Start persistent browser session
    orchestrator.start(headless=args.headless)

    summary_records = []

    try:
        for query in queries:
            logger.info(f">>> Processing: [bold blue]{query}[/bold blue] (limit={args.limit}, max_scrolls={args.max_scrolls})")

            posts = orchestrator.scrape(
                query=query,
                limit=args.limit,
                max_scrolls=args.max_scrolls,
                max_empty_scrolls=args.max_empty_scrolls,
                select_latest=(args.tab == "latest"),
            )

            bm = orchestrator.last_benchmark

            # Print dedicated benchmark card immediately
            if bm:
                print_benchmark_card(bm)
                save_benchmark_to_disk(bm)
                # Benchmark comparison
                from scraper.utils.benchmark import PerformanceBenchmark
                bench = PerformanceBenchmark()
                comp = bench.compare_with_latest(bm)
                logger.info(f"Benchmark comparison: {comp['summary']}")

            # Save posts to JSON file
            safe_name = "".join(c for c in query if c.isalnum() or c in ("_", "-"))
            out_file = output_dir / f"{safe_name}_posts.json"

            if posts:
                with open(out_file, "w", encoding="utf-8") as f:
                    json.dump(posts, f, indent=2, ensure_ascii=False)
                logger.info(f"Saved [bold magenta]{len(posts)}[/bold magenta] posts to [dim]{out_file}[/dim]")
            else:
                logger.warning(f"No posts collected for: [bold red]{query}[/bold red]")

            summary_records.append({
                "query": query,
                "posts": len(posts),
                "scrolls": bm.get("scrolls_performed", 0) if bm else 0,
                "duration": bm.get("time_breakdown", {}).get("total_duration_sec", 0.0) if bm else 0.0,
                "ppm": bm.get("throughput", {}).get("ppm", 0.0) if bm else 0.0,
                "file": str(out_file) if posts else "N/A",
            })

        # Display final aggregated performance and resource metrics
        final_metrics = get_process_metrics()
        print_summary_table(summary_records, final_metrics)

    finally:
        orchestrator.stop()
        console.print("[bold green]✔ Scraping and benchmark session completed.[/bold green]\n")


if __name__ == "__main__":
    main()
