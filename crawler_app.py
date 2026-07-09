import requests
import argparse
import logging
import signal
import time
import os
import json
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser
from database import init_db, save_links_to_db, update_link_in_db, \
    load_pending_links, get_database_name, is_database_empty, \
    is_duplicate_content
from utils import fetch_page, extract_links, compute_hash, ensure_directory_exists, extract_article_content
from bs4 import BeautifulSoup
from config import USER_AGENT
from datetime import datetime
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

_active_crawlers = []
_active_crawlers_lock = threading.Lock()
_original_sigint_handler = None


def get_log_file_name(domain, logs_dir, logger=None):
    """Generate the log filename based on the domain and current datetime, and save it in the specified logs directory."""
    # Ensure the logs directory exists
    ensure_directory_exists(logs_dir, logger=logger)

    # Get the current datetime in a formatted string (e.g., 20231015143022)
    current_datetime = datetime.now().strftime("%Y%m%d%H%M%S")

    # Include the domain and datetime in the log filename
    return os.path.join(logs_dir, f"crawler_{domain}_{current_datetime}.log")


class SiteCrawler:
    """Encapsulates the state and crawl logic for a single domain website."""

    def __init__(self, start_url, respect_robots=True, no_duplicates=True,
                 crawl_delay=30, resume=False, re_crawl_time=3,
                 logs_dir="logs", db_dir="db", batch_size=100,
                 workers=1, parser_engine="auto"):
        self.start_url = start_url
        self.respect_robots = respect_robots
        self.no_duplicates = no_duplicates
        self.crawl_delay = crawl_delay
        self.resume = resume
        self.re_crawl_time = re_crawl_time
        self.logs_dir = logs_dir
        self.db_dir = db_dir
        self.batch_size = batch_size
        self.workers = workers
        self.parser_engine = parser_engine

        self.domain = urlparse(start_url).netloc
        self.database_name = get_database_name(self.domain, self.db_dir)
        self.robots_parser = None
        self.robots_delay_applied = False
        self.logger = None
        self.shutdown_event = threading.Event()

    def initialize(self):
        """Initialize the crawler: set up logging, database schemas, and robots.txt."""
        log_file_name = get_log_file_name(self.domain, self.logs_dir)

        # Create a per-domain named logger so parallel crawls write to separate files.
        self.logger = logging.getLogger(f"crawler.{self.domain}")
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False

        # Remove any stale handlers from a previous run (e.g. when resuming)
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
            handler.close()

        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

        file_handler = logging.FileHandler(log_file_name, encoding="utf-8")
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)

        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        self.logger.addHandler(stream_handler)

        # Initialize database schemas and indexes
        init_db(self.database_name, logger=self.logger)

        # Initialize robots.txt parser
        if self.respect_robots:
            self.robots_parser = RobotFileParser()
            robots_url = urljoin(self.start_url, "/robots.txt")
            robots_content, _, robots_error_description = fetch_page(robots_url, logger=self.logger)
            if robots_error_description:
                self.logger.warning(f"Failed to fetch robots.txt: {robots_error_description}")
                return
            try:
                self.robots_parser.parse(robots_content.splitlines())
                # Use the crawl delay from robots.txt if available
                robots_crawl_delay = self.robots_parser.crawl_delay(USER_AGENT)
                if robots_crawl_delay is not None and robots_crawl_delay > self.crawl_delay:
                    self.crawl_delay = robots_crawl_delay
                    self.robots_delay_applied = True
                    self.logger.info(f"Using crawl delay from robots.txt: {self.crawl_delay} seconds")
            except Exception as e:
                self.logger.warning(f"Failed to read robots.txt: {e}")

    def prepare_queue(self):
        """Seed the database queue with the start URL when not resuming."""
        if self.resume and not is_database_empty(self.database_name, logger=self.logger):
            self.logger.info(f"Resuming from existing database: {self.database_name}")
        else:
            self.logger.info(f"Starting fresh crawl from: {self.start_url}")
            save_links_to_db(self.database_name, self.domain, [self.start_url], self.robots_parser, re_crawl_time=self.re_crawl_time, logger=self.logger)

    def crawl_page(self, current_url):
        """Crawl a single page, fetch content, check for duplicates, and save data.

        Returns:
            tuple: (content, new_links, action)
        """
        # Check robots.txt
        if self.robots_parser and not self.robots_parser.can_fetch(USER_AGENT, current_url):
            self.logger.info(f"Skipping {current_url} due to robots.txt")
            return None, set(), "skip"

        # Fetch the page
        self.logger.info(f"Crawling: {current_url}")
        content, content_type, error_description = fetch_page(current_url, logger=self.logger)
        if error_description:
            # Handle failure
            error_description_hash = compute_hash(error_description)
            update_link_in_db(self.database_name, current_url, error_description, error_description_hash, status="pending", logger=self.logger)
            self.logger.info(f"Failed to crawl {current_url}: {error_description}")
            return None, set(), None

        # Check for duplicate content using the database index.
        content_hash = compute_hash(content)
        if self.no_duplicates and is_duplicate_content(self.database_name, content_hash, logger=self.logger):
            self.logger.info(f"Skipping duplicate content: {current_url}")
            return None, set(), None

        # Detect HTML once using the Content-Type header or a limited prefix search of
        # the first 1000 characters, avoiding memory-intensive full-page string copies.
        is_html = (content_type and "html" in content_type) or (
            content and any(tag in content[:1000].lower() for tag in ("<html", "<body", "<p", "<div"))
        )
        soup = BeautifulSoup(content, "html.parser") if is_html else None

        # Extract links FIRST using the pre-parsed soup (non-destructive)
        new_links = extract_links(current_url, content, self.robots_parser, soup=soup, logger=self.logger) if soup else set()

        # Extract article content, passing the same soup so the bs4 path skips a redundant parse
        if is_html:
            extracted = extract_article_content(content, url=current_url, engine=self.parser_engine, soup=soup, logger=self.logger)
        else:
            extracted = {"title": None, "text": None, "authors": None, "date": None, "keywords": None, "parser_used": None}

        update_link_in_db(
            self.database_name, current_url, content, content_hash, status="crawled",
            extracted_title=extracted["title"],
            extracted_text=extracted["text"],
            extracted_authors=extracted["authors"],
            extracted_date=extracted["date"],
            extracted_keywords=extracted["keywords"],
            parser_used=extracted["parser_used"],
            logger=self.logger
        )

        return content, new_links, None

    def crawl_worker(self, current_url):
        """Fetch a single URL, save content, and enqueue discovered links.

        Designed to be submitted to a ThreadPoolExecutor.
        """
        # Check for shutdown before starting work on this URL
        if self.shutdown_event.is_set():
            return current_url

        content, new_links, action = self.crawl_page(current_url)
        if content and action is None:
            if new_links:
                save_links_to_db(self.database_name, self.domain, list(new_links), self.robots_parser, re_crawl_time=self.re_crawl_time, logger=self.logger)
        elif content is None and action:
            # Robot skip — no network request was made, skip delay
            return current_url

        # Respect the crawl delay after every real network request.
        # Event.wait() blocks efficiently and wakes up instantly if a shutdown is requested.
        self.logger.info(f"Waiting for {self.crawl_delay} seconds before the next request...")
        self.shutdown_event.wait(self.crawl_delay)
        return current_url

    def crawl(self):
        """Crawl the site starting from the given URL."""
        # Register crawler instance for centralized shutdown
        with _active_crawlers_lock:
            _active_crawlers.append(self)

        try:
            self.initialize()
            self.prepare_queue()

            # Apply worker constraints and delay auto-scaling.
            if self.workers > 1:
                if self.robots_delay_applied:
                    self.logger.warning(
                        f"robots.txt specifies a crawl delay of {self.crawl_delay}s. "
                        f"Forcing --workers to 1 to honour it."
                    )
                    self.workers = 1
                else:
                    scaled_delay = self.crawl_delay * self.workers
                    self.logger.info(
                        f"Scaling crawl delay from {self.crawl_delay}s to {scaled_delay}s "
                        f"({self.workers} workers × {self.crawl_delay}s) to maintain server load."
                    )
                    self.crawl_delay = scaled_delay

            # Pull pending links from the DB in bounded batches to keep memory usage flat.
            while not self.shutdown_event.is_set():
                batch = load_pending_links(self.database_name, self.re_crawl_time, limit=self.batch_size, logger=self.logger)
                if not batch:
                    self.logger.info("No pending links remaining. Crawl complete.")
                    break

                with ThreadPoolExecutor(max_workers=self.workers) as executor:
                    futures = {
                        executor.submit(self.crawl_worker, url): url
                        for url in batch
                    }
                    for future in as_completed(futures):
                        url = futures[future]
                        try:
                            future.result()
                        except Exception as exc:
                            self.logger.error(f"Worker raised an exception for {url}: {exc}")

            if self.shutdown_event.is_set():
                self.logger.info("Shutdown requested. Crawl stopped gracefully.")

        finally:
            # Unregister crawler instance
            with _active_crawlers_lock:
                if self in _active_crawlers:
                    _active_crawlers.remove(self)


