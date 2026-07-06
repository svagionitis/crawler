import requests
import argparse
import logging
import time
import os
import json
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser
from database import init_db, save_links_to_db, update_link_in_db, \
    load_pending_links, get_database_name, is_database_empty, check_re_crawl
from utils import fetch_page, extract_links, compute_hash, ensure_directory_exists, extract_article_content
from config import USER_AGENT
from datetime import datetime
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

def get_log_file_name(domain, logs_dir):
    """Generate the log filename based on the domain and current datetime, and save it in the specified logs directory."""
    # Ensure the logs directory exists
    ensure_directory_exists(logs_dir)

    # Get the current datetime in a formatted string (e.g., 20231015143022)
    current_datetime = datetime.now().strftime("%Y%m%d%H%M%S")

    # Include the domain and datetime in the log filename
    return os.path.join(logs_dir, f"crawler_{domain}_{current_datetime}.log")

def initialize_crawler(start_url, respect_robots, crawl_delay, logs_dir, db_dir):
    """Initialize the crawler, including database, logging, and robots.txt parser.

    Returns:
        tuple: (database_name, robots_parser, crawl_delay, robots_delay_applied)
               robots_delay_applied is True when the crawl_delay was overridden by
               robots.txt, so callers can enforce single-threaded mode appropriately.
    """
    # Parse the domain
    domain = urlparse(start_url).netloc

    # Generate the database and log file names
    database_name = get_database_name(domain, db_dir)
    log_file_name = get_log_file_name(domain, logs_dir)

    # Configure logging with UTF-8 encoding (resetting handlers first to support multiple log targets)
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
        handler.close()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_file_name, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )

    # Initialize the database
    init_db(database_name)

    # Initialize robots.txt parser
    robots_parser = None
    robots_delay_applied = False
    if respect_robots:
        robots_parser = RobotFileParser()
        robots_url = urljoin(start_url, "/robots.txt")
        robots_content, robots_error_description = fetch_page(robots_url)
        if robots_error_description:
            logging.warning(f"Failed to fetch robots.txt: {robots_error_description}")
            return database_name, None, crawl_delay, False
        try:
            robots_parser.parse(robots_content.splitlines())
            # Use the crawl delay from robots.txt if available
            robots_crawl_delay = robots_parser.crawl_delay(USER_AGENT)
            if robots_crawl_delay is not None and robots_crawl_delay > crawl_delay:
                crawl_delay = robots_crawl_delay
                robots_delay_applied = True
                logging.info(f"Using crawl delay from robots.txt: {crawl_delay} seconds")
        except Exception as e:
            logging.warning(f"Failed to read robots.txt: {e}")

    return database_name, robots_parser, crawl_delay, robots_delay_applied

def prepare_crawl_queue(database_name, start_url, robots_parser, resume):
    """Seed the database queue with the start URL when not resuming.

    The queue is now entirely DB-backed; this function no longer returns a list.
    """
    if resume and not is_database_empty(database_name):
        logging.info(f"Resuming from existing database: {database_name}")
    else:
        logging.info(f"Starting fresh crawl from: {start_url}")
        save_links_to_db(database_name, urlparse(start_url).netloc, [start_url], robots_parser)

