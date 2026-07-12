from bs4 import BeautifulSoup
from utils import extract_links, extract_article_content, compute_hash
from database import is_duplicate_content, update_queue_link, get_connection
from datetime import datetime


class BaseContentProcessor:
    """Strategy interface for processing crawled pages."""

    def process_page(self, crawler, url: str, content: str, content_type: str) -> tuple:
        """
        Process page content, perform custom parsing/extraction, save payload data,
        and extract links for further crawling.

        Args:
            crawler: The crawler instance (for configuration/DB access).
            url (str): The fetched URL.
            content (str): The raw page content.
            content_type (str): The MIME type.

        Returns:
            tuple: (success_status, extracted_links, action_flag)
        """
        raise NotImplementedError


class NewsContentProcessor(BaseContentProcessor):
    """News-specific content processor that extracts article metadata and checks for plagiarism."""

    def __init__(self):
        # Keep track of initialized database names to run table creation queries only once per DB
        self._db_initialized = set()

    def _init_news_table(self, database_name):
        """Ensure the news_articles payload table exists in the target SQLite database."""
        if database_name in self._db_initialized:
            return
        conn = get_connection(database_name)
        with conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS news_articles (
                    link TEXT PRIMARY KEY,
                    extracted_title TEXT,
                    extracted_text TEXT,
                    extracted_authors TEXT,
                    extracted_date TEXT,
                    extracted_keywords TEXT,
                    parser_used TEXT,
                    FOREIGN KEY(link) REFERENCES crawled_data(link) ON DELETE CASCADE
                )
                """
            )
            conn.commit()
        self._db_initialized.add(database_name)

    def process_page(self, crawler, url: str, content: str, content_type: str) -> tuple:
        # Dynamically initialize news_articles table for this domain database
        self._init_news_table(crawler.database_name)

        # Check for duplicate content using the database index.
        content_hash = compute_hash(content)
        if crawler.no_duplicates and is_duplicate_content(
            crawler.database_name, content_hash, logger=crawler.logger
        ):
            crawler.logger.info(f"Skipping duplicate content: {url}")
            return None, set(), None

        # Detect HTML once using the Content-Type header or a limited prefix search of
        # the first 1000 characters, avoiding memory-intensive full-page string copies.
        is_html = (content_type and "html" in content_type) or (
            content
            and any(
                tag in content[:1000].lower()
                for tag in ("<html", "<body", "<p", "<div")
            )
        )
        soup = BeautifulSoup(content, "html.parser") if is_html else None

        # Extract links FIRST using the pre-parsed soup (non-destructive)
        new_links = (
            extract_links(
                url, content, crawler.robots_parser, soup=soup, logger=crawler.logger
            )
            if soup
            else set()
        )

        # Extract article content, passing the same soup so the bs4 path skips a redundant parse
        if is_html:
            extracted = extract_article_content(
                content,
                url=url,
                engine=crawler.parser_engine,
                soup=soup,
                normalize_whitespace=crawler.normalize_whitespace,
                logger=crawler.logger,
            )
        else:
            extracted = {
                "title": None,
                "text": None,
                "authors": None,
                "date": None,
                "keywords": None,
                "parser_used": None,
            }

        # Memory Optimization: Free the heavy BeautifulSoup parse tree immediately
        soup = None

        # Extract MIME type from content_type header (excluding charset properties)
        mime_type = content_type.split(";")[0].strip() if content_type else None

        # 1. Update core crawl queue status and raw HTML content cache
        success = update_queue_link(
            crawler.database_name,
            url,
            content,
            content_hash,
            status="crawled",
            mime_type=mime_type,
            logger=crawler.logger,
        )
        if not success:
            return False, set(), None

        # 2. Update/Insert news-specific metadata payload into the news_articles table
        conn = get_connection(crawler.database_name)
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO news_articles (link, extracted_title, extracted_text, extracted_authors, extracted_date, extracted_keywords, parser_used)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(link) DO UPDATE SET
                        extracted_title = excluded.extracted_title,
                        extracted_text = excluded.extracted_text,
                        extracted_authors = excluded.extracted_authors,
                        extracted_date = excluded.extracted_date,
                        extracted_keywords = excluded.extracted_keywords,
                        parser_used = excluded.parser_used
                    """,
                    (
                        url,
                        extracted["title"],
                        extracted["text"],
                        extracted["authors"],
                        extracted["date"],
                        extracted["keywords"],
                        extracted["parser_used"],
                    ),
                )
                conn.commit()
        except Exception as e:
            crawler.logger.error(
                f"Failed to save article payload to news_articles table: {e}"
            )

        # Memory Optimization: Free the raw content string immediately
        content_fetched = content is not None
        content = None

        if extracted.get("text"):
            try:
                # Check for plagiarism / near-duplicates against the central index
                matches = crawler.indexer.index_and_check(
                    url=url,
                    domain=crawler.domain,
                    title=extracted["title"] or "",
                    extracted_text=extracted["text"],
                    date_crawled=datetime.now(),
                    threshold=crawler.plagiarism_threshold,
                )
                for match in matches:
                    crawler.logger.warning(
                        f"🚨 Plagiarism/Duplicate Detected! {url} is "
                        f"{match['score']*100:.1f}% similar to {match['url']} ({match['title']})"
                    )
            except Exception as e:
                crawler.logger.error(f"Error checking similarity for {url}: {e}")

        return content_fetched, new_links, None


