from bs4 import BeautifulSoup
from utils import extract_links, extract_article_content, compute_hash
from database import is_duplicate_content, update_link_in_db
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

    def process_page(self, crawler, url: str, content: str, content_type: str) -> tuple:
        # Check for duplicate content using the database index.
        content_hash = compute_hash(content)
        if crawler.no_duplicates and is_duplicate_content(crawler.database_name, content_hash, logger=crawler.logger):
            crawler.logger.info(f"Skipping duplicate content: {url}")
            return None, set(), None

        # Detect HTML once using the Content-Type header or a limited prefix search of
        # the first 1000 characters, avoiding memory-intensive full-page string copies.
        is_html = (content_type and "html" in content_type) or (
            content and any(tag in content[:1000].lower() for tag in ("<html", "<body", "<p", "<div"))
        )
        soup = BeautifulSoup(content, "html.parser") if is_html else None

        # Extract links FIRST using the pre-parsed soup (non-destructive)
        new_links = extract_links(url, content, crawler.robots_parser, soup=soup, logger=crawler.logger) if soup else set()

        # Extract article content, passing the same soup so the bs4 path skips a redundant parse
        if is_html:
            extracted = extract_article_content(
                content,
                url=url,
                engine=crawler.parser_engine,
                soup=soup,
                normalize_whitespace=crawler.normalize_whitespace,
                logger=crawler.logger
            )
        else:
            extracted = {"title": None, "text": None, "authors": None, "date": None, "keywords": None, "parser_used": None}

        # Memory Optimization: Free the heavy BeautifulSoup parse tree immediately
        soup = None

        update_link_in_db(
            crawler.database_name, url, content, content_hash, status="crawled",
            extracted_title=extracted["title"],
            extracted_text=extracted["text"],
            extracted_authors=extracted["authors"],
            extracted_date=extracted["date"],
            extracted_keywords=extracted["keywords"],
            parser_used=extracted["parser_used"],
            logger=crawler.logger
        )

        # Memory Optimization: Free the raw content string immediately after saving it to the DB
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
                    threshold=crawler.plagiarism_threshold
                )
                for match in matches:
                    crawler.logger.warning(
                        f"🚨 Plagiarism/Duplicate Detected! {url} is "
                        f"{match['score']*100:.1f}% similar to {match['url']} ({match['title']})"
                    )
            except Exception as e:
                crawler.logger.error(f"Error checking similarity for {url}: {e}")

        return content_fetched, new_links, None
