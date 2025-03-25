from urllib.robotparser import RobotFileParser
import requests
import logging

class RobotsParser:
    def __init__(self, user_agent):
        self.user_agent = user_agent
        self.parser = RobotFileParser()

    def parse_robots_txt(self, robots_url, timeout=60):
        """Parse robots.txt and set the crawl delay if specified."""
        headers = {"User-Agent": self.user_agent}
        robots_content, robots_error_description = requests.get(robots_url, headers=headers, timeout=timeout)
        if robots_error_description:
            logging.warning(f"Failed to fetch robots.txt: {robots_error_description}")
            return False
        try:
            self.parser.parse(robots_content.splitlines())
            # Use the crawl delay from robots.txt if available
            robots_crawl_delay = self.parser.crawl_delay(self.user_agent)
            if robots_crawl_delay is not None and robots_crawl_delay > crawl_delay:
                crawl_delay = robots_crawl_delay
                logging.info(f"Using crawl delay from robots.txt: {crawl_delay} seconds")
        except Exception as e:
            logging.warning(f"Failed to read robots.txt: {e}")
            return False
        return True

    def can_fetch(self, url):
        """Check if a URL can be fetched based on robots.txt rules."""
        return self.parser.can_fetch(self.user_agent, url)
