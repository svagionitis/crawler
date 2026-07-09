import sqlite3
from datetime import datetime
import logging
from config import USER_AGENT
from utils import ensure_directory_exists
import os
from typing import Optional


def get_database_name(domain, db_dir, logger=None):
    """Generate the database filename based on the domain and save it in the specified db directory."""

    # Ensure the db directory exists
    ensure_directory_exists(db_dir, logger=logger)

    # Generate the database filename
    return os.path.join(db_dir, f"crawled_data_{domain}.db")

def init_db(database_name, logger=None):
    """Initialize the SQLite database and create the table if it doesn't exist."""
    if logger is None:
        logger = logging.getLogger(__name__)
    with sqlite3.connect(database_name) as conn:
        cursor = conn.cursor()
        # WAL mode allows concurrent reads during writes — essential for multi-threading
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS crawled_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                domain TEXT NOT NULL,
                date_inserted DATETIME NOT NULL,
                date_crawled DATETIME,
                link TEXT NOT NULL,
                content TEXT,
                content_hash TEXT,
                status TEXT NOT NULL CHECK(status IN ('pending', 'crawled')),
                extracted_title TEXT,
                extracted_text TEXT,
                extracted_authors TEXT,
                extracted_date TEXT,
                extracted_keywords TEXT
            )
            """
        )
        # Create an index on the link column
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_link ON crawled_data (link)")
        # Create an index on the status column
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_status ON crawled_data (status)")
        # Create an index on the link, status columns
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_link_status ON crawled_data (link, status)")
        # Unique index on content_hash for DB-level duplicate detection.
        # SQLite treats each NULL as distinct, so pending/failed rows (where
        # content_hash IS NULL) are never affected by this constraint.
        #
        # For existing databases that pre-date this index, we deduplicate
        # automatically before creating it: keep the row with the lowest id
        # for each hash and delete the rest.  This runs only once (when the
        # index is absent) so it has zero cost on already-migrated databases.
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_content_hash'"
        )
        if cursor.fetchone() is None:
            cursor.execute(
                """
                DELETE FROM crawled_data
                WHERE  content_hash IS NOT NULL
                  AND  id NOT IN (
                           SELECT MIN(id)
                           FROM   crawled_data
                           WHERE  content_hash IS NOT NULL
                           GROUP  BY content_hash
                       )
                """
            )
            deleted = cursor.rowcount
            if deleted:
                logger.info(
                    f"Auto-migration: removed {deleted} duplicate content_hash "
                    f"row(s) before creating unique index."
                )
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_content_hash ON crawled_data (content_hash)")

        # Run migrations dynamically for existing databases
        cursor.execute("PRAGMA table_info(crawled_data)")
        columns = [row[1] for row in cursor.fetchall()]
        new_columns = [
            ("extracted_title", "TEXT"),
            ("extracted_text", "TEXT"),
            ("extracted_authors", "TEXT"),
            ("extracted_date", "TEXT"),
            ("extracted_keywords", "TEXT")
        ]
        for col_name, col_type in new_columns:
            if col_name not in columns:
                cursor.execute(f"ALTER TABLE crawled_data ADD COLUMN {col_name} {col_type}")
                logger.info(f"Added column {col_name} to crawled_data table.")

        conn.commit()

def save_links_to_db(database_name, domain, links, robots_parser, status="pending", logger=None):
    """Save multiple links to the database in a batch, if allowed by robots.txt."""
    if logger is None:
        logger = logging.getLogger(__name__)
    try:
        with sqlite3.connect(database_name) as conn:
            cursor = conn.cursor()
            for link in links:
                if robots_parser and not robots_parser.can_fetch(USER_AGENT, link):
                    logger.info(f"Skipping disallowed link: {link}")
                    continue

                # Check if the link already exists and is pending
                cursor.execute(
                    """
                    SELECT id FROM crawled_data WHERE link = ? AND status = 'pending'
                    """,
                    (link,),
                )
                existing_link = cursor.fetchone()

                if existing_link:
                    # Update the date_inserted for the existing pending link
                    cursor.execute(
                        """
                        UPDATE crawled_data
                        SET date_inserted = ?
                        WHERE id = ?
                        """,
                        (datetime.now(), existing_link[0]),
                    )
                    logger.info(f"Updated date_inserted for pending link: {link}")
                else:
                    # Insert the new link
                    cursor.execute(
                        """
                        INSERT OR IGNORE INTO crawled_data (domain, date_inserted, link, status)
                        VALUES (?, ?, ?, ?)
                        """,
                        (domain, datetime.now(), link, status),
                    )
                    logger.info(f"Saved link to database: {link} (status: {status})")
            conn.commit()  # Commit all changes at once
    except sqlite3.Error as e:
        logger.error(f"Database error while saving links: {e}")

def update_link_in_db(database_name, link, content, content_hash, status="crawled",
                      extracted_title=None, extracted_text=None, extracted_authors=None,
                      extracted_date=None, extracted_keywords=None, logger=None) -> bool:
    """Update a link in the database with content, hash, date_crawled, parsed metadata, and mark it with the given status.

    Returns:
        True on success, False if the update was rejected due to a duplicate
        content_hash (IntegrityError from the UNIQUE index).
    """
    if logger is None:
        logger = logging.getLogger(__name__)
    try:
        with sqlite3.connect(database_name) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE crawled_data
                SET content = ?, content_hash = ?, status = ?, date_crawled = ?,
                    extracted_title = ?, extracted_text = ?, extracted_authors = ?,
                    extracted_date = ?, extracted_keywords = ?
                WHERE link = ?
                """,
                (content, content_hash, status, datetime.now(),
                 extracted_title, extracted_text, extracted_authors,
                 extracted_date, extracted_keywords, link),
            )
            conn.commit()
            logger.info(f"Updated link in database: {link}")
            return True
    except sqlite3.IntegrityError:
        # Another row with the same content_hash was committed between our
        # duplicate-check and this UPDATE (TOCTOU race in multi-threaded mode).
        logger.info(f"Skipping duplicate content (concurrent write race): {link}")
        return False
    except sqlite3.Error as e:
        logger.error(f"Database error while updating link: {e}")
        return False

