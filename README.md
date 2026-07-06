# Greek News Scraper — Crawler

A lightweight, polite web crawler written in Python that scrapes news sites and stores raw page content in a per-domain SQLite database. Built with `robots.txt` compliance, configurable crawl delays, exponential-backoff retries, SHA-256 duplicate detection, and resume support.

---

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Requirements](#requirements)
- [Installation](#installation)
- [Usage](#usage)
  - [Command-line Arguments](#command-line-arguments)
  - [Examples](#examples)
- [PowerShell Helper Script](#powershell-helper-script)
- [Database Schema](#database-schema)
- [Project Structure](#project-structure)
- [Configuration](#configuration)
- [Logging](#logging)
- [Graceful Shutdown](#graceful-shutdown)
- [Known Limitations & Future Work](#known-limitations--future-work)

---

## Features

- **robots.txt compliance** — respects `Disallow` rules and honours the `Crawl-delay` directive.
- **Configurable crawl delay** — defaults to 30 s; overridden by `robots.txt` if its value is higher.
- **Concurrent crawling (multi-threading)** — support for parallel worker threads via a thread pool (`--workers`) with safety locks.
- **Auto-scaled rate-limiting** — automatically scales individual worker delays to keep the overall request rate to the server safe and unchanged.
- **Resume support** — loads `pending` links from an existing SQLite database so interrupted runs can continue.
- **Re-crawl window** — skips pages crawled within a configurable time window (default: 3 hours) to avoid hammering the same URL.
- **Duplicate detection** — optional SHA-256 content-hash check prevents storing identical pages more than once per session.
- **Binary content handling** — non-text responses (images, PDFs, etc.) are stored Base64-encoded.
- **Retry with exponential backoff** — up to 3 retries on timeouts and 504 Gateway Timeout errors.
- **Domain-scoped crawl** — only follows links that share the same `netloc` as the seed URL.
- **Structured logging** — timestamped log files per domain, written with UTF-8 encoding. Each site gets its own isolated logger in parallel mode — no cross-contamination between log files.
- **Graceful shutdown** — press `Ctrl+C` once to finish in-flight pages and exit cleanly; press again to force-quit immediately.

---

## Architecture

```
crawler_app.py        ← entry point / orchestration
  ├── config.py       ← global constants (User-Agent string)
  ├── utils.py        ← HTTP fetching, link extraction, hashing, filesystem helpers
  └── database.py     ← SQLite schema, CRUD operations
scripts/
  └── crawl-links.ps1 ← PowerShell launcher for parallel multi-site crawls
```

The crawler follows a simple **BFS queue** pattern:

1. Seed URL is inserted as `pending` in the database.
2. The main loop pops a URL, fetches its content, updates the record to `crawled`, extracts new same-domain links, and appends them to the queue.
3. New links are batch-saved to the database before the next request.
4. A configurable sleep is observed between each real fetch.

---

## Requirements

- Python 3.10+
- [requests](https://pypi.org/project/requests/)
- [beautifulsoup4](https://pypi.org/project/beautifulsoup4/)
- [certifi](https://pypi.org/project/certifi/)
- [trafilatura](https://pypi.org/project/trafilatura/) (≥ 1.8.0) — article text extraction & boilerplate removal
- [newspaper3k](https://pypi.org/project/newspaper3k/) (≥ 0.2.8) — news article scraping (title, authors, date, keywords)

Standard-library modules used: `sqlite3`, `hashlib`, `argparse`, `logging`, `signal`, `urllib`, `base64`, `datetime`, `os`, `time`, `json`, `threading`.

---

## Installation

```bash
# Clone the repository
git clone https://github.com/svagionitis/crawler.git
cd crawler

# Create and activate a virtual environment (recommended)
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

# Install dependencies using the requirements file
pip install -r requirements.txt
```

---

## Usage

```bash
# Crawl a single website
python crawler_app.py --url <URL> [OPTIONS]

# Crawl multiple websites in parallel using a JSON configuration file
python crawler_app.py --config <PATH_TO_JSON> [OPTIONS]
```

### Command-line Arguments

| Argument | Type | Default | Description |
|---|---|---|---|
| `--url` | `str` | `None` | Seed URL to start crawling from (required unless `--config` is specified). |
| `--config` | `str` | `None` | Path to a JSON configuration file containing target URLs and site-specific options (array of objects format). |
| `--respect-robots` | flag | `False` | Honour `robots.txt` disallow rules and crawl-delay. |
| `--no-duplicates` | flag | `False` | Skip pages whose SHA-256 hash was already seen in this session. |
| `--crawl-delay` | `int` | `30` | Seconds to wait between requests. Overridden upward by `robots.txt`. |
| `--resume` | flag | `False` | Resume from an existing database (loads all `pending` links). |
| `--re-crawl-time` | `int` | `3` | Hours that must elapse before a URL is eligible for re-crawl. |
| `--logs-dir` | `str` | `logs` | Directory for log files (created if absent). |
| `--db-dir` | `str` | `db` | Directory for SQLite databases (created if absent). |
| `--batch-size` | `int` | `100` | Pending URLs fetched from the DB per batch. Tune down for low-memory hosts, up for resume runs on large DBs. |
| `--workers` | `int` | `1` | Number of parallel worker threads. The crawl delay is automatically scaled by this factor to maintain the aggregate request rate to the server, and forced to 1 if a `robots.txt` crawl delay is applied. |
| `--parser` | `str` | `auto` | Parsing engine for content & text extraction (`auto`, `newspaper`, `trafilatura`, `bs4`). |

### Crawling Multiple URLs via JSON Configuration

Instead of crawling a single site via `--url`, you can provide a JSON file containing an array of target site configurations using `--config`. All sites in the file are crawled **in parallel** — each site runs in its own thread, with its own database and log file.

Each object in the array represents a target site and can override any of the standard crawler settings:

```json
[
  {
    "url": "https://news.ycombinator.com",
    "respect_robots": true,
    "crawl_delay": 5,
    "re_crawl_time": 8,
    "workers": 2
  },
  {
    "url": "https://www.tovima.gr",
    "respect_robots": true,
    "crawl_delay": 15,
    "re_crawl_time": 24
  }
]
```

#### Option Merging & Fallbacks
Any site-specific settings omitted from a site's JSON block will automatically fall back to the CLI arguments supplied on execution (or standard CLI defaults). For example, running:

```bash
python crawler_app.py --config config.json --db-dir F:\db --logs-dir F:\logs
```

will apply `F:\db` and `F:\logs` as the database and logs directory settings for all sites in `config.json` except those that specify their own local `db_dir` or `logs_dir` fields.

### Multi-threading & Rate Limiting

To increase throughput without overloading target servers, the crawler supports concurrent crawling via `--workers`:
- **Auto-scaled Delay**: If you specify `--workers N` and a `--crawl-delay D`, the crawler automatically scales the delay for each individual worker to `D * N` seconds. This ensures that the overall request frequency hitting the server remains 1 request every `D` seconds on average.
- **robots.txt Safety**: If a site's `robots.txt` specifies a `Crawl-delay` and you run with `--respect-robots`, the crawler forces `--workers` to `1`. This is done to strictly honor the site's crawling policies and prevent parallel request bursts.

### Content Parsing & Text Extraction

For downstream text similarity, plagiarism checking, or general news analysis, the crawler extracts structured data from crawled HTML files:
- **Extracted Fields**:
  - `extracted_title`: The article headline.
  - `extracted_text`: Clean body text with boilerplate (headers, footer, ads, navigation menus) removed.
  - `extracted_authors`: Comma-separated list of article authors.
  - `extracted_date`: Publication date in ISO format or raw string.
  - `extracted_keywords`: Comma-separated list of keywords.
- **Parser Engines**:
  - `newspaper`: Uses the `newspaper3k` package (best for full news metadata, authorship, and NLP keywords).
  - `trafilatura`: Uses the `trafilatura` library (highly accurate text extraction and boilerplate cleaning).
  - `bs4`: Standard BeautifulSoup cleaning fallback (removes `<script>`, `<style>`, `<nav>`, `<footer>`, etc., and retrieves `<p>` blocks).
  - `auto` (Default): Attempts to use `newspaper` first, falls back to `trafilatura` if unavailable, and uses `bs4` if neither is installed.


**Basic crawl (no robots.txt, 30 s delay):**
```bash
python crawler_app.py --url https://www.example.com
```

**Parallel multi-site crawl using a JSON configuration:**
```bash
python crawler_app.py --config config.json --db-dir F:\db --logs-dir F:\logs
```

**Polite crawl with resume and duplicate filtering:**
```bash
python crawler_app.py \
  --url https://www.kathimerini.gr \
  --respect-robots \
  --no-duplicates \
  --crawl-delay 15 \
  --resume \
  --re-crawl-time 24 \
  --logs-dir C:\logs \
  --db-dir C:\db
```

**Multi-threaded crawl with 4 workers (auto-scales 15 s delay to 60 s per worker thread to maintain 15 s server rate):**
```bash
python crawler_app.py \
  --url https://www.kathimerini.gr \
  --workers 4 \
  --crawl-delay 15
```

**Re-crawl the same site weekly (168 h window):**
```bash
python crawler_app.py \
  --url https://cr.yp.to \
  --crawl-delay 30 \
  --resume \
  --re-crawl-time 168
```

---

## PowerShell Helper Scripts

There are two PowerShell scripts available in the `scripts/` directory:

### Hardcoded Launcher (Parallel)

`scripts/crawl-links.ps1` launches parallel crawls for a hardcoded set of sites, opening each in a separate maximized PowerShell window:

```powershell
# Run from the project root
.\scripts\crawl-links.ps1
```

Each window's title bar shows the URL being crawled. Sites currently configured include:

| Outlet | Crawl Delay | Re-crawl Window |
|---|---|---|
| tovima.gr, tanea.gr, protothema.gr, … | 15 s | 24 h |
| rizospastis.gr | 30 s | 24 h |
| bbc.com, theguardian.com, aljazeera.com | 30 s | 24 h |
| cr.yp.to, labtestsonline.org.uk | 30 s | 168 h (weekly) |
| news.ycombinator.com | 0 s (robots.txt) | 8 h |

### Config-driven Launcher (Parallel)

`scripts/crawl-by-config.ps1` passes a JSON configuration file directly to `crawler_app.py --config`, which crawls **all sites in parallel** in the current console session. It defaults to `config/news-sites-gr.json` but accepts any config file via the `-ConfigPath` parameter:

```powershell
# Run using the default configuration (config/news-sites-gr.json)
.\scripts\crawl-by-config.ps1

# Run using a custom configuration file
.\scripts\crawl-by-config.ps1 -ConfigPath config/sites.json
```

> **Tip:** Edit `config/news-sites-gr.json` or `config/sites.json` to add or remove sites, and use `crawl-by-config.ps1` to run crawls dynamically based on those files.

---

## Database Schema

Each domain gets its own SQLite file named `crawled_data_<domain>.db` inside `--db-dir`. The database uses Write-Ahead Log (WAL) mode (`PRAGMA journal_mode=WAL`) to support concurrent writes from multiple worker threads without locking.

```sql
CREATE TABLE crawled_data (
    id                 INTEGER  PRIMARY KEY AUTOINCREMENT,
    domain             TEXT     NOT NULL,
    date_inserted      DATETIME NOT NULL,   -- when the link was first discovered / last updated
    date_crawled       DATETIME,            -- when the page was last successfully fetched
    link               TEXT     NOT NULL,
    content            TEXT,                -- HTML (text) or Base64 (binary)
    content_hash       TEXT,                -- SHA-256 of content; also stored on fetch errors
    status             TEXT     NOT NULL    -- 'pending' | 'crawled'
                       CHECK(status IN ('pending', 'crawled')),
    extracted_title    TEXT,                -- article headline
    extracted_text     TEXT,                -- clean body text (boilerplate removed)
    extracted_authors  TEXT,                -- comma-separated author list
    extracted_date     TEXT,                -- publication date (ISO format or raw string)
    extracted_keywords TEXT                 -- comma-separated keywords
);

-- Indexes for fast queue queries
CREATE INDEX idx_link          ON crawled_data (link);
CREATE INDEX idx_status        ON crawled_data (status);
CREATE INDEX idx_link_status   ON crawled_data (link, status);
```

**Status lifecycle:**

```
discovered → pending
fetched ok → crawled
fetch error → pending  (retried on next run)
re-crawl skipped → pending (date_inserted refreshed)
```

---

## Project Structure

```
.
├── crawler_app.py          # Main entry point and crawl orchestration
├── config.py               # Shared constants (USER_AGENT)
├── database.py             # SQLite helpers (init, save, update, load, check)
├── utils.py                # HTTP fetch, link extraction, hashing, directory utils
├── requirements.txt        # Python dependencies
├── config/
│   ├── news-sites-gr.json  # Default multi-site crawl configuration (Greek news outlets)
│   └── sites.json          # Alternative/extended site configuration
├── scripts/
│   ├── crawl-links.ps1     # PowerShell multi-site launcher (one window per site)
│   └── crawl-by-config.ps1 # PowerShell config-driven launcher (single process)
├── test-page.htm           # Sample HTML page for offline testing
├── .editorconfig           # Editor formatting rules (4-space indent, UTF-8)
├── .gitignore              # Standard Python gitignore
└── README.md
```

---

## Configuration

The only shared configuration lives in [`config.py`](config.py):

```python
USER_AGENT = "Crawler/1.0 (+https://example.com/crawler)"
```

Update this value to identify your crawler in server access logs and to `robots.txt` parsers.

---

## Logging

A new log file is created per run, named:

```
<logs-dir>/crawler_<domain>_<YYYYMMDDHHMMSS>.log
```

Each site gets its own **named logger** (`crawler.<domain>`), so when crawling multiple sites in parallel via `--config`, each site's log output is written to a **separate file** with no cross-contamination. Log entries are written both to the file and to the console (`StreamHandler`) at `INFO` level. UTF-8 encoding is enforced on the file handler to support Greek characters.

Example log output:
```
2024-10-15 14:30:22,001 - INFO - Crawling: https://www.kathimerini.gr/
2024-10-15 14:30:22,543 - INFO - Saved link to database: https://www.kathimerini.gr/politics/ (status: pending)
2024-10-15 14:30:22,544 - INFO - Waiting for 15 seconds before the next request...
```

---

## Graceful Shutdown

The crawler supports graceful shutdown via `Ctrl+C` (SIGINT):

| Action | Behaviour |
|---|---|
| **First `Ctrl+C`** | Sets a shutdown flag. Workers finish their **current in-flight page**, skip remaining queued URLs, and exit cleanly. A log message confirms: *"Shutdown requested. Crawl stopped gracefully."* |
| **Second `Ctrl+C`** | Restores the default signal handler and exits immediately (hard kill). |

This works for both `--url` (single site) and `--config` (parallel multi-site) modes. Since `crawl-by-config.ps1` runs `python.exe` directly, `Ctrl+C` in the PowerShell window propagates to the Python process automatically.

Pending links remain in the database with `status = 'pending'`, so you can resume with `--resume` after a graceful stop.

---

## Known Limitations & Future Work

- **Dynamic / JavaScript-Rendered Sites** — The crawler currently performs static HTTP requests. Sites that rely on client-side JavaScript framework rendering (React, Vue, etc.) or load articles dynamically will not have their text contents fully captured. Incorporating a headless browser rendering engine (such as Playwright, Selenium, or Pyppeteer) is a planned feature to handle dynamic web content.
- **Plagiarism & Duplicate Content Detection** — To check if news reports are plagiarized or cover identical stories, extracted article texts can be compared using natural language processing (NLP) and similarity algorithms (such as MinHash/LSH, Cosine Similarity via TF-IDF or word/document embeddings, and sequence alignment).
- **Link extraction limited to `<a href>`** — `<link>`, `<script src>`, sitemaps, and RSS feeds are not followed.

