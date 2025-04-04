import requests
import time
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import hashlib
import logging
from config import USER_AGENT
import os
import base64
import certifi

def fetch_page(url, max_retries=3, initial_timeout=60):
    """
    Fetch the content of a web page with retries and exponential backoff.

    Args:
        url (str): The URL to fetch.
        max_retries (int): Maximum number of retries (default: 3).
        initial_timeout (int): Initial timeout in seconds (default: 60).

    Returns:
        tuple: (content, error_description) where content is the page content or None,
               and error_description is an error message or None.
    """
    headers = {"User-Agent": USER_AGENT}
    retry_count = 0
    timeout = initial_timeout

    while retry_count < max_retries:
        try:
            response = requests.get(url, headers=headers, timeout=timeout, verify=certifi.where())
            response.raise_for_status()

            # Check the Content-Type header
            content_type = response.headers.get("Content-Type", "").lower()

            if "text/" in content_type:
                 # Return text content as plain text
                return response.text, None
            else:
                # Return binary content as Base64-encoded string
                return base64.b64encode(response.content).decode("utf-8"), None

        except requests.exceptions.HTTPError as e:
            if response.status_code == 504:  # Handle 504 Gateway Timeout
                retry_count += 1
                if retry_count < max_retries:
                    logging.warning(f"504 Gateway Timeout for {url}. Retrying in {timeout} seconds... (Attempt {retry_count}/{max_retries})")
                    time.sleep(timeout)  # Wait before retrying
                    timeout *= 2  # Exponential backoff
                else:
                    error_description = f"504 Gateway Timeout after {max_retries} retries: {e}"
                    logging.error(f"Failed to fetch {url}: {error_description}")
                    return None, error_description
            else:
                error_description = f"HTTP Error {response.status_code}: {e}"
                logging.error(f"Failed to fetch {url}: {error_description}")
                return None, error_description

        except requests.exceptions.Timeout as e:
            retry_count += 1
            if retry_count < max_retries:
                logging.warning(f"Timeout occurred for {url}. Retrying in {timeout} seconds... (Attempt {retry_count}/{max_retries})")
                time.sleep(timeout)  # Wait before retrying
                timeout *= 2  # Exponential backoff
            else:
                error_description = f"Timeout after {max_retries} retries: {e}"
                logging.error(f"Failed to fetch {url}: {error_description}")
                return None, error_description

        except requests.exceptions.RequestException as e:
            error_description = str(e)
            logging.error(f"Failed to fetch {url}: {error_description}")
            return None, error_description

    return None, "Max retries reached without success"

def extract_links(base_url, html_content, robots_parser):
    """Extract all links from the HTML content that belong to the same domain and are allowed by robots.txt."""
    soup = BeautifulSoup(html_content, "html.parser")
    links = set()
    for a_tag in soup.find_all("a", href=True):
        try:
            link = urljoin(base_url, a_tag["href"])
            if urlparse(link).netloc == urlparse(base_url).netloc:
                if not robots_parser or robots_parser.can_fetch(USER_AGENT, link):
                    links.add(link)
                else:
                    logging.info(f"Skipping disallowed link: {link}")
        except ValueError as e:
            logging.warning(f"Failed to extract href link: {a_tag["href"]} ({e})")
    return links

def compute_hash(content):
    """Compute the SHA-256 hash of the content."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()

def ensure_directory_exists(directory):
    """Ensure a directory exists. If not, create it."""
    if not os.path.exists(directory):
        os.makedirs(directory)
        logging.info(f"Created directory: {directory}")
