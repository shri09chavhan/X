"""
Resource monitoring utility.
Tracks CPU, RAM, and basic network throughput for the current process.
"""

import os
import psutil
from typing import Dict

def get_process_metrics() -> Dict[str, float]:
    """
    Returns current process resource usage metrics.
    """
    process = psutil.Process(os.getpid())
    
    # CPU usage (interval=None gives since last call, first call might be 0)
    cpu_percent = process.cpu_percent(interval=0.1)
    
    # Memory usage in MB
    memory_info = process.memory_info()
    rss_mb = memory_info.rss / (1024 * 1024)
    
    # Network (approximate based on process io counters)
    io_counters = process.io_counters()
    read_bytes_mb = io_counters.read_bytes / (1024 * 1024)
    write_bytes_mb = io_counters.write_bytes / (1024 * 1024)
    
    return {
        "cpu_percent": cpu_percent,
        "rss_mb": rss_mb,
        "read_mb": read_bytes_mb,
        "write_mb": write_bytes_mb
    }
