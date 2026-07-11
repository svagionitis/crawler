# C4 Model - Level 3: Component Diagram

The Component diagram shows the internal structure of the Python CLI Engine container and how components cooperate at runtime.

## ASCII Diagram

```text
+-------------------------------------------------------------------------------------+
| Container: Python CLI Engine                                                        |
|                                                                                     |
|   +-------------------+        Uses         +-----------------------+               |
|   |   SiteCrawler     +-------------------->|    CrawlerConfig      |               |
|   |  (Orchestrator,   |                     |  (Stores defaults &   |               |
|   |   Thread manager) |                     |   custom site flags)  |               |
|   +---------+---------+                     +-----------------------+               |
|             |                                                                       |
|             | Uses                                                                  |
|             v                                                                       |
|   +---------+---------+        Uses         +-----------------------+               |
|   |   ProxyProvider   +-------------------->|  fetch_page (utils)   |               |
|   |  (Direct, Tor,    |                     |  (requests Wrapper    |               |
|   |   Static Proxies) |                     |   with retry/backoff) |               |
|   +-------------------+                     +-----------+-----------+               |
|                                                         |                           |
|                                                         | Employs                   |
|                                                         v                           |
|   +-------------------+        Delegates    +-----------+-----------+               |
|   |  ContentProcessor |<--------------------+    Extractor Strategy |               |
|   | (news strategy for|                     |   (Trafilatura, BS4,  |               |
|   |  saving/matching) |                     |    Newspaper3k)       |               |
|   +---------+---------+                     +-----------------------+               |
|             |                                                                       |
|             +-----------------------+                                               |
|             | Calls                 | Calls                                         |
|             v                       v                                               |
|   +---------+---------+   +---------+---------+                                     |
|   |   Database API    |   | SimilarityIndexer |                                     |
|   |  (SQLite schemas, |   | (MinHash, Jaccard |                                     |
|   |   queries, queue) |   |  similarity checks|                                     |
|   +-------------------+   +-------------------+                                     |
+-------------------------------------------------------------------------------------+
```

## Mermaid Diagram

```mermaid
graph TD
    SiteCrawler["SiteCrawler (orchestrator)"]
    CrawlerConfig["CrawlerConfig (dataclass)"]
    ProxyProvider["ProxyProvider (proxies.py)"]
    FetchPage["fetch_page (utils.py)"]
    Extractor["Extractor Strategy (extractors.py)"]
    Processor["ContentProcessor (processors.py)"]
    DatabaseAPI["Database API (database.py)"]
    SimilarityIndexer["SimilarityIndexer (similarity.py)"]

    SiteCrawler -->|Loads settings| CrawlerConfig
    SiteCrawler -->|Sets proxies| ProxyProvider
    SiteCrawler -->|Fetches pages| FetchPage
    FetchPage -->|Extracts links & HTML| Extractor
    SiteCrawler -->|Processes page data| Processor
    Processor -->|Saves state & links| DatabaseAPI
    Processor -->|Generates signatures & checks duplicates| SimilarityIndexer
```

## Details & Description

### 1. SiteCrawler (`crawler_app.py`)
* Manages crawler runtime loop, thread execution (Producer/Consumer model), log initiation, and safe shutdown processes.

### 2. CrawlerConfig (`config.py`)
* Centralized dataclass encapsulating all execution parameters (crawl delay, respect robots, DB directory, logging paths, and plagiarism parameters) with standard fallback values.

### 3. ProxyProvider (`proxies.py`)
* Factory provider representing direct connection, static proxies, or Tor proxy configuration strategies.

### 4. Fetch Page Helper (`utils.py`)
* Standard wrapper around the `requests` library implementing connection timeouts, exponential backoff retries, SSL verification, and binary/text parsing.

### 5. Extractor Strategy (`extractors.py`)
* Implements Strategy Pattern to extract text content, metadata, titles, and publishing dates using `BeautifulSoup`, `Trafilatura`, or `newspaper3k` extractors depending on availability and preference.

### 6. ContentProcessor Strategy (`processors.py`)
* Dictates what to do with crawled HTML and text. The default `NewsContentProcessor` parses the text, checks database constraints, generates fingerprint hashes, checks for plagiarism, and saves the article.

### 7. Database API (`database.py`)
* Interface mapping read/write operations to SQLite, handling thread-local connection pools, queue structures, and schema migrations.

### 8. SimilarityIndexer (`similarity.py`)
* Performs content deduplication and plagiarism checking. Calculates Jaccard similarity indices on MinHash signatures generated from document shingles.
