import time
from urllib.parse import urlparse
from utils import compute_hash
from DatabaseManager import DatabaseManager
from Logger import Logger
from PageFetcher import PageFetcher
from LinkExtractor import LinkExtractor
from RobotsParser import RobotsParser
from config import USER_AGENT


class Crawler:
    def __init__(self, start_url, respect_robots, no_duplicates, crawl_delay, resume, re_crawl_time, logs_dir, db_dir):
        self.start_url = start_url
        self.respect_robots = respect_robots
        self.no_duplicates = no_duplicates
        self.crawl_delay = crawl_delay
        self.resume = resume
        self.re_crawl_time = re_crawl_time
        self.logs_dir = logs_dir
        self.db_dir = db_dir

        self.domain = urlparse(start_url).netloc
        self.database_manager = DatabaseManager(db_dir, self.domain)
        self.logger = Logger(logs_dir, self.domain)
        self.page_fetcher = PageFetcher(USER_AGENT)
        self.link_extractor = LinkExtractor(USER_AGENT)
        self.robots_parser = RobotsParser(USER_AGENT) if respect_robots else None

    def start_crawling(self):
        """Start the crawling process."""
        to_crawl = self.prepare_crawl_queue()
        visited_hashes = set()

        while to_crawl:
            current_url = to_crawl.pop(0)
            self.crawl_page(current_url, visited_hashes)
            time.sleep(self.crawl_delay)

    def prepare_crawl_queue(self):
        """Prepare the queue of links to crawl, either from the database or the starting URL."""
        to_crawl = []
        if self.resume and not self.database_manager.is_database_empty():
            self.logger.log_info(f"Resuming from existing database: {self.database_manager.database_name}")
            to_crawl = self.database_manager.load_pending_links()
        else:
            to_crawl = [self.start_url]
            self.database_manager.save_links_to_db(self.domain, [self.start_url], self.robots_parser)
        return to_crawl

    def crawl_page(self, current_url, visited_hashes):
        """Crawl a single page, fetch content, check for duplicates, and save data."""
        if self.robots_parser and not self.robots_parser.can_fetch(current_url):
            self.logger.log_info(f"Skipping {current_url} due to robots.txt")
            return

        if not self.database_manager.check_re_crawl(current_url, self.re_crawl_time):
            self.logger.log_info(f"Link {current_url} was crawled recently. Updating date_inserted and setting status to pending.")
            self.database_manager.save_links_to_db(self.domain, [current_url], self.robots_parser, status="pending")
            return

        content, error_description = self.page_fetcher.fetch_page(current_url)
        if error_description:
            error_description_hash = compute_hash(error_description)
            self.database_manager.update_link_in_db(current_url, error_description, error_description_hash, status="pending")
            self.logger.log_info(f"Failed to crawl {current_url}: {error_description}")
            return

        content_hash = compute_hash(content)
        if self.no_duplicates and content_hash in visited_hashes:
            self.logger.log_info(f"Skipping duplicate content: {current_url}")
            return

        self.database_manager.update_link_in_db(current_url, content, content_hash, status="crawled")
        visited_hashes.add(content_hash)

        new_links = self.link_extractor.extract_links(current_url, content, self.robots_parser)
        self.database_manager.save_links_to_db(self.domain, new_links, self.robots_parser)
