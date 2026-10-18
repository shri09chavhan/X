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
    Decorator that measures the execution time of a function 
    and logs the result to a persistent JSON file.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        end_time = time.perf_counter()
        
        duration = end_time - start_time
        metric_data = {
            "function": func.__name__,
            "duration": duration,
            "timestamp": time.time()
        }
        
        logger.info(f"Performance: {func.__name__} took {duration:.4f} seconds.")
        
        # Simple persistence: append to metrics file
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
            
        return result
    return wrapper
