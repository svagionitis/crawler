# Future Architectural & Engineering Patterns

This document details proposed architectural patterns, engineering practices, and advanced features inspired by mature projects like `yt-dlp` that can be integrated into the Greek News Scraper in future development phases.

---

## 1. Site-Specific Selective Selector Overrides
*   **Concept**: Building upon the **InfoExtractor Pattern** introduced in Phase 3, we can allow each site-specific extractor class (e.g. `KathimeriniGrExtractor`) to override default parsing behaviors with precise HTML element selectors.
*   **Application**:
    Instead of relying purely on auto-extraction models (`newspaper3k` / `trafilatura`) which might miss custom metadata, site classes can define a configuration mapping or override the `extract()` method directly:
    ```python
    class KathimeriniGrExtractor(BaseSiteExtractor):
        _VALID_URL = r'^https?://(?:www\.)?kathimerini\.gr/.*$'

        def extract(self, html_content, **kwargs):
            soup = kwargs.get('soup') or BeautifulSoup(html_content, 'html.parser')
            # Kathimerini-specific clean authorship selectors
            author = soup.select_one(".article-author-name").get_text(strip=True)
            # Default to generic fallback for text body
            data = GenericExtractor().extract(html_content, **kwargs)
            data["authors"] = author
            return data
    ```

---

## 2. Browser Cookie Integration (Paywall & Auth Bypass)
*   **Concept**: Inspired by `yt-dlp`'s `--cookies-from-browser` flag. The crawler can import session cookies directly from the operator's local browser profile (Chrome, Firefox, Safari, Edge) to authenticate requests.
*   **Application**:
    Useful for crawling paywalled news portals or sites requiring cookie verification checks. Integrate the `browser-cookie3` package to dynamically load cookies into the request session:
    ```python
    import browser_cookie3

    def get_authenticated_session(domain_name: str):
        session = requests.Session()
        try:
            # Extract active browser cookies for this domain
            cookies = browser_cookie3.firefox(domain_name=domain_name)
            session.cookies.update(cookies)
        except Exception as e:
            logging.warning(f"Could not load browser cookies: {e}")
        return session
    ```

---

## 3. HTTP/2 and TLS Fingerprint Spoofing
*   **Concept**: Web protection platforms (Cloudflare, Akamai, Imperva) block automated crawlers by fingerprinting TLS Handshakes and HTTP/1.1 headers.
*   **Application**:
    Migrate from standard `requests` (which is HTTP/1.1 and has a distinct Python-urllib signature) to libraries like `curl_cffi` or `httpx` supporting HTTP/2 and TLS JA3 fingerprint impersonation:
    ```python
    # Using curl_cffi to impersonate a real Chrome browser signature
    from curl_cffi import requests

    response = requests.get(
        url,
        impersonate="chrome120",  # Automatically mimics Chrome's TLS fingerprint & headers
        timeout=30
    )
    ```

---

## 4. Decoupled Post-Processing Pipelines
*   **Concept**: Separation of concerns post-crawl. Instead of running analysis (like plagiarism indexing, translation, or entity extraction) inside the worker threads, separate these concerns into a modular pipeline.
*   **Application**:
    Expose a pipeline pattern where developers can register plugins to run sequentially after a page is written to the core queue:
    ```
    Raw Crawled Page
         │
         ▼
    [Pipeline Base]
         │
         ├──► PlagiarismIndexer (MinHash verification)
         ├──► NamedEntityRecognizer (NER for Greek names/locations)
         ├──► VectorDatabaseLoader (Generate embeddings for AI search)
         └──► SentimentAnalyzer (Calculate article polarity)
    ```

---

## 5. Active Tor Circuit Rotation (Active Anti-Blocking)
*   **Concept**: When crawling via Tor, rather than waiting out a rate-limit block (HTTP 429), the crawler can actively signal the local Tor controller to obtain a new IP address circuit.
*   **Application**:
    Use the `stem` library to authenticate with the local Tor controller port and request a `NEWNYM` signal:
    ```python
    from stem import Signal
    from stem.control import Controller

    def rotate_tor_ip(control_port=9051, password="tor_password"):
        with Controller.from_port(port=control_port) as controller:
            controller.authenticate(password=password)
            controller.signal(Signal.NEWNYM)
            logging.info("Requested new Tor circuit IP address.")
    ```

---

## 6. Vector Store & Semantic Similarity Indexing
*   **Concept**: Shifting from MinHash Jaccard similarity (which requires lexical near-duplicates) to semantic similarity (concepts, meanings, cross-lingual duplicates).
*   **Application**:
    Encode extracted text into dense vectors (e.g., using lightweight Greek BERT models or OpenAI text-embeddings) and index them in a vector database (like ChromaDB or SQLite-vec extension) to support semantic plagiarism checks.

