import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import hashlib
import logging
from config import USER_AGENT
import os
import base64

def fetch_page(url):
    """Fetch the content of a web page."""
    headers = {"User-Agent": USER_AGENT}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        # Check the Content-Type header
        content_type = response.headers.get("Content-Type", "").lower()

        if "text/html" in content_type:
            # Return HTML content as text
            return response.text, None
        else:
             # Return binary content as Base64-encoded string
            return base64.b64encode(response.content).decode("utf-8"), None

    except requests.exceptions.RequestException as e:
        error_description = str(e)
        logging.error(f"Failed to fetch {url}: {error_description}")
        return None, error_description  # Return no content and error description

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

def ensure_directory_exists(directory):
    """Ensure a directory exists. If not, create it."""
    if not os.path.exists(directory):
        os.makedirs(directory)
        logging.info(f"Created directory: {directory}")
