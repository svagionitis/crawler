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


def detects_javascript_required(html_content: str, logger=None) -> bool:
    """
    Detects if a page requires JavaScript to render content.
    Checks for:
    - Empty SPA entry points combined with script tags.
    - Noscript warnings asking to enable JavaScript.
    """
    if not html_content:
        return False
    try:
        soup = BeautifulSoup(html_content, "html.parser")

        # Check noscript warning tags
        noscript_tags = soup.find_all("noscript")
        for ns in noscript_tags:
            text = ns.get_text().lower()
            if "javascript" in text and any(
                x in text for x in ["enable", "required", "turn on", "support", "need"]
            ):
                if logger:
                    logger.info(
                        "Auto-detected JavaScript required based on <noscript> tag contents."
                    )
                return True

        # Check for empty client-side rendering target (e.g. root, app) with script tags
        body = soup.body
        if body:
            body_text = body.get_text().strip()
            words = body_text.split()
            scripts = soup.find_all("script")
            if len(words) < 35 and len(scripts) >= 2:
                target_divs = soup.find_all(
                    "div", id=["root", "app", "__next", "app-root", "react-root"]
                )
                if target_divs:
                    if logger:
                        logger.info(
                            "Auto-detected JavaScript required: SPA container found with minimal static text."
                        )
                    return True
    except Exception as e:
        if logger:
            logger.warning(f"Error parsing HTML for JS auto-detection: {e}")
    return False


