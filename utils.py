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

# Optional imports for advanced article text extraction
try:
    import trafilatura
    from trafilatura.metadata import extract_metadata as trafilatura_extract_metadata
    HAS_TRAFILATURA = True
except ImportError:
    HAS_TRAFILATURA = False

try:
    import newspaper
    HAS_NEWSPAPER = True
except ImportError:
    HAS_NEWSPAPER = False

def fetch_page(url, max_retries=3, initial_timeout=60, logger=None):
    """
    Fetch the content of a web page with retries and exponential backoff.

    Args:
        url (str): The URL to fetch.
        max_retries (int): Maximum number of retries (default: 3).
        initial_timeout (int): Initial timeout in seconds (default: 60).
        logger: Optional logger instance. Falls back to module-level logger.

    Returns:
        tuple: (content, error_description) where content is the page content or None,
               and error_description is an error message or None.
    """
    if logger is None:
        logger = logging.getLogger(__name__)
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
                    return None, error_description
            else:
                error_description = f"HTTP Error {status_code}: {e}"
                logger.error(f"Failed to fetch {url}: {error_description}")
                return None, error_description

        except requests.exceptions.Timeout as e:
            retry_count += 1
            if retry_count < max_retries:
                logger.warning(f"Timeout occurred for {url}. Retrying in {timeout} seconds... (Attempt {retry_count}/{max_retries})")
                time.sleep(timeout)  # Wait before retrying
                timeout *= 2  # Exponential backoff
            else:
                error_description = f"Timeout after {max_retries} retries: {e}"
                logger.error(f"Failed to fetch {url}: {error_description}")
                return None, error_description

        except requests.exceptions.RequestException as e:
            error_description = str(e)
            logger.error(f"Failed to fetch {url}: {error_description}")
            return None, error_description

    return None, "Max retries reached without success"

def extract_links(base_url, html_content, robots_parser, logger=None):
    """Extract all links from the HTML content that belong to the same domain and are allowed by robots.txt."""
    if logger is None:
        logger = logging.getLogger(__name__)
    soup = BeautifulSoup(html_content, "html.parser")
    links = set()
    for a_tag in soup.find_all("a", href=True):
        try:
            link = urljoin(base_url, a_tag["href"])
            if urlparse(link).netloc == urlparse(base_url).netloc:
                if not robots_parser or robots_parser.can_fetch(USER_AGENT, link):
                    links.add(link)
                else:
                    logger.info(f"Skipping disallowed link: {link}")
        except ValueError as e:
            logger.warning(f"Failed to extract href link: {a_tag['href']} ({e})")
    return links

