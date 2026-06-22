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
- [Known Limitations & Future Work](#known-limitations--future-work)

---

## Features

- **robots.txt compliance** — respects `Disallow` rules and honours the `Crawl-delay` directive.
- **Configurable crawl delay** — defaults to 30 s; overridden by `robots.txt` if its value is higher.
- **Resume support** — loads `pending` links from an existing SQLite database so interrupted runs can continue.
- **Re-crawl window** — skips pages crawled within a configurable time window (default: 3 hours) to avoid hammering the same URL.
- **Duplicate detection** — optional SHA-256 content-hash check prevents storing identical pages more than once per session.
- **Binary content handling** — non-text responses (images, PDFs, etc.) are stored Base64-encoded.
- **Retry with exponential backoff** — up to 3 retries on timeouts and 504 Gateway Timeout errors.
- **Domain-scoped crawl** — only follows links that share the same `netloc` as the seed URL.
- **Structured logging** — timestamped log files per domain, written with UTF-8 encoding.

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

Standard-library modules used: `sqlite3`, `hashlib`, `argparse`, `logging`, `urllib`, `base64`, `datetime`, `os`, `time`.

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

# Install dependencies
pip install requests beautifulsoup4 certifi
```

---

## Usage

```bash
python crawler_app.py --url <URL> [OPTIONS]
```

### Command-line Arguments

| Argument | Type | Default | Description |
|---|---|---|---|
| `--url` | `str` | **required** | Seed URL to start crawling from. |
| `--respect-robots` | flag | `False` | Honour `robots.txt` disallow rules and crawl-delay. |
| `--no-duplicates` | flag | `False` | Skip pages whose SHA-256 hash was already seen in this session. |
| `--crawl-delay` | `int` | `30` | Seconds to wait between requests. Overridden upward by `robots.txt`. |
| `--resume` | flag | `False` | Resume from an existing database (loads all `pending` links). |
| `--re-crawl-time` | `int` | `3` | Hours that must elapse before a URL is eligible for re-crawl. |
| `--logs-dir` | `str` | `logs` | Directory for log files (created if absent). |
| `--db-dir` | `str` | `db` | Directory for SQLite databases (created if absent). |

### Examples

**Basic crawl (no robots.txt, 30 s delay):**
```bash
python crawler_app.py --url https://www.example.com
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

**Re-crawl the same site weekly (168 h window):**
```bash
python crawler_app.py \
  --url https://cr.yp.to \
  --crawl-delay 30 \
  --resume \
  --re-crawl-time 168
```

---

## PowerShell Helper Script

`scripts/crawl-links.ps1` launches a separate maximised PowerShell window for each configured site, enabling parallel crawls across dozens of Greek and international news outlets simultaneously.

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

> **Tip:** Edit `crawl-links.ps1` to add or remove sites, or adjust delays and re-crawl windows to match each site's terms of service.

---

## Database Schema

Each domain gets its own SQLite file named `crawled_data_<domain>.db` inside `--db-dir`.

```sql
CREATE TABLE crawled_data (
    id             INTEGER  PRIMARY KEY AUTOINCREMENT,
    domain         TEXT     NOT NULL,
    date_inserted  DATETIME NOT NULL,   -- when the link was first discovered / last updated
    date_crawled   DATETIME,            -- when the page was last successfully fetched
    link           TEXT     NOT NULL,
    content        TEXT,                -- HTML (text) or Base64 (binary)
    content_hash   TEXT,                -- SHA-256 of content; also stored on fetch errors
    status         TEXT     NOT NULL    -- 'pending' | 'crawled'
                   CHECK(status IN ('pending', 'crawled'))
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
├── scripts/
│   └── crawl-links.ps1     # PowerShell multi-site launcher
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

Log entries are written both to the file and to the console (`StreamHandler`) at `INFO` level. UTF-8 encoding is enforced on the file handler to support Greek characters.

Example log output:
```
2024-10-15 14:30:22,001 - INFO - Crawling: https://www.kathimerini.gr/
2024-10-15 14:30:22,543 - INFO - Saved link to database: https://www.kathimerini.gr/politics/ (status: pending)
2024-10-15 14:30:22,544 - INFO - Waiting for 15 seconds before the next request...
```

---

## Known Limitations & Future Work

- **In-memory queue only** — the `to_crawl` list lives in RAM; very large sites may exhaust memory. Consider switching to a database-backed queue (e.g., read from `pending` in batches).
- **Single-threaded** — one page fetched at a time. Adding `asyncio` or a thread pool would increase throughput significantly.
- **No content parsing** — raw HTML/Base64 is stored as-is. A downstream pipeline is needed to extract article text, metadata, etc.
- **No `requirements.txt` / `pyproject.toml`** — adding one would simplify dependency management for new contributors.
- **`response` variable referenced before assignment** — in `utils.py`, the `HTTPError` handler accesses `response.status_code` which is set by `requests.get`, but the name could theoretically be unbound if the exception is raised before assignment. This is safe in practice with `requests` but adding an `UnboundLocalError` guard would make the intent explicit.
- **Link extraction limited to `<a href>`** — `<link>`, `<script src>`, sitemaps, and RSS feeds are not followed.