def crawl_page(database_name, current_url, robots_parser, no_duplicates,
               visited_hashes, visited_hashes_lock, re_crawl_time, parser_engine="auto"):
    """Crawl a single page, fetch content, check for duplicates, and save data.

    Args:
        visited_hashes_lock (threading.Lock): Acquired atomically around the
            hash check-and-add to prevent TOCTOU races in multi-threaded mode.
            Always provided; only contended when --no-duplicates is active.
    """
    # Check robots.txt
    if robots_parser and not robots_parser.can_fetch(USER_AGENT, current_url):
        logging.info(f"Skipping {current_url} due to robots.txt")
        return None, "skip"

    # Check if the link should be re-crawled
    if not check_re_crawl(database_name, current_url, re_crawl_time):
        logging.info(f"Link {current_url} was crawled recently. Updating date_inserted and setting status to pending.")
        save_links_to_db(database_name, urlparse(current_url).netloc, [current_url], robots_parser, status="pending")
        return None, "save"

    # Fetch the page
    logging.info(f"Crawling: {current_url}")
    content, error_description = fetch_page(current_url)
    if error_description:
        # Handle failure
        error_description_hash = compute_hash(error_description)
        update_link_in_db(database_name, current_url, error_description, error_description_hash, status="pending")
        logging.info(f"Failed to crawl {current_url}: {error_description}")
        return None, None

    # Compute hash and check for duplicates.
    # The lock makes the check-and-add atomic, preventing two threads from both
    # seeing a miss and both saving the same content (TOCTOU race).
    content_hash = compute_hash(content)
    if no_duplicates:
        with visited_hashes_lock:
            if content_hash in visited_hashes:
                logging.info(f"Skipping duplicate content: {current_url}")
                return None, None
            visited_hashes.add(content_hash)

    # Save content and mark as crawled
    is_html = ("<html" in content.lower() or "<body" in content.lower() or "<p" in content.lower() or "<div" in content.lower())
    if is_html:
        extracted = extract_article_content(content, url=current_url, engine=parser_engine)
    else:
        extracted = {"title": None, "text": None, "authors": None, "date": None, "keywords": None}

    update_link_in_db(
        database_name, current_url, content, content_hash, status="crawled",
        extracted_title=extracted["title"],
        extracted_text=extracted["text"],
        extracted_authors=extracted["authors"],
        extracted_date=extracted["date"],
        extracted_keywords=extracted["keywords"]
    )

    return content, None

def process_new_links(current_url, content, robots_parser):
    """Process new links extracted from a page and add them to the crawl queue."""
    new_links = extract_links(current_url, content, robots_parser)
    return new_links

def crawl_worker(database_name, current_url, robots_parser, no_duplicates,
                  visited_hashes, visited_hashes_lock, re_crawl_time,
                  domain, crawl_delay, parser_engine="auto"):
    """Fetch a single URL, save content, and enqueue discovered links.

    Designed to be submitted to a ThreadPoolExecutor. Each worker sleeps
    crawl_delay seconds after a real fetch so the effective request rate to
    the server equals crawl_delay / workers (auto-scaled by crawl_site).

    Returns:
        str: The URL that was processed, for logging in the caller.
    """
    content, action = crawl_page(
        database_name, current_url, robots_parser,
        no_duplicates, visited_hashes, visited_hashes_lock, re_crawl_time,
        parser_engine=parser_engine
    )
    if content and action is None:
        new_links = process_new_links(current_url, content, robots_parser)
        if new_links:
            save_links_to_db(database_name, domain, list(new_links), robots_parser)
    elif content is None and action:
        # Robot skip or re-crawl window — no network request was made, skip delay
        return current_url

    # Respect the crawl delay after every real network request
    logging.info(f"Waiting for {crawl_delay} seconds before the next request...")
    time.sleep(crawl_delay)
    return current_url