def compute_hash(content):
    """Compute the SHA-256 hash of the content."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()

def ensure_directory_exists(directory, logger=None):
    """Ensure a directory exists. If not, create it."""
    if logger is None:
        logger = logging.getLogger(__name__)
    if not os.path.exists(directory):
        os.makedirs(directory)
        logger.info(f"Created directory: {directory}")

def extract_with_newspaper(html_content, url, logger=None):
    """Extract news article fields using newspaper3k."""
    import tempfile
    # newspaper3k does not create its own temp directory on Windows, which
    # causes a WinError 3 ("path not found") on first use.  Create it here
    # so the library can always find it — os.makedirs is a no-op if it
    # already exists.
    _newspaper_tmp = os.path.join(
        tempfile.gettempdir(), ".newspaper_scraper", "article_resources"
    )
    os.makedirs(_newspaper_tmp, exist_ok=True)

    from newspaper import Article
    article_url = url if url else "https://example.com"
    article = Article(article_url)
    article.set_html(html_content)
    article.parse()

    title = article.title
    text = article.text
    authors = ", ".join(article.authors) if article.authors else None

    date_str = None
    if article.publish_date:
        if hasattr(article.publish_date, "isoformat"):
            date_str = article.publish_date.isoformat()
        else:
            date_str = str(article.publish_date)

    keywords_str = None
    try:
        article.nlp()
        if article.keywords:
            keywords_str = ", ".join(article.keywords)
    except Exception:
        # Fallback to parsing meta keywords if punkt dataset is missing
        pass

    return title, text, authors, date_str, keywords_str

def extract_with_trafilatura(html_content, logger=None):
    """Extract news article fields using trafilatura."""
    text = trafilatura.extract(html_content, include_comments=False, no_fallback=False)

    metadata = None
    try:
        metadata = trafilatura_extract_metadata(html_content)
    except Exception:
        pass

    title = None
    authors = None
    date_str = None
    keywords_str = None

    if metadata:
        title = metadata.title
        authors = metadata.author
        date_str = metadata.date
        kws = []
        if metadata.categories:
            kws.extend(metadata.categories)
        if metadata.tags:
            kws.extend(metadata.tags)
        if kws:
            keywords_str = ", ".join(list(set(kws)))

    return title, text, authors, date_str, keywords_str

def extract_with_bs4(html_content, logger=None):
    """Extract news article fields using standard BeautifulSoup (boilerplate removal fallback)."""
    soup = BeautifulSoup(html_content, "html.parser")

    title = None
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
    if not title:
        h1 = soup.find("h1")
        if h1:
            title = h1.get_text(strip=True)

    authors = None
    author_meta = (
        soup.find("meta", attrs={"name": "author"}) or
        soup.find("meta", attrs={"property": "article:author"}) or
        soup.find("meta", attrs={"name": "twitter:creator"})
    )
    if author_meta and author_meta.get("content"):
        authors = author_meta["content"].strip()

    date_str = None
    date_meta = (
        soup.find("meta", attrs={"property": "article:published_time"}) or
        soup.find("meta", attrs={"name": "pubdate"}) or
        soup.find("meta", attrs={"name": "publish-date"}) or
        soup.find("meta", attrs={"property": "og:article:published_time"})
    )
    if date_meta and date_meta.get("content"):
        date_str = date_meta["content"].strip()

    keywords_str = None
    keywords_meta = (
        soup.find("meta", attrs={"name": "keywords"}) or
        soup.find("meta", attrs={"name": "news_keywords"})
    )
    if keywords_meta and keywords_meta.get("content"):
        keywords_str = keywords_meta["content"].strip()

    # Decompose boilerplate elements
    for element in soup(["script", "style", "nav", "footer", "header", "aside", "form", "iframe"]):
        element.decompose()

    text_blocks = []
    paragraphs = soup.find_all("p")
    if paragraphs:
        for p in paragraphs:
            p_text = p.get_text(strip=True)
            if len(p_text) > 10:
                text_blocks.append(p_text)
        text = "\n\n".join(text_blocks)
    else:
        text = soup.get_text("\n", strip=True)

    return title, text, authors, date_str, keywords_str

def extract_article_content(html_content, url=None, engine="auto", logger=None):
    """
    Extract the main content and metadata of an article from HTML.

    Args:
        html_content (str): The HTML content of the page.
        url (str | None): The URL of the page (helps newspaper3k identify details).
        engine (str): The parser engine ('auto', 'newspaper', 'trafilatura', 'bs4').
        logger: Optional logger instance. Falls back to module-level logger.

    Returns:
        dict: A dictionary containing title, text, authors, date, keywords, and
              parser_used (the name of the engine that actually ran the extraction).
    """
    if logger is None:
        logger = logging.getLogger(__name__)
    engine = engine.lower()

    if engine == "auto":
        if HAS_NEWSPAPER:
            engine = "newspaper"
        elif HAS_TRAFILATURA:
            engine = "trafilatura"
        else:
            engine = "bs4"

    title, text, authors, date_str, keywords_str = None, None, None, None, None
    # Tracks which engine actually ran so we can persist it in the DB.
    # Set after each successful extraction call; overwritten on fallback.
    actual_engine = None

    try:
        if engine == "newspaper":
            if HAS_NEWSPAPER:
                title, text, authors, date_str, keywords_str = extract_with_newspaper(html_content, url, logger=logger)
                actual_engine = "newspaper"
            else:
                logger.warning("newspaper3k is selected but not installed. Falling back to trafilatura or bs4.")
                if HAS_TRAFILATURA:
                    title, text, authors, date_str, keywords_str = extract_with_trafilatura(html_content, logger=logger)
                    actual_engine = "trafilatura"
                else:
                    title, text, authors, date_str, keywords_str = extract_with_bs4(html_content, logger=logger)
                    actual_engine = "bs4"

        elif engine == "trafilatura":
            if HAS_TRAFILATURA:
                title, text, authors, date_str, keywords_str = extract_with_trafilatura(html_content, logger=logger)
                actual_engine = "trafilatura"
            else:
                logger.warning("trafilatura is selected but not installed. Falling back to bs4.")
                title, text, authors, date_str, keywords_str = extract_with_bs4(html_content, logger=logger)
                actual_engine = "bs4"

        elif engine == "bs4":
            title, text, authors, date_str, keywords_str = extract_with_bs4(html_content, logger=logger)
            actual_engine = "bs4"

        else:
            logger.error(f"Unknown parser engine '{engine}'. Falling back to bs4.")
            title, text, authors, date_str, keywords_str = extract_with_bs4(html_content, logger=logger)
            actual_engine = "bs4"

    except Exception as e:
        logger.error(f"Error during content extraction with engine {engine}: {e}. Falling back to bs4.")
        try:
            title, text, authors, date_str, keywords_str = extract_with_bs4(html_content, logger=logger)
            actual_engine = "bs4"
        except Exception as e_fallback:
            logger.error(f"Critical error in fallback bs4 parser: {e_fallback}")
            actual_engine = None

    return {
        "title": title.strip() if title else None,
        "text": text.strip() if text else None,
        "authors": authors.strip() if authors else None,
        "date": date_str.strip() if date_str else None,
        "keywords": keywords_str.strip() if keywords_str else None,
        "parser_used": actual_engine,
    }
