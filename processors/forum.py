from bs4 import BeautifulSoup
from utils import extract_links, compute_hash
from database import is_duplicate_content, update_queue_link, get_connection
from .base import BaseContentProcessor


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