---

## 7. Downloader Middleware Pipeline (Inspired by Scrapy)
*   **Concept**: Scrapy uses Downloader Middlewares to globally intercept and modify HTTP requests before they are sent, and responses before they are returned to the crawl strategy.
*   **Application in our Crawler**:
    We can refactor our HTTP client in `utils.py` to route all fetches through a registered middleware stack. This decouples core request execution from auxiliary concerns like User-Agent rotation, proxy cycling, or logging:
    ```python
    class DownloaderMiddleware:
        def process_request(self, request_opts: dict) -> None:
            """Modify request options (headers, cookies, proxies) in-place."""
            pass

        def process_response(self, response) -> None:
            """Inspect or alter the fetched response before returning."""
            pass

    class UserAgentRotationMiddleware(DownloaderMiddleware):
        def process_request(self, request_opts: dict) -> None:
            request_opts["headers"]["User-Agent"] = get_random_user_agent()
    ```

---

## 8. Addon Event-Driven Lifecycle hooks (Inspired by mitmproxy)
*   **Concept**: Instead of rigid class inheritance, `mitmproxy` utilizes an "Addon" design where simple Python objects register event-listener hooks that the core engine calls during runtime transitions.
*   **Application in our Crawler**:
    We can define explicit hook execution points within `crawler_app.py` (e.g., `on_start`, `on_fetch_success`, `on_error`, `on_shutdown`). This allows developer extensions (like dynamic dashboard outputs, Slack notification integrations, or data filters) to be added without modifying the core crawler loop code:
    ```python
    class CrawlerAddonRegistry:
        def __init__(self):
            self.addons = []

        def trigger_event(self, event_name: str, *args, **kwargs):
            for addon in self.addons:
                if hasattr(addon, event_name):
                    getattr(addon, event_name)(*args, **kwargs)

    # Example Addon:
    class SlackAlertAddon:
        def on_error(self, url, exception):
            send_slack_message(f"Crawl error on {url}: {exception}")
    ```

---

## 9. Distributed Crawl Queue Scheduling (Inspired by scrapy-redis)
*   **Concept**: Moving scheduling state out of local memory or local SQLite databases into a centralized Redis server so that multiple independent scraper instances can run in parallel without duplicate fetches.
*   **Application in our Crawler**:
    Instead of checking and locking links via thread-local SQLite transactions, we can replace the feeder/worker queue mechanisms with **Redis**:
    - **Pending Queue**: Stored in a Redis List (`crawled_data:pending:<domain>`).
    - **Deduplication Set**: Stored in a Redis Set (`crawled_data:seen:<domain>`).
    This configuration allows us to run the crawler application on 10 separate servers concurrently. They will pull targets from the shared Redis instance, ensuring no two workers fetch the same URL.

---