def crawl_site(start_url, respect_robots, no_duplicates, crawl_delay, resume,
               re_crawl_time, logs_dir, db_dir, batch_size, workers, parser_engine="auto"):
    """Crawl the site starting from the given URL."""
    # Initialize the crawler
    database_name, robots_parser, crawl_delay, robots_delay_applied = initialize_crawler(
        start_url, respect_robots, crawl_delay, logs_dir, db_dir
    )

    # Apply worker constraints and delay auto-scaling.
    # With N workers each sleeping D seconds, the server receives one request
    # every D/N seconds.  To maintain the user’s intended per-request interval,
    # scale the per-worker delay up by N so the aggregate rate stays the same.
    if workers > 1:
        if robots_delay_applied:
            logging.warning(
                f"robots.txt specifies a crawl delay of {crawl_delay}s. "
                f"Forcing --workers to 1 to honour it."
            )
            workers = 1
        else:
            scaled_delay = crawl_delay * workers
            logging.info(
                f"Scaling crawl delay from {crawl_delay}s to {scaled_delay}s "
                f"({workers} workers × {crawl_delay}s) to maintain server load."
            )
            crawl_delay = scaled_delay

    # Seed or resume the DB queue
    prepare_crawl_queue(database_name, start_url, robots_parser, resume)

    # Shared state for duplicate detection (lock prevents TOCTOU race)
    visited_hashes = set()
    visited_hashes_lock = threading.Lock()

    domain = urlparse(start_url).netloc

    # Pull pending links from the DB in bounded batches to keep memory usage flat.
    # The executor is re-created per batch so newly discovered links are picked
    # up by the next DB query before the next batch is dispatched.
    while True:
        batch = load_pending_links(database_name, limit=batch_size)
        if not batch:
            logging.info("No pending links remaining. Crawl complete.")
            break

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(
                    crawl_worker,
                    database_name=database_name,
                    current_url=url,
                    robots_parser=robots_parser,
                    no_duplicates=no_duplicates,
                    visited_hashes=visited_hashes,
                    visited_hashes_lock=visited_hashes_lock,
                    re_crawl_time=re_crawl_time,
                    domain=domain,
                    crawl_delay=crawl_delay,
                    parser_engine=parser_engine,
                ): url
                for url in batch
            }
            for future in as_completed(futures):
                url = futures[future]
                try:
                    future.result()
                except Exception as exc:
                    logging.error(f"Worker raised an exception for {url}: {exc}")

def main():
    """Main function to handle command-line arguments and start crawling."""
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
        crawl_site(
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
            parser_engine=args.parser,
        )
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

        # Build the per-site argument sets
        site_configs = []
        for site in config_data:
            site_configs.append({
                "start_url":     site["url"],
                "respect_robots": site.get("respect_robots", args.respect_robots),
                "no_duplicates":  site.get("no_duplicates",  args.no_duplicates),
                "crawl_delay":    site.get("crawl_delay",    args.crawl_delay),
                "resume":         site.get("resume",         args.resume),
                "re_crawl_time":  site.get("re_crawl_time",  args.re_crawl_time),
                "logs_dir":       site.get("logs_dir",       args.logs_dir),
                "db_dir":         site.get("db_dir",         args.db_dir),
                "batch_size":     site.get("batch_size",     args.batch_size),
                "workers":        site.get("workers",        args.workers),
                "parser_engine":  site.get("parser",         args.parser),
            })

        def _crawl_site_task(cfg):
            """Thread entry point: crawl one site and return its URL."""
            print(f"\n=== Starting crawl for: {cfg['start_url']} ===")
            try:
                crawl_site(**cfg)
            except (KeyboardInterrupt, SystemExit):
                raise
            except Exception as e:
                logging.error(
                    f"Failed to crawl site {cfg['start_url']}: {e}", exc_info=True
                )
            return cfg["start_url"]

        # Run all site crawls in parallel — each site has its own DB and log
        # file so there is no shared mutable state between threads at this level.
        print(f"\nLaunching {len(site_configs)} site crawl(s) in parallel...")
        with ThreadPoolExecutor(max_workers=len(site_configs)) as site_executor:
            site_futures = {
                site_executor.submit(_crawl_site_task, cfg): cfg["start_url"]
                for cfg in site_configs
            }
            for future in as_completed(site_futures):
                url = site_futures[future]
                try:
                    future.result()
                    print(f"\n=== Crawl finished for: {url} ===")
                except (KeyboardInterrupt, SystemExit):
                    print("\nCrawl execution interrupted by user. Exiting.")
                    raise
                except Exception as e:
                    logging.error(f"Unhandled error for {url}: {e}", exc_info=True)


if __name__ == "__main__":
    main()
