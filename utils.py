import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import hashlib
import logging
from config import USER_AGENT

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