def fetch_page(
    url,
    max_retries=3,
    initial_timeout=60,
    proxies=None,
    session=None,
    logger=None,
    js_rendering=False,
    js_driver="auto",
    auto_detect_js=True,
):
    """
    Fetch the content of a web page with retries and exponential backoff.
    Optionally renders JS using Playwright, Selenium, or Puppeteer.

    Args:
        url (str): The URL to fetch.
        max_retries (int): Maximum number of retries (default: 3).
        initial_timeout (int): Initial timeout in seconds (default: 60).
        proxies (dict): Optional dictionary mapping protocol to proxy URL.
        session: Optional requests.Session instance to reuse connections.
        logger: Optional logger instance. Falls back to module-level logger.
        js_rendering (bool): Force rendering with JavaScript.
        js_driver (str): Browser engine to use if js_rendering is True.
        auto_detect_js (bool): Dynamically upgrade to JS rendering if page appears JS-dependent.

    Returns:
        tuple: (content, content_type, error_description) where content is the page content or None,
               content_type is the MIME type or None, and error_description is an error message or None.
    """
    if logger is None:
        logger = logging.getLogger(__name__)

    # If JS rendering is forced
    if js_rendering:
        try:
            from rendering import render_page

            logger.info(f"Using dynamic browser rendering ({js_driver}) for {url}")
            content = render_page(
                url,
                driver_type=js_driver,
                timeout_secs=initial_timeout,
                proxies=proxies,
            )
            return content, "text/html", None
        except Exception as e:
            logger.error(f"Dynamic browser rendering failed for {url}: {e}")
            return None, None, str(e)

    headers = {"User-Agent": CrawlerConfig().user_agent}
    retry_count = 0
    timeout = initial_timeout

    client = session if session is not None else requests

    while retry_count < max_retries:
        try:
            response = client.get(
                url,
                headers=headers,
                timeout=timeout,
                verify=certifi.where(),
                proxies=proxies,
            )
            response.raise_for_status()

            # Check the Content-Type header
            content_type = response.headers.get("Content-Type", "").lower()

            if (
                "text/" in content_type
                or "xml" in content_type
                or "json" in content_type
            ):
                html_text = response.text
                if auto_detect_js and "text/html" in content_type:
                    if detects_javascript_required(html_text, logger=logger):
                        logger.info(
                            f"Upgrading to dynamic rendering for {url} due to detected JS requirement."
                        )
                        try:
                            from rendering import render_page

                            rendered_content = render_page(
                                url,
                                driver_type=js_driver,
                                timeout_secs=initial_timeout,
                                proxies=proxies,
                            )
                            return rendered_content, "text/html", None
                        except Exception as render_err:
                            logger.warning(
                                f"Dynamic rendering upgrade failed for {url}, falling back to static text. Error: {render_err}"
                            )
                return html_text, content_type, None
            else:
                # Return binary content as Base64-encoded string
                return (
                    base64.b64encode(response.content).decode("utf-8"),
                    content_type,
                    None,
                )

        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code if e.response is not None else None
            if status_code == 504:  # Handle 504 Gateway Timeout
                retry_count += 1
                if retry_count < max_retries:
                    logger.warning(
                        f"504 Gateway Timeout for {url}. Retrying in {timeout} seconds... (Attempt {retry_count}/{max_retries})"
                    )
                    time.sleep(timeout)  # Wait before retrying
                    timeout *= 2  # Exponential backoff
                else:
                    error_description = (
                        f"504 Gateway Timeout after {max_retries} retries: {e}"
                    )
                    logger.error(f"Failed to fetch {url}: {error_description}")
                    return None, None, error_description
            else:
                error_description = f"HTTP Error {status_code}: {e}"
                logger.error(f"Failed to fetch {url}: {error_description}")
                return None, None, error_description

        except requests.exceptions.Timeout as e:
            retry_count += 1
            if retry_count < max_retries:
                logger.warning(
                    f"Timeout occurred for {url}. Retrying in {timeout} seconds... (Attempt {retry_count}/{max_retries})"
                )
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
                logger.warning(
                    f"SSL error for {url}. Retrying in {timeout} seconds... (Attempt {retry_count}/{max_retries})"
                )
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
                logger.warning(
                    f"Connection error for {url}. Retrying in {timeout} seconds... (Attempt {retry_count}/{max_retries})"
                )
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
    """Extract all links from the HTML content, sitemaps, or RSS feeds that belong to the same domain and are allowed by robots.txt.

    Args:
        soup: Optional pre-parsed BeautifulSoup object.  When provided,
              ``html_content`` is not parsed again, eliminating a redundant
              pass through the HTML parser.
    """
    if logger is None:
        logger = logging.getLogger(__name__)

    base_netloc = urlparse(
        base_url
    ).netloc  # hoisted outside the loop — urlparse is not free
    links = set()

    if not html_content:
        return links

    # 1. Detect and parse XML (Sitemaps, RSS, and Atom feeds)
    trimmed_content = html_content.strip()
    if (
        trimmed_content.startswith("<?xml")
        or trimmed_content.startswith("<urlset")
        or trimmed_content.startswith("<sitemapindex")
        or trimmed_content.startswith("<rss")
        or trimmed_content.startswith("<feed")
    ):
        try:
            import xml.etree.ElementTree as ET

            root = ET.fromstring(html_content.encode("utf-8", errors="ignore"))
            for elem in root.iter():
                tag_local = elem.tag.split("}")[-1]
                raw_link = None
                if tag_local == "loc":
                    raw_link = elem.text
                elif tag_local == "link":
                    # Atom uses <link href="...">, RSS uses <link>...</link>
                    raw_link = elem.attrib.get("href") or elem.text

                if raw_link:
                    raw_link = raw_link.strip()
                    try:
                        link = urljoin(base_url, raw_link)
                        if urlparse(link).netloc == base_netloc:
                            if not robots_parser or robots_parser.can_fetch(
                                CrawlerConfig().user_agent, link
                            ):
                                links.add(link)
                            else:
                                logger.info(f"Skipping disallowed link: {link}")
                    except ValueError as e:
                        logger.warning(
                            f"Failed to parse XML feed/sitemap link: {raw_link} ({e})"
                        )
            return links
        except Exception as xml_err:
            logger.warning(
                f"Failed to parse content as XML: {xml_err}. Falling back to HTML parser."
            )

    # 2. Parse HTML content
    if soup is None:
        soup = BeautifulSoup(html_content, "html.parser")

    # Extract standard anchor tags
    for a_tag in soup.find_all("a", href=True):
        try:
            link = urljoin(base_url, a_tag["href"])
            if urlparse(link).netloc == base_netloc:
                if not robots_parser or robots_parser.can_fetch(
                    CrawlerConfig().user_agent, link
                ):
                    links.add(link)
                else:
                    logger.info(f"Skipping disallowed link: {link}")
        except ValueError as e:
            logger.warning(f"Failed to extract href link: {a_tag['href']} ({e})")

    # Extract document links (<link href="...">) excluding styles, icons, and preloads
    for link_tag in soup.find_all("link", href=True):
        rel = link_tag.get("rel", [])
        if isinstance(rel, str):
            rel = [rel]
        if any(
            r.lower()
            in ("stylesheet", "icon", "shortcut icon", "preload", "dns-prefetch")
            for r in rel
        ):
            continue
        try:
            link = urljoin(base_url, link_tag["href"])
            if urlparse(link).netloc == base_netloc:
                if not robots_parser or robots_parser.can_fetch(
                    CrawlerConfig().user_agent, link
                ):
                    links.add(link)
                else:
                    logger.info(f"Skipping disallowed link: {link}")
        except ValueError as e:
            logger.warning(f"Failed to extract <link> tag: {link_tag['href']} ({e})")

    # Extract scripts (<script src="...">)
    for script_tag in soup.find_all("script", src=True):
        try:
            link = urljoin(base_url, script_tag["src"])
            if urlparse(link).netloc == base_netloc:
                if not robots_parser or robots_parser.can_fetch(
                    CrawlerConfig().user_agent, link
                ):
                    links.add(link)
                else:
                    logger.info(f"Skipping disallowed link: {link}")
        except ValueError as e:
            logger.warning(f"Failed to extract script src: {script_tag['src']} ({e})")

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


def extract_article_content(
    html_content,
    url=None,
    engine="auto",
    soup=None,
    normalize_whitespace=True,
    logger=None,
):
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
