import requests
import argparse
import logging
import time
import os
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser
from database import init_db, save_link_to_db, update_link_in_db, \
    load_pending_links, get_database_name, is_database_empty, check_re_crawl
from utils import fetch_page, extract_links, compute_hash, ensure_directory_exists
from config import USER_AGENT
from datetime import datetime

def get_log_file_name(domain, logs_dir):
    """Generate the log filename based on the domain and current datetime, and save it in the specified logs directory."""
    # Ensure the logs directory exists
    ensure_directory_exists(logs_dir)

    # Get the current datetime in a formatted string (e.g., 20231015143022)
    current_datetime = datetime.now().strftime("%Y%m%d%H%M%S")

    # Include the domain and datetime in the log filename
    return os.path.join(logs_dir, f"crawler_{domain}_{current_datetime}.log")

def initialize_crawler(start_url, respect_robots, crawl_delay, logs_dir, db_dir):
    """Initialize the crawler, including database, logging, and robots.txt parser."""
    # Parse the domain
    domain = urlparse(start_url).netloc

    # Generate the database and log file names
    database_name = get_database_name(domain, db_dir)
    log_file_name = get_log_file_name(domain, logs_dir)

    # Configure logging with UTF-8 encoding
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
    if respect_robots:
        robots_parser = RobotFileParser()
        robots_url = urljoin(start_url, "/robots.txt")
        robots_content = requests.get(robots_url, timeout=10)
        try:
            robots_parser.parse(robots_content.text.splitlines())
            # Use the crawl delay from robots.txt if available
            robots_crawl_delay = robots_parser.crawl_delay(USER_AGENT)
            if robots_crawl_delay is not None and robots_crawl_delay > crawl_delay:
                crawl_delay = robots_crawl_delay
                logging.info(f"Using crawl delay from robots.txt: {crawl_delay} seconds")
        except Exception as e:
            logging.warning(f"Failed to read robots.txt: {e}")

    return database_name, robots_parser, crawl_delay

def prepare_crawl_queue(database_name, start_url, robots_parser, resume):
    """Prepare the queue of links to crawl, either from the database or the starting URL."""
    to_crawl = []
    # If we want to resume and the database is not empty, load pending links,
    # else start with the initial URL
    if resume and not is_database_empty(database_name):
        logging.info(f"Resuming from existing database: {database_name}")
        to_crawl = load_pending_links(database_name)
    else:
        # Start with the initial URL
        to_crawl = [start_url]
        save_link_to_db(database_name, urlparse(start_url).netloc, start_url, robots_parser)

    return to_crawl

def crawl_page(database_name, current_url, robots_parser, no_duplicates, visited_hashes, re_crawl_time):
    """Crawl a single page, fetch content, check for duplicates, and save data."""
    # Check robots.txt
    if robots_parser and not robots_parser.can_fetch(USER_AGENT, current_url):
        logging.info(f"Skipping {current_url} due to robots.txt")
        return ""

    # Check if the link should be re-crawled
    if not check_re_crawl(database_name, current_url, re_crawl_time):
        logging.info(f"Link {current_url} was crawled recently. Updating date_inserted and setting status to pending.")
        save_link_to_db(database_name, urlparse(current_url).netloc, current_url, robots_parser, status="pending")
        return ""

    # Fetch the page
    logging.info(f"Crawling: {current_url}")
    content, error_description = fetch_page(current_url)
    if error_description:
        # Handle failure
        error_description_hash = compute_hash(error_description)
        update_link_in_db(database_name, current_url, error_description, error_description_hash, status="pending")
        logging.info(f"Failed to crawl {current_url}: {error_description}")
        return None

    # Compute hash and check for duplicates
    content_hash = compute_hash(content)
    if no_duplicates and content_hash in visited_hashes:
        logging.info(f"Skipping duplicate content: {current_url}")
        return None

    # Save content and mark as crawled
    update_link_in_db(database_name, current_url, content, content_hash, status="crawled")
    visited_hashes.add(content_hash)

    return content

def process_new_links(database_name, current_url, content, robots_parser):
    """Process new links extracted from a page and add them to the crawl queue."""
    new_links = extract_links(current_url, content, robots_parser)
    for link in new_links:
        save_link_to_db(database_name, urlparse(current_url).netloc, link, robots_parser)
    return new_links

def crawl_site(start_url, respect_robots, no_duplicates, crawl_delay, resume, re_crawl_time, logs_dir, db_dir):
    """Crawl the site starting from the given URL."""
    # Initialize the crawler
    database_name, robots_parser, crawl_delay = initialize_crawler(start_url, respect_robots, crawl_delay, logs_dir, db_dir)

    # Prepare the crawl queue
    to_crawl = prepare_crawl_queue(database_name, start_url, robots_parser, resume)

    # Initialize visited hashes for duplicate detection
    visited_hashes = set()

    while to_crawl:
        current_url = to_crawl.pop(0)

        # Crawl the page
        content = crawl_page(database_name, current_url, robots_parser, no_duplicates, visited_hashes, re_crawl_time)
        if content:
            # Process new links
            new_links = process_new_links(database_name, current_url, content, robots_parser)
            to_crawl.extend(new_links)
        elif not content:
            # If the page was not crawled successfully, because of the robot rules or the re-crawl time, then get the next link to crawl
            # without waiting for the crawl delay
            continue

        # Respect the crawl delay
        logging.info(f"Waiting for {crawl_delay} seconds before the next request...")
        time.sleep(crawl_delay)

def main():
    """Main function to handle command-line arguments and start crawling."""
    parser = argparse.ArgumentParser(description="Crawl a news site and save data to SQLite.")
    parser.add_argument("--url", required=True, help="The URL of the news site to crawl.")
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
    args = parser.parse_args()

    # Start crawling
    crawl_site(args.url, args.respect_robots, args.no_duplicates, args.crawl_delay,
               args.resume, args.re_crawl_time, args.logs_dir, args.db_dir)

if __name__ == "__main__":
    main()
