# X (Twitter) Automation & Scraping Engine

A high-performance, anti-detect scraping and automation engine built on **CloakBrowser** and **Playwright**. It reuses authenticated browser sessions, features native stealth mouse-wheel scrolling, dynamic smart waiting, and detailed real-time resource and latency benchmarking.

---

## Quick Start

### 1. Installation
Run the automated setup script to create a virtual environment, install dependencies, and configure browser binaries:

```bash
./setup.sh
source .venv/bin/activate
```

### 2. Authentication
Log in once through the interactive CloakBrowser window to generate `session.json`:

```bash
python login_and_save_session.py
```
*Enter your credentials and log in. Once you land on your home feed, press ENTER in the terminal (or wait for auto-detection) to export your session.*

---

## Running the Scraper (`main.py`)

Run `main.py` directly from the terminal without editing any code.

### Command-Line Arguments Reference

| Flag | Long Option | Type | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `-q` | `--query`, `--search` | `str` | `None` | Search query or comma-separated queries (e.g. `"Python"` or `"AI, ML, Robotics"`). If omitted, falls back to `TrendProvider`. |
| `-l` | `--limit` | `int` | `5` | Target number of posts to collect per query. |
| `-s` | `--max-scrolls` | `int` | `15` | Maximum scroll operations allowed per query. |
| | `--max-empty-scrolls`| `int` | `4` | Stop scrolling if N consecutive attempts yield no new posts. |
| | `--tab` | `choice` | `latest` | Tab to target on search results: `latest` or `top`. |
| | `--headless` | `flag` | `False` | Run browser in headless mode in the background (default: visual GUI). |
| `-o` | `--output-dir` | `str` | `output` | Directory where output JSON files are saved. |
| `-h` | `--help` | | | Display available options and exit. |

---

## Usage Examples

### 1. Default Run (Trend Provider)
Runs queries provided by `TrendProvider` (`Python`, `ArtificialIntelligence`, `WebScraping`) with visual browser:
```bash
python main.py
```

### 2. Single Query with Custom Limits
Scrape 10 posts for "DeepSeek" with a maximum of 5 scrolls:
```bash
python main.py -q "DeepSeek" -l 10 -s 5
```

### 3. Multiple Queries in One Session
Pass comma-separated queries to scrape in a single browser session:
```bash
python main.py -q "AI, MachineLearning, WebScraping" -l 5 -s 3
```

### 4. Background (Headless) Execution
Scrape 50 posts in the background without opening a visible browser window:
```bash
python main.py -q "MPSC Protest" -l 50 -s 15 --headless
```

### 5. Target "Top" Tab Instead of "Latest"
Scrape top viral posts for a search query:
```bash
python main.py -q "OpenAI" --tab top -l 20
```

### 6. Custom Output Directory
Save results to a specific folder:
```bash
python main.py -q "Robotics" -l 10 -o my_data
```

---

## Output & Benchmarks

### 1. Post Records
Scraped posts are incrementally saved to `{output_dir}/{query}_posts.json`:
```json
[
  {
    "post_id": "2111827969476018589",
    "post_url": "https://x.com/username/status/2111827969476018589",
    "author_name": "Full Name",
    "author_handle": "@handle",
    "text": "Tweet body content...",
    "created_at": "2026-10-18T14:33:18.000Z",
    "reply_count": 12,
    "repost_count": 4,
    "like_count": 88,
    "view_count": 1420
  }
]
```

### 2. Real-Time Benchmark Analysis
After each query, a detailed benchmark card is displayed:
- **Time Breakdown**: Network & Navigation time vs. Scroll & Lazy-Wait time vs. DOM Extraction time.
- **Throughput**: Calculated in **PPM** (Posts Per Minute) and seconds per post.
- **Resource Usage**: CPU %, Memory (RSS in MB and delta), and Disk I/O.
- **Historical Metrics**: Appended to `output/metrics.json` for analysis.

---

## Project Structure

```text
├── config/
│   └── selectors.yaml        # Externalized DOM selectors
├── output/                   # Scraped JSON files and metrics (git-ignored)
├── scraper/
│   ├── browser_handler.py    # CloakBrowser context lifecycle management
│   ├── dom_extractor.py      # Robust DOM parsing and regex metric extraction
│   ├── orchestrator.py       # Main scraping flow with smart wait & big scrolls
│   ├── trend_provider.py     # Default keyword provider
│   └── utils/
│       ├── metrics.py        # Performance decorators and metric persistence
│       └── monitor.py        # System resource tracking (CPU, RAM, I/O)
├── login_and_save_session.py # Interactive authentication script
├── main.py                   # CLI entry point with Rich UI
├── session.json              # Authentication storage state (git-ignored)
└── setup.sh                  # Virtualenv setup and dependency installer
```
