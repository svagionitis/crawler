# C4 Model - Level 1: System Context Diagram

This diagram shows the GreekNewsScraper Crawler system boundaries, the users/operators interacting with it, and the external dependencies or systems it communicates with.

## ASCII Diagram

```text
+---------------------------------------+
|              Developer /              |
|               Operator                |
|      (Runs CLI / Config crawls)       |
+-------------------+-------------------+
                    |
                    | Triggers
                    v
+-------------------+-------------------+
|                                       |
|        News Crawler System            |  Reads settings
|     (Executes site scraping,          +------------------->  Local JSON Config
|      parses & stores articles)        |                      (sites.json)
|                                       |
+---------+-------------------+---------+
          |                   |
          | Scrapes           | Reroutes (optional)
          v                   v
+---------+---------+   +-----+-------------+
|  News Websites    |   | Tor / Proxy       |
|  (Target hosts    |   | Services          |
|   e.g. tovima.gr) |   | (IP Rotation)     |
+-------------------+   +-------------------+
```

## Mermaid Diagram

```mermaid
graph TD
    User["Developer / Operator (User)"]
    Crawler["News Crawler System (Python Scraper)"]
    Config["Local JSON Config (sites.json / news-sites-gr.json)"]
    Websites["News Websites (Target HTML Servers)"]
    Proxy["Tor / Proxy Services (SOCKS5/HTTP Proxy)"]

    User -->|Triggers & Coordinates| Crawler
    Crawler -->|Reads target list & settings| Config
    Crawler -->|Scrapes HTML pages directly| Websites
    Crawler -->|Reroutes connections dynamically| Proxy
    Proxy -->|Scrapes HTML pages anonymously| Websites
```

## Details & Description

### Users / Actors
* **Developer / Operator**: Triggers the crawler execution either via a single target URL (`--url`) or using parallel configurations (`--config`). They read log outputs and query the generated SQLite databases.

### Software System
* **News Crawler System**: The core Python application (`crawler_app.py`). It orchestrates connection management, respects crawling rules (such as `robots.txt`), performs boilerplate removal and text extraction, flags near-duplicate articles, and stores structured content.

### External Dependencies & Systems
* **Local JSON Config**: Local configuration files containing target news site urls, crawl delays, re-crawl times, and proxy preferences.
* **News Websites**: Remote HTTP/HTTPS servers hosting target news portals. These are scraped strictly following their `robots.txt` directives.
* **Tor / Proxy Services**: Services (e.g. SOCKS5h Tor wrapper or HTTP proxies) optional for connection routing, helping bypass rate-limits, prevent IP blocks, and ensure anonymity.