def load_pending_links(database_name, limit=None, logger=None):
    """Load pending links from the database.

    Args:
        database_name (str): Path to the SQLite database.
        limit (int | None): Maximum number of links to return.
                            Pass None to load all pending links (default behaviour).
        logger: Optional logger instance. Falls back to module-level logger.

    Returns:
        list[str]: List of pending URLs.
    """
    if logger is None:
        logger = logging.getLogger(__name__)
    pending_links = []
    try:
        with sqlite3.connect(database_name) as conn:
            cursor = conn.cursor()
            query = "SELECT link FROM crawled_data WHERE status = 'pending'"
            params = ()
            if limit is not None:
                query += " LIMIT ?"
                params = (limit,)
            cursor.execute(query, params)
            pending_links = [row[0] for row in cursor.fetchall()]
    except sqlite3.Error as e:
        logger.error(f"Failed to load pending links from database: {e}")
    return pending_links

def is_database_empty(database_name, logger=None):
    """Check if the database is empty."""
    if logger is None:
        logger = logging.getLogger(__name__)
    try:
        with sqlite3.connect(database_name) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM crawled_data")
            count = cursor.fetchone()[0]
            return count == 0
    except sqlite3.Error as e:
        logger.error(f"Failed to check if database is empty: {e}")
        return True  # Assume empty if there's an error

def check_re_crawl(database_name, link, re_crawl_time, logger=None):
    """
    Check if a link should be re-crawled based on the re-crawl time.
    Returns True if the link should be re-crawled, False otherwise.
    """
    if logger is None:
        logger = logging.getLogger(__name__)
    try:
        with sqlite3.connect(database_name) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT date_crawled FROM crawled_data WHERE link = ?
                """,
                (link,),
            )
            date_crawled = cursor.fetchone()

            if date_crawled and date_crawled[0]:
                last_crawled_time = datetime.fromisoformat(date_crawled[0])
                time_since_last_crawl = datetime.now() - last_crawled_time
                if time_since_last_crawl.total_seconds() <= re_crawl_time * 3600:  # Convert hours to seconds
                    return False  # Do not re-crawl
            return True  # Re-crawl
    except sqlite3.Error as e:
        logger.error(f"Failed to check re-crawl status for link {link}: {e}")
        return True  # Assume re-crawl if there's an error


def is_duplicate_content(database_name, content_hash: str, logger=None) -> bool:
    """Check whether a page with the given content_hash has already been saved.

    This replaces the in-memory ``visited_hashes`` set, letting the database
    be the single source of truth.  The lookup is fast because
    ``idx_content_hash`` is a covering index on this column.

    Args:
        database_name (str): Path to the SQLite database.
        content_hash (str): SHA-256 hex digest to look up.
        logger: Optional logger instance.

    Returns:
        True if a row with this hash already exists, False otherwise.
    """
    if logger is None:
        logger = logging.getLogger(__name__)
    try:
        with sqlite3.connect(database_name) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT 1 FROM crawled_data WHERE content_hash = ? LIMIT 1",
                (content_hash,),
            )
            return cursor.fetchone() is not None
    except sqlite3.Error as e:
        logger.error(f"Database error while checking duplicate content hash: {e}")
        return False  # Assume not a duplicate so the page is not silently dropped
