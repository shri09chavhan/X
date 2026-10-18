"""
Performance instrumentation utility.
Provides decorators for measuring execution time and logging performance metrics.
"""

import time
import functools
import logging
import json
from pathlib import Path
from typing import Callable, Any

logger = logging.getLogger("twitter_scraper.metrics")
METRICS_FILE = Path("output/metrics.json")

def timeit(func: Callable) -> Callable:
    """
    Decorator that measures the execution time and calculates posts-per-minute (PPM).
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        start_time = time.perf_counter()
        
        # Execute the function
        result = func(*args, **kwargs)
        
        end_time = time.perf_counter()
        duration_sec = end_time - start_time
        
        # Calculate performance metrics
        post_count = len(result) if isinstance(result, list) else 0
        ppm = (post_count / duration_sec) * 60 if duration_sec > 0 else 0
        
        metric_data = {
            "function": func.__name__,
            "duration_sec": duration_sec,
            "posts_collected": post_count,
            "ppm": ppm,
            "timestamp": time.time()
        }
        
        logger.info(
            f"Performance: [cyan]{func.__name__}[/cyan] | "
            f"Collected [bold green]{post_count}[/bold green] posts in "
            f"[yellow]{duration_sec:.2f}s[/yellow] ([blue]{ppm:.1f} PPM[/blue])"
        )
        
        # Persist metrics
        _persist_metric(metric_data)
        
        return result
    return wrapper

def _persist_metric(metric_data: dict) -> None:
    """Persists metrics to JSON file."""
    try:
        metrics = []
        if METRICS_FILE.exists():
            with open(METRICS_FILE, "r") as f:
                try:
                    metrics = json.load(f)
                except json.JSONDecodeError:
                    metrics = []
        
        metrics.append(metric_data)
        
        METRICS_FILE.parent.mkdir(exist_ok=True)
        with open(METRICS_FILE, "w") as f:
            json.dump(metrics, f, indent=2)
            
    except Exception as e:
        logger.warning(f"Failed to save metrics: {e}")
