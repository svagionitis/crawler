import sqlite3
from datetime import datetime
import logging
from config import CrawlerConfig
from utils import ensure_directory_exists
import os
import threading

_local = threading.local()


def get_connection(database_name):
    """Get or create a thread-local SQLite connection for the specified database."""
    if not hasattr(_local, "connections"):
        _local.connections = {}
    if database_name not in _local.connections:
        conn = sqlite3.connect(database_name)
        # WAL mode allows concurrent reads during writes — essential for multi-threading.
        # We also set a high busy timeout to handle concurrent write access elegantly.
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
        _local.connections[database_name] = conn
    return _local.connections[database_name]


def close_thread_connections():
    """Close all SQLite connections cached in the current thread's local storage."""
    if hasattr(_local, "connections"):
        for db_name, conn in list(_local.connections.items()):
            try:
                conn.close()
            except Exception:
                pass
        _local.connections.clear()


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
    conn = get_connection(database_name)
    with conn:
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
                mime_type TEXT,
                content TEXT,
                content_hash TEXT,
                status TEXT NOT NULL CHECK(status IN ('pending', 'crawled'))
            )
            """
        )
        # Check if the mime_type column exists (for auto-migration of existing databases)
        cursor.execute("PRAGMA table_info(crawled_data)")
        columns = [row[1] for row in cursor.fetchall()]
        if "mime_type" not in columns:
            cursor.execute("ALTER TABLE crawled_data ADD COLUMN mime_type TEXT")
            if logger:
                logger.info("Auto-migration: added mime_type column to crawled_data.")

        # Ensure idx_link is a UNIQUE index for UPSERT compatibility and data integrity.
        cursor.execute(
            "SELECT sql FROM sqlite_master WHERE type='index' AND name='idx_link'"
        )
        idx_sql = cursor.fetchone()
        is_unique = idx_sql and "UNIQUE" in idx_sql[0].upper()

        if not is_unique:
            # Clean up duplicate links before creating the unique index.
            # Keep the row with the lowest id (oldest insertion) for each link.
            cursor.execute(
                """
                DELETE FROM crawled_data
                WHERE id NOT IN (
                    SELECT MIN(id)
                    FROM crawled_data
                    GROUP BY link
                )
                """
            )
            deleted_links = cursor.rowcount
            if deleted_links:
                logger.info(
                    f"Auto-migration: removed {deleted_links} duplicate link row(s)."
                )

            cursor.execute("DROP INDEX IF EXISTS idx_link")
            cursor.execute("CREATE UNIQUE INDEX idx_link ON crawled_data (link)")
            logger.info("Auto-migration: created UNIQUE index idx_link.")
        # Create an index on the status column
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_status ON crawled_data (status)")
        # Create an index on the link, status columns
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_link_status ON crawled_data (link, status)"
        )
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
        cursor.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_content_hash ON crawled_data (content_hash)"
        )
        conn.commit()


def save_links_to_db(
    database_name,
    domain,
    links,
    robots_parser,
    status="pending",
    re_crawl_time=3,
    logger=None,
):
    """Save multiple links to the database in a batch, if allowed by robots.txt."""
    if logger is None:
        logger = logging.getLogger(__name__)
    try:
        conn = get_connection(database_name)
        with conn:
            cursor = conn.cursor()
            for link in links:
                if robots_parser and not robots_parser.can_fetch(
                    CrawlerConfig().user_agent, link
                ):
                    logger.info(f"Skipping disallowed link: {link}")
                    continue

                cursor.execute(
                    """
                    INSERT INTO crawled_data (domain, date_inserted, link, status)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(link) DO UPDATE SET
                        status = CASE
                            WHEN status = 'crawled' AND (julianday('now') - julianday(date_crawled)) * 24 >= ? THEN 'pending'
                            ELSE status
                        END,
                        date_inserted = CASE
                            WHEN status = 'pending' OR (status = 'crawled' AND (julianday('now') - julianday(date_crawled)) * 24 >= ?) THEN excluded.date_inserted
                            ELSE date_inserted
                        END
                    """,
                    (
                        domain,
                        datetime.now(),
                        link,
                        status,
                        re_crawl_time,
                        re_crawl_time,
                    ),
                )
                if cursor.rowcount > 0:
                    logger.info(
                        f"Saved/updated link in database: {link} (status: {status})"
                    )
            conn.commit()  # Commit all changes at once
    except sqlite3.Error as e:
        logger.error(f"Database error while saving links: {e}")


def reset_link_to_pending(database_name, link, logger=None):
    """Reset a crawled link back to pending (for re-crawls)."""
    if logger is None:
        logger = logging.getLogger(__name__)
    try:
        conn = get_connection(database_name)
        with conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE crawled_data
                SET status = 'pending', date_inserted = ?
                WHERE link = ?
                """,
                (datetime.now(), link),
            )
            conn.commit()
            logger.info(f"Reset link status to pending for re-crawl: {link}")
    except sqlite3.Error as e:
        logger.error(f"Database error while resetting link to pending: {e}")


def update_queue_link(
    database_name,
    link,
    content,
    content_hash,
    status="crawled",
    mime_type=None,
    logger=None,
) -> bool:
    """Update a link in the crawl queue with content, hash, date_crawled, and mark it with the given status.

    Returns:
        True on success, False if the update was rejected due to a duplicate
        content_hash (IntegrityError from the UNIQUE index).
    """
    if logger is None:
        logger = logging.getLogger(__name__)
    try:
        conn = get_connection(database_name)
        with conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE crawled_data
                SET content = ?, content_hash = ?, status = ?, date_crawled = ?, mime_type = ?
                WHERE link = ?
                """,
                (content, content_hash, status, datetime.now(), mime_type, link),
            )
            conn.commit()
            logger.info(f"Updated queue link in database: {link}")
            return True
    except sqlite3.IntegrityError:
        # Another row with the same content_hash was committed between our
        # duplicate-check and this UPDATE (TOCTOU race in multi-threaded mode).
        logger.info(f"Skipping duplicate content (concurrent write race): {link}")
        return False
    except sqlite3.Error as e:
        logger.error(f"Database error while updating queue link: {e}")
        return False


def load_pending_links(database_name, re_crawl_time=3, limit=None, logger=None):
    """Load pending links from the database.

    Args:
        database_name (str): Path to the SQLite database.
        re_crawl_time (int): Time in hours after which a link should be re-crawled.
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
        conn = get_connection(database_name)
        with conn:
            cursor = conn.cursor()
            query = """
                SELECT link FROM crawled_data
                WHERE status = 'pending'
                  AND (date_crawled IS NULL OR (julianday('now') - julianday(date_crawled)) * 24 >= ?)
            """
            params = (re_crawl_time,)
            if limit is not None:
                query += " LIMIT ?"
                params = (re_crawl_time, limit)
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
        conn = get_connection(database_name)
        with conn:
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
        conn = get_connection(database_name)
        with conn:
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
                if (
                    time_since_last_crawl.total_seconds() <= re_crawl_time * 3600
                ):  # Convert hours to seconds
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
        conn = get_connection(database_name)
        with conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT 1 FROM crawled_data WHERE content_hash = ? LIMIT 1",
                (content_hash,),
            )
            return cursor.fetchone() is not None
    except sqlite3.Error as e:
        logger.error(f"Database error while checking duplicate content hash: {e}")
        return False  # Assume not a duplicate so the page is not silently dropped
