
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import logging

class LinkExtractor:
    def __init__(self, user_agent):
        self.user_agent = user_agent

    def extract_links(self, base_url, html_content, robots_parser):
        """Extract all links from the HTML content that belong to the same domain and are allowed by robots.txt."""
        soup = BeautifulSoup(html_content, "html.parser")
        links = set()
        for a_tag in soup.find_all("a", href=True):
            link = urljoin(base_url, a_tag["href"])
            if urlparse(link).netloc == urlparse(base_url).netloc:
                if not robots_parser or robots_parser.can_fetch(self.user_agent, link):
                    links.add(link)
                else:
                    logging.info(f"Skipping disallowed link: {link}")
        return links