## 10. Dynamic Browser Header Profile Spoofing (Inspired by Fake-Useragent & ScrapeOps)
*   **Concept**: Modern bot protection blocks request signatures that feature mismatching client properties (e.g., sending a Chrome User-Agent but omitting Chrome's unique client hints headers).
*   **Application in our Crawler**:
    Implement a header generation factory that constructs fully consistent HTTP header profiles based on the selected browser brand:
    ```python
    def generate_browser_headers(browser_type="chrome"):
        if browser_type == "chrome":
            return {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
                "Sec-Ch-Ua-Mobile": "?0",
                "Sec-Ch-Ua-Platform": '"Windows"',
                "Accept-Language": "el-GR,el;q=0.9,en-US;q=0.8,en;q=0.7",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"
            }
        # Similar profiles for firefox, safari, etc.
    ```

---

## 11. Third-Party Libraries for Direct Integration

These Python projects can be directly added as dependencies (`requirements.txt`) and integrated into our modular packages to implement advanced capabilities:

### A. Bot Protection & Cloudflare Bypass (`curl_cffi` or `tls-client`)
*   **How to use it in our project**:
    Instead of using standard Python `requests` sessions inside `utils.py` (which are easily fingerprinted by JA3 checkers), we can import `Session` from `curl_cffi.requests` to mimic real browser TLS profiles:
    ```python
    # Inside utils.py (or a new Downloader Middleware)
    from curl_cffi import requests as curl_requests

    def fetch_protected_page(url, headers, proxies):
        # Automatically impersonates a Chrome 120 client TLS handshake & HTTP/2 frame structure
        response = curl_requests.get(
            url,
            headers=headers,
            proxies=proxies,
            impersonate="chrome120",
            timeout=30
        )
        return response.text
    ```

### B. Heuristic & Machine Learning Content Parsers (`justext` & `extractnet`)
*   **How to use it in our project**:
    Register these libraries as concrete parsing strategies inside `extractors/engines.py`:
    *   **`justext`**: Excellent for extracting raw text from layout-heavy forum indexes and news sites with heavy sidebars.
    *   **`extractnet`**: A machine-learning approach that can be called when `newspaper3k` fails to identify author names or publication dates in atypical news structures:
        ```python
        # Inside extractors/engines.py
        import extractnet

        class ExtractNetEngine(BaseExtractor):
            def extract(self, html, url, **kwargs):
                # Run ML extraction models
                results = extractnet.extract_news(html)
                return {
                    "extracted_title": results.get("title"),
                    "extracted_text": results.get("content"),
                    "extracted_authors": ", ".join(results.get("authors", [])),
                    "extracted_date": results.get("date")
                }
        ```

### C. Lightweight Queue Workers (`RQ` - Redis Queue)
*   **How to use it in our project**:
    Instead of writing custom thread pool managers (`SiteCrawler` orchestrating feeder/worker loops), we can delegate task queuing to `RQ`:
    ```python
    # In crawler_app.py
    from redis import Redis
    from rq import Queue

    q = Queue(connection=Redis())

    def queue_crawl_job(url, site_config):
        # Enqueues the crawl job to be picked up by background worker processes
        q.enqueue(crawl_worker_job, url, site_config)
    ```

### D. Automated SQL Database Migrations (`yoyo-migrations`)
*   **How to use it in our project**:
    Integrate `yoyo` to manage schema alterations (like adding `mime_type` or new strategy tables) cleanly:
    - Create a `migrations/` directory containing SQL scripts (`0001_add_mime_type.sql`).
    - Run the migrations on crawler startup inside `database.py`'s database initialization logic.

### E. Asynchronous HTTP Client (`httpx`)
*   **How to use it in our project**:
    If migrating the project to an asynchronous paradigm to reduce OS thread overhead, we can integrate `httpx`:
    - Refactor `crawler_app.py` to use Python `asyncio` loop.
    - Replace standard synchronous connections inside `utils.py` with `httpx.AsyncClient()` and use `await client.get()` for fetching.

### F. Payload Validation and Modeling (`pydantic`)
*   **How to use it in our project**:
    Define strictly typed data models for our payload schemas:
    - Define models (e.g. `NewsArticleModel`, `SupermarketProductModel`) inside a new file `models.py`.
    - Validate crawler outputs inside content processors (e.g., `NewsContentProcessor.process_page`) before writing them to the SQLite database.

### G. Structured & Thread-Safe Logging (`loguru`)
*   **How to use it in our project**:
    Instead of configuring standard library `logging` file handlers dynamically for each worker thread, we can initialize `loguru`:
    - Clean up standard logging configurations in `crawler_app.py`.
    - Use `logger.add("logs/crawler_{time}.log", rotation="500 MB", retention="10 days")` which is fully thread-safe and handles rotation automatically.

---

## 12. Architectural Inspiration from Open-Source Projects

### A. PySpider (Web Crawling System)
*   **Inspiration**: PySpider teaches a multi-process queue architecture. Instead of running all tasks inside a single Python thread pool (orchestrated in `crawler_app.py`), the codebase can be split into three independent command-line apps communicating over a message broker (e.g. RabbitMQ/Redis):
    - **`scheduler.py`**: Reads pending links from DB and schedules runs.
    - **`fetcher.py`**: Executes network HTTP/JS rendering fetches.
    - **`processor.py`**: Parses downloaded content and saves text.
    *This eliminates global interpreter lock (GIL) bottlenecks completely.*

### B. Feedparser (RSS Feed Extraction)
*   **Inspiration**: Standardizing dates, times, and authorship from hundreds of disparate sites. `feedparser` implements extreme sanitization heuristics (handling 20+ date formats, unescaping broken HTML entities, and standardizing empty lists). We can adopt their formatting pipelines inside `extractors/generic.py` to guarantee clean database outputs regardless of target formatting quirks.

### C. Scrapy's AutoThrottle (Smart Rate Limiting)
*   **Inspiration**: Dynamic, latency-based delay adjustment. Instead of utilizing a static `--crawl-delay`, we can calculate a sliding average of the response latencies from target sites. If the response latency climbs, the crawler increases the delay dynamically to protect the server; if the latency is low, it safely reduces the delay toward a minimum threshold.