def _handle_sigint(signum, frame):
    """Handle Ctrl+C by setting the shutdown event on all active crawlers.

    The first Ctrl+C triggers a graceful shutdown — in-flight pages finish,
    no new work is started.  A second Ctrl+C restores the original handler
    and re-raises, causing an immediate (hard) exit.
    """
    global _original_sigint_handler

    already_shutting_down = False
    with _active_crawlers_lock:
        if _active_crawlers and all(c.shutdown_event.is_set() for c in _active_crawlers):
            already_shutting_down = True

    if already_shutting_down or not _active_crawlers:
        # Second Ctrl+C or no active crawlers — restore original handler and re-raise for hard exit
        signal.signal(signal.SIGINT, _original_sigint_handler)
        print("\nForced shutdown. Exiting immediately.")
        raise KeyboardInterrupt

    print("\nShutdown requested (Ctrl+C). Finishing in-flight pages … press Ctrl+C again to force quit.")
    with _active_crawlers_lock:
        for crawler in _active_crawlers:
            crawler.shutdown_event.set()


def main():
    """Main function to handle command-line arguments and start crawling."""
    global _original_sigint_handler
    _original_sigint_handler = signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT, _handle_sigint)
    parser = argparse.ArgumentParser(description="Crawl news sites and save data to SQLite.")
    parser.add_argument("--url", help="The URL of the news site to crawl.")
    parser.add_argument(
        "--config",
        type=str,
        help="Path to a JSON configuration file containing site crawl settings (array of objects format).",
    )
    parser.add_argument(
        "--respect-robots",
        action="store_true",
        help="Respect robots.txt when crawling.",
    )
    parser.add_argument(
        "--no-duplicates",
        action="store_true",
        help="Skip saving duplicate content.",
    )
    parser.add_argument(
        "--crawl-delay",
        type=int,
        default=30,
        help="Crawl delay in seconds (default: 30). If robots.txt specifies a delay, it will override this.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume crawling from an existing database.",
    )
    parser.add_argument(
        "--re-crawl-time",
        type=int,
        default=3,
        help="Time in hours after which a link should be re-crawled (default: 3).",
    )
    parser.add_argument(
        "--logs-dir",
        type=str,
        default="logs",
        help="Directory to save log files (default: logs).",
    )
    parser.add_argument(
        "--db-dir",
        type=str,
        default="db",
        help="Directory to save database files (default: db).",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Number of pending links to load from the database per batch (default: 100).",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help=(
            "Number of parallel worker threads (default: 1 = single-threaded). "
            "The crawl delay is automatically scaled by this factor so the "
            "effective request rate to the server remains unchanged. "
            "Forced to 1 when robots.txt specifies a Crawl-delay."
        ),
    )
    parser.add_argument(
        "--parser",
        type=str,
        default="auto",
        choices=["auto", "newspaper", "trafilatura", "bs4"],
        help=(
            "The content parsing engine to extract structured text & metadata. "
            "Options: 'auto' (tries newspaper, then trafilatura, then falls back to bs4), "
            "'newspaper' (uses newspaper3k), 'trafilatura' (uses trafilatura), "
            "'bs4' (uses BeautifulSoup fallback)."
        ),
    )
    args = parser.parse_args()

    # Validate mutual exclusivity of --url and --config
    if not args.url and not args.config:
        parser.error("one of the following arguments is required: --url or --config")
    if args.url and args.config:
        parser.error("arguments --url and --config are mutually exclusive")

    if args.url:
        # Start crawling the single URL
        crawler = SiteCrawler(
            start_url=args.url,
            respect_robots=args.respect_robots,
            no_duplicates=args.no_duplicates,
            crawl_delay=args.crawl_delay,
            resume=args.resume,
            re_crawl_time=args.re_crawl_time,
            logs_dir=args.logs_dir,
            db_dir=args.db_dir,
            batch_size=args.batch_size,
            workers=args.workers,
            parser_engine=args.parser
        )
        crawler.crawl()
    else:
        # Load and validate configuration file
        try:
            with open(args.config, "r", encoding="utf-8") as f:
                config_data = json.load(f)
        except Exception as e:
            parser.error(f"Failed to read or parse configuration file: {e}")

        if not isinstance(config_data, list):
            parser.error("Configuration file must contain a JSON array of objects.")

        for i, site in enumerate(config_data):
            if not isinstance(site, dict):
                parser.error(f"Item at index {i} in configuration file is not a JSON object.")
            if "url" not in site:
                parser.error(f"Item at index {i} in configuration file is missing the required 'url' field.")

        # Build the per-site crawler instances
        crawlers = []
        for site in config_data:
            crawler = SiteCrawler(
                start_url=site["url"],
                respect_robots=site.get("respect_robots", args.respect_robots),
                no_duplicates=site.get("no_duplicates", args.no_duplicates),
                crawl_delay=site.get("crawl_delay", args.crawl_delay),
                resume=site.get("resume", args.resume),
                re_crawl_time=site.get("re_crawl_time", args.re_crawl_time),
                logs_dir=site.get("logs_dir", args.logs_dir),
                db_dir=site.get("db_dir", args.db_dir),
                batch_size=site.get("batch_size", args.batch_size),
                workers=site.get("workers", args.workers),
                parser_engine=site.get("parser", args.parser)
            )
            crawlers.append(crawler)

        def _crawl_site_task(crawler_instance):
            """Thread entry point: crawl one site and return its URL."""
            print(f"\n=== Starting crawl for: {crawler_instance.start_url} ===")
            try:
                crawler_instance.crawl()
            except Exception as e:
                print(f"Failed to crawl site {crawler_instance.start_url}: {e}")
            return crawler_instance.start_url

        # Run all site crawls in parallel
        print(f"\nLaunching {len(crawlers)} site crawl(s) in parallel...")
        with ThreadPoolExecutor(max_workers=len(crawlers)) as site_executor:
            site_futures = {
                site_executor.submit(_crawl_site_task, crawler): crawler.start_url
                for crawler in crawlers
            }
            for future in as_completed(site_futures):
                url = site_futures[future]
                try:
                    future.result()
                    print(f"\n=== Crawl finished for: {url} ===")
                except (KeyboardInterrupt, SystemExit):
                    print("\nCrawl execution interrupted by user. Exiting.")
                    break
                except Exception as e:
                    print(f"Unhandled error for {url}: {e}")


if __name__ == "__main__":
    main()