class SupermarketContentProcessor(BaseContentProcessor):
    """Supermarket-specific content processor to extract product metadata (pricing, name, SKU)."""

    def __init__(self):
        self._db_initialized = set()

    def _init_market_table(self, database_name):
        if database_name in self._db_initialized:
            return
        conn = get_connection(database_name)
        with conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS supermarket_products (
                    link TEXT PRIMARY KEY,
                    product_name TEXT,
                    price REAL,
                    sku TEXT,
                    category TEXT,
                    FOREIGN KEY(link) REFERENCES crawled_data(link) ON DELETE CASCADE
                )
                """
            )
            conn.commit()
        self._db_initialized.add(database_name)

    def process_page(self, crawler, url: str, content: str, content_type: str) -> tuple:
        self._init_market_table(crawler.database_name)

        content_hash = compute_hash(content)
        if crawler.no_duplicates and is_duplicate_content(
            crawler.database_name, content_hash, logger=crawler.logger
        ):
            crawler.logger.info(f"Skipping duplicate content: {url}")
            return None, set(), None

        is_html = (content_type and "html" in content_type) or (
            content
            and any(
                tag in content[:1000].lower()
                for tag in ("<html", "<body", "<p", "<div")
            )
        )
        soup = BeautifulSoup(content, "html.parser") if is_html else None
        new_links = (
            extract_links(
                url, content, crawler.robots_parser, soup=soup, logger=crawler.logger
            )
            if soup
            else set()
        )

        # Extract product details
        product_name = None
        price = None
        sku = None
        category = None

        if soup:
            import json

            # 1. Try parsing JSON-LD product markup
            for script in soup.find_all("script", type="application/ld+json"):
                try:
                    data = json.loads(script.string)
                    # Support list of schemas
                    items = data if isinstance(data, list) else [data]
                    for item in items:
                        if item.get("@type") == "Product":
                            product_name = item.get("name")
                            sku = item.get("sku") or item.get("mpn")
                            offers = item.get("offers")
                            if offers:
                                if isinstance(offers, list):
                                    offers = offers[0]
                                price_val = offers.get("price")
                                if price_val is not None:
                                    try:
                                        price = float(price_val)
                                    except ValueError:
                                        pass
                            category = item.get("category")
                            break
                except Exception:
                    pass

            # 2. Fallback to OpenGraph / Meta tags
            if not product_name:
                title_tag = soup.find("meta", property="og:title") or soup.find(
                    "meta", attrs={"name": "title"}
                )
                product_name = (
                    title_tag["content"]
                    if title_tag
                    else (soup.title.string if soup.title else None)
                )
            if price is None:
                price_tag = soup.find(
                    "meta", property="product:price:amount"
                ) or soup.find("meta", property="og:price:amount")
                if price_tag:
                    try:
                        price = float(price_tag["content"])
                    except ValueError:
                        pass
            if not sku:
                sku_tag = soup.find(
                    "meta", property="product:retailer_item_id"
                ) or soup.find("meta", attrs={"name": "sku"})
                sku = sku_tag["content"] if sku_tag else None

        soup = None

        # Extract MIME type from content_type header (excluding charset properties)
        mime_type = content_type.split(";")[0].strip() if content_type else None

        # 1. Update Core Queue
        success = update_queue_link(
            crawler.database_name,
            url,
            content,
            content_hash,
            status="crawled",
            mime_type=mime_type,
            logger=crawler.logger,
        )
        if not success:
            return False, set(), None

        # 2. Update Supermarket Payload
        conn = get_connection(crawler.database_name)
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO supermarket_products (link, product_name, price, sku, category)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(link) DO UPDATE SET
                        product_name = excluded.product_name,
                        price = excluded.price,
                        sku = excluded.sku,
                        category = excluded.category
                    """,
                    (url, product_name, price, sku, category),
                )
                conn.commit()
        except Exception as e:
            crawler.logger.error(f"Failed to save supermarket payload: {e}")

        return content is not None, new_links, None


class ForumContentProcessor(BaseContentProcessor):
    """Forum-specific content processor to extract discussion thread posts and authors."""

    def __init__(self):
        self._db_initialized = set()

    def _init_forum_table(self, database_name):
        if database_name in self._db_initialized:
            return
        conn = get_connection(database_name)
        with conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS forum_posts (
                    link TEXT PRIMARY KEY,
                    thread_title TEXT,
                    author TEXT,
                    post_content TEXT,
                    post_date TEXT,
                    FOREIGN KEY(link) REFERENCES crawled_data(link) ON DELETE CASCADE
                )
                """
            )
            conn.commit()
        self._db_initialized.add(database_name)

    def process_page(self, crawler, url: str, content: str, content_type: str) -> tuple:
        self._init_forum_table(crawler.database_name)

        content_hash = compute_hash(content)
        if crawler.no_duplicates and is_duplicate_content(
            crawler.database_name, content_hash, logger=crawler.logger
        ):
            crawler.logger.info(f"Skipping duplicate content: {url}")
            return None, set(), None

        is_html = (content_type and "html" in content_type) or (
            content
            and any(
                tag in content[:1000].lower()
                for tag in ("<html", "<body", "<p", "<div")
            )
        )
        soup = BeautifulSoup(content, "html.parser") if is_html else None
        new_links = (
            extract_links(
                url, content, crawler.robots_parser, soup=soup, logger=crawler.logger
            )
            if soup
            else set()
        )

        # Extract forum post details
        thread_title = None
        author = None
        post_content = None
        post_date = None

        if soup:
            import json

            # 1. Try parsing JSON-LD DiscussionForumPosting markup
            for script in soup.find_all("script", type="application/ld+json"):
                try:
                    data = json.loads(script.string)
                    items = data if isinstance(data, list) else [data]
                    for item in items:
                        if item.get("@type") in (
                            "DiscussionForumPosting",
                            "SocialMediaPosting",
                            "Comment",
                        ):
                            thread_title = item.get("headline") or item.get("name")
                            author_obj = item.get("author")
                            if author_obj:
                                author = (
                                    author_obj.get("name")
                                    if isinstance(author_obj, dict)
                                    else str(author_obj)
                                )
                            post_content = item.get("articleBody") or item.get("text")
                            post_date = item.get("datePublished")
                            break
                except Exception:
                    pass

            # 2. Fallback to basic HTML tags
            if not thread_title:
                thread_title = soup.title.string if soup.title else None
            if not post_content:
                # Find first paragraph text or general container
                p_tag = soup.find("p")
                post_content = p_tag.get_text().strip() if p_tag else None

        soup = None

        # Extract MIME type from content_type header (excluding charset properties)
        mime_type = content_type.split(";")[0].strip() if content_type else None

        # 1. Update Core Queue
        success = update_queue_link(
            crawler.database_name,
            url,
            content,
            content_hash,
            status="crawled",
            mime_type=mime_type,
            logger=crawler.logger,
        )
        if not success:
            return False, set(), None

        # 2. Update Forum Payload
        conn = get_connection(crawler.database_name)
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO forum_posts (link, thread_title, author, post_content, post_date)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(link) DO UPDATE SET
                        thread_title = excluded.thread_title,
                        author = excluded.author,
                        post_content = excluded.post_content,
                        post_date = excluded.post_date
                    """,
                    (url, thread_title, author, post_content, post_date),
                )
                conn.commit()
        except Exception as e:
            crawler.logger.error(f"Failed to save forum payload: {e}")

        return content is not None, new_links, None


def get_processor(processor_type: str) -> BaseContentProcessor:
    """Registry factory to return content processors based on a configuration string."""
    registry = {
        "news": NewsContentProcessor,
        "supermarket": SupermarketContentProcessor,
        "forum": ForumContentProcessor,
    }
    normalized = (processor_type or "news").strip().lower()
    if normalized not in registry:
        raise ValueError(
            f"Unknown processor type '{processor_type}'. Available options: {list(registry.keys())}"
        )
    return registry[normalized]()
