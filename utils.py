import requests
import time
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import hashlib
import logging
from config import CrawlerConfig
import os
import base64
import certifi

from extractors import get_extractor

def fetch_page(url, max_retries=3, initial_timeout=60, proxies=None, session=None, logger=None):
    """
    Fetch the content of a web page with retries and exponential backoff.

    Args:
        url (str): The URL to fetch.
        max_retries (int): Maximum number of retries (default: 3).
        initial_timeout (int): Initial timeout in seconds (default: 60).
        proxies (dict): Optional dictionary mapping protocol to proxy URL.
        session: Optional requests.Session instance to reuse connections.
        logger: Optional logger instance. Falls back to module-level logger.

    Returns:
        tuple: (content, content_type, error_description) where content is the page content or None,
               content_type is the MIME type or None, and error_description is an error message or None.
    """
    if logger is None:
        logger = logging.getLogger(__name__)
    headers = {"User-Agent": CrawlerConfig().user_agent}
    retry_count = 0
    timeout = initial_timeout

    client = session if session is not None else requests

    while retry_count < max_retries:
        try:
            response = client.get(url, headers=headers, timeout=timeout, verify=certifi.where(), proxies=proxies)
            response.raise_for_status()

            # Check the Content-Type header
            content_type = response.headers.get("Content-Type", "").lower()

            if "text/" in content_type:
                 # Return text content as plain text
                return response.text, content_type, None
            else:
                 # Return binary content as Base64-encoded string
                return base64.b64encode(response.content).decode("utf-8"), content_type, None

        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code if e.response is not None else None
            if status_code == 504:  # Handle 504 Gateway Timeout
                retry_count += 1
                if retry_count < max_retries:
                    logger.warning(f"504 Gateway Timeout for {url}. Retrying in {timeout} seconds... (Attempt {retry_count}/{max_retries})")
                    time.sleep(timeout)  # Wait before retrying
                    timeout *= 2  # Exponential backoff
                else:
                    error_description = f"504 Gateway Timeout after {max_retries} retries: {e}"
                    logger.error(f"Failed to fetch {url}: {error_description}")
                    return None, None, error_description
            else:
                error_description = f"HTTP Error {status_code}: {e}"
                logger.error(f"Failed to fetch {url}: {error_description}")
                return None, None, error_description

        except requests.exceptions.Timeout as e:
            retry_count += 1
            if retry_count < max_retries:
                logger.warning(f"Timeout occurred for {url}. Retrying in {timeout} seconds... (Attempt {retry_count}/{max_retries})")
                time.sleep(timeout)  # Wait before retrying
                timeout *= 2  # Exponential backoff
            else:
                error_description = f"Timeout after {max_retries} retries: {e}"
                logger.error(f"Failed to fetch {url}: {error_description}")
                return None, None, error_description

        except requests.exceptions.SSLError as e:
            # Transient SSL failures (e.g. UNEXPECTED_EOF_WHILE_READING) — the
            # server dropped the connection during the TLS handshake or transfer.
            # These are retriable; hard certificate errors also surface here but
            # are unlikely to succeed on retry, so we still cap at max_retries.
            retry_count += 1
            if retry_count < max_retries:
                logger.warning(f"SSL error for {url}. Retrying in {timeout} seconds... (Attempt {retry_count}/{max_retries})")
                time.sleep(timeout)
                timeout *= 2
            else:
                error_description = f"SSL error after {max_retries} retries: {e}"
                logger.error(f"Failed to fetch {url}: {error_description}")
                return None, None, error_description

        except requests.exceptions.ConnectionError as e:
            # Server reset the connection, refused it, or the network dropped.
            # Typically transient — worth a few retries with backoff.
            retry_count += 1
            if retry_count < max_retries:
                logger.warning(f"Connection error for {url}. Retrying in {timeout} seconds... (Attempt {retry_count}/{max_retries})")
                time.sleep(timeout)
                timeout *= 2
            else:
                error_description = f"Connection error after {max_retries} retries: {e}"
                logger.error(f"Failed to fetch {url}: {error_description}")
                return None, None, error_description

        except requests.exceptions.RequestException as e:
            # Non-retriable errors (e.g. invalid URL, DNS resolution failure).
            error_description = str(e)
            logger.error(f"Failed to fetch {url}: {error_description}")
            return None, None, error_description


    return None, None, "Max retries reached without success"

def extract_links(base_url, html_content, robots_parser, soup=None, logger=None):
    """Extract all links from the HTML content that belong to the same domain and are allowed by robots.txt.

    Args:
        soup: Optional pre-parsed BeautifulSoup object.  When provided,
              ``html_content`` is not parsed again, eliminating a redundant
              pass through the HTML parser.
    """
    if logger is None:
        logger = logging.getLogger(__name__)
    if soup is None:
        soup = BeautifulSoup(html_content, "html.parser")
    base_netloc = urlparse(base_url).netloc  # hoisted outside the loop — urlparse is not free
    links = set()
    for a_tag in soup.find_all("a", href=True):
        try:
            link = urljoin(base_url, a_tag["href"])
            if urlparse(link).netloc == base_netloc:
                if not robots_parser or robots_parser.can_fetch(CrawlerConfig().user_agent, link):
                    links.add(link)
                else:
                    logger.info(f"Skipping disallowed link: {link}")
        except ValueError as e:
            logger.warning(f"Failed to extract href link: {a_tag['href']} ({e})")
    return links

def compute_hash(content):
    """Compute the SHA-256 hash of the content, chunking large strings to minimize peak memory usage."""
    h = hashlib.sha256()
    if isinstance(content, bytes):
        h.update(content)
    elif isinstance(content, str):
        # Encode in 64KB chunks to avoid duplicating the entire content string in memory
        chunk_size = 65536
        for i in range(0, len(content), chunk_size):
            h.update(content[i : i + chunk_size].encode("utf-8"))
    return h.hexdigest()

def ensure_directory_exists(directory, logger=None):
    """Ensure a directory exists. If not, create it."""
    if logger is None:
        logger = logging.getLogger(__name__)
    if not os.path.exists(directory):
        os.makedirs(directory)
        logger.info(f"Created directory: {directory}")

def extract_article_content(html_content, url=None, engine="auto", soup=None, normalize_whitespace=True, logger=None):
    """
    Extract the main content and metadata of an article from HTML.

    Delegates to the Strategy Pattern implementations in extractors.py.
    """
    extractor = get_extractor(engine)
    result = extractor.extract(html_content, url=url, soup=soup, logger=logger)

    if normalize_whitespace and result.get("text"):
        # Split on any whitespace sequence (spaces, tabs, newlines) and rejoin with a single space.
        result["text"] = " ".join(result["text"].split())

    return result
