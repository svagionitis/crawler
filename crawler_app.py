import requests
import argparse
import logging
import time
import os
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser
from database import init_db, save_link_to_db, update_link_in_db, load_pending_links, get_database_name, is_database_empty
from utils import fetch_page, extract_links, compute_hash
from config import USER_AGENT

def get_log_file_name(domain):
    """Generate the log filename based on the domain."""
    return f"crawler_{domain}.log"

def crawl_site(start_url, respect_robots, no_duplicates, crawl_delay, resume):
    """Crawl the site starting from the given URL."""
    # Parse the domain
    domain = urlparse(start_url).netloc

    # Generate the database and log file names
    database_name = get_database_name(domain)
    log_file_name = get_log_file_name(domain)

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[logging.FileHandler(log_file_name), logging.StreamHandler()],
    )

    # Check if the database exists when resuming
    if resume and not os.path.exists(database_name):
        logging.warning(f"Database not found: {database_name}. Creating a new database and starting fresh.")

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
            if robots_crawl_delay is not None:
                crawl_delay = robots_crawl_delay
                logging.info(f"Using crawl delay from robots.txt: {crawl_delay} seconds")
        except Exception as e:
            logging.warning(f"Failed to read robots.txt: {e}")

    # Load pending links if resuming
    to_crawl = []
    # If we want to resume and the database is not empty, load pending links,
    # else start with the initial URL
    if resume and not is_database_empty(database_name):
        logging.info(f"Resuming from existing database: {database_name}")
        to_crawl = load_pending_links(database_name)
    else:
        # Start with the initial URL
        to_crawl = [start_url]
        save_link_to_db(database_name, domain, start_url, robots_parser)

    # Initialize visited hashes for duplicate detection
    visited_hashes = set()

    while to_crawl:
        current_url = to_crawl.pop(0)

        # Check robots.txt
        if respect_robots and not robots_parser.can_fetch(USER_AGENT, current_url):
            logging.info(f"Skipping {current_url} due to robots.txt")
            continue

        # Fetch the page
        logging.info(f"Crawling: {current_url}")
        content = fetch_page(current_url)
        if not content:
            continue

        # Compute hash and check for duplicates
        content_hash = compute_hash(content)
        if no_duplicates and content_hash in visited_hashes:
            logging.info(f"Skipping duplicate content: {current_url}")
            continue

        # Save content and mark as crawled
        update_link_in_db(database_name, current_url, content, content_hash)
        visited_hashes.add(content_hash)

        # Extract and save new links
        new_links = extract_links(current_url, content, robots_parser)
        for link in new_links:
            save_link_to_db(database_name, domain, link, robots_parser)

        # Add new links to the queue
        to_crawl.extend(new_links)

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
    args = parser.parse_args()

    # Start crawling
    crawl_site(args.url, args.respect_robots, args.no_duplicates, args.crawl_delay, args.resume)

if __name__ == "__main__":
    main()
