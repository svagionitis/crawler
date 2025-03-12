import argparse
import hashlib
import logging
import sqlite3
import time
from datetime import datetime
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser
import os

import requests
from bs4 import BeautifulSoup

# User agent for the crawler
USER_AGENT = "Crawler/1.0 (+https://example.com/crawler)"

def get_database_name(domain):
    """Generate the database filename based on the domain."""
    return f"crawled_data_{domain}.db"

def get_log_file_name(domain):
    """Generate the log filename based on the domain."""
    return f"crawler_{domain}.log"

def init_db(database_name):
    """Initialize the SQLite database and create the table if it doesn't exist."""
    with sqlite3.connect(database_name) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS crawled_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                domain TEXT NOT NULL,
                date_inserted DATETIME NOT NULL,
                link TEXT NOT NULL,
                content TEXT,
                content_hash TEXT,
                status TEXT NOT NULL CHECK(status IN ('pending', 'crawled'))
            )
            """
        )
        conn.commit()

def save_link_to_db(database_name, domain, link, robots_parser, status="pending"):
    """Save a link to the database with a given status, if allowed by robots.txt."""
    if robots_parser and not robots_parser.can_fetch(USER_AGENT, link):
        logging.info(f"Skipping disallowed link: {link}")
        return

    try:
        with sqlite3.connect(database_name) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR IGNORE INTO crawled_data (domain, date_inserted, link, status)
                VALUES (?, ?, ?, ?)
                """,
                (domain, datetime.now(), link, status),
            )
            conn.commit()
            logging.info(f"Saved link to database: {link} (status: {status})")
    except sqlite3.Error as e:
        logging.error(f"Database error while saving link: {e}")

def update_link_in_db(database_name, link, content, content_hash):
    """Update a link in the database with content and hash, and mark it as crawled."""
    try:
        with sqlite3.connect(database_name) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE crawled_data
                SET content = ?, content_hash = ?, status = 'crawled'
                WHERE link = ?
                """,
                (content, content_hash, link),
            )
            conn.commit()
            logging.info(f"Updated link in database: {link}")
    except sqlite3.Error as e:
        logging.error(f"Database error while updating link: {e}")

def fetch_page(url):
    """Fetch the content of a web page."""
    headers = {"User-Agent": USER_AGENT}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to fetch {url}: {e}")
        return None

def extract_links(base_url, html_content, robots_parser):
    """Extract all links from the HTML content that belong to the same domain and are allowed by robots.txt."""
    soup = BeautifulSoup(html_content, "html.parser")
    links = set()
    for a_tag in soup.find_all("a", href=True):
        link = urljoin(base_url, a_tag["href"])
        if urlparse(link).netloc == urlparse(base_url).netloc:
            if not robots_parser or robots_parser.can_fetch(USER_AGENT, link):
                links.add(link)
            else:
                logging.info(f"Skipping disallowed link: {link}")
    return links

def compute_hash(content):
    """Compute the SHA-256 hash of the content."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()

def load_pending_links(database_name):
    """Load all pending links from the database."""
    pending_links = []
    try:
        with sqlite3.connect(database_name) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT link FROM crawled_data WHERE status = 'pending'")
            pending_links = [row[0] for row in cursor.fetchall()]
    except sqlite3.Error as e:
        logging.error(f"Failed to load pending links from database: {e}")
    return pending_links

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
        logging.error(f"Database not found: {database_name}. Cannot resume.")
        return

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
    if resume:
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