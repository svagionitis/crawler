from bs4 import BeautifulSoup
from utils import extract_links, compute_hash
from database import is_duplicate_content, update_queue_link, get_connection
from datetime import datetime
from .base import BaseContentProcessor
from extractors import get_site_extractor


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
                    link TEXT PRIMARY KEY CHECK(length(link) > 0),
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

        # Route URL to the appropriate site extractor (or Generic fallback)
        if is_html:
            site_extractor = get_site_extractor(url)
            extracted = site_extractor.extract(
                content,
                url=url,
                soup=soup,
                parser_engine=crawler.parser_engine,
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
