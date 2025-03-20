import sqlite3
from datetime import datetime
import logging
from config import USER_AGENT
from utils import ensure_directory_exists
import os


def get_database_name(domain, db_dir):
    """Generate the database filename based on the domain and save it in the specified db directory."""

    # Ensure the db directory exists
    ensure_directory_exists(db_dir)

    # Generate the database filename
    return os.path.join(db_dir, f"crawled_data_{domain}.db")

def init_db(database_name):
    """Initialize the SQLite database and create the table if it doesn't exist."""
    with sqlite3.connect(database_name) as conn:
        cursor = conn.cursor()
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
                status TEXT NOT NULL CHECK(status IN ('pending', 'crawled'))
            )
            """
        )
        # Create an index on the link column
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_link ON crawled_data (link)")
        # Create an index on the status column
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_status ON crawled_data (status)")
        # Create an index on the link, status columns
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_link_status ON crawled_data (link, status)")
        conn.commit()

def save_link_to_db(database_name, domain, link, robots_parser, status="pending"):
    """Save a link to the database with a given status, if allowed by robots.txt."""
    if robots_parser and not robots_parser.can_fetch(USER_AGENT, link):
        logging.info(f"Skipping disallowed link: {link}")
        return

    try:
        with sqlite3.connect(database_name) as conn:
            cursor = conn.cursor()
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
                logging.info(f"Updated date_inserted for pending link: {link}")
            else:
                # Insert the new link
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO crawled_data (domain, date_inserted, link, status)
                    VALUES (?, ?, ?, ?)
                    """,
                    (domain, datetime.now(), link, status),
                )
                logging.info(f"Saved link to database: {link} (status: {status})")
            conn.commit()
    except sqlite3.Error as e:
        logging.error(f"Database error while saving link: {e}")

def update_link_in_db(database_name, link, content, content_hash, status="crawled"):
    """Update a link in the database with content, hash, and date_crawled, and mark it with the given status."""
    try:
        with sqlite3.connect(database_name) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE crawled_data
                SET content = ?, content_hash = ?, status = ?, date_crawled = ?
                WHERE link = ?
                """,
                (content, content_hash, status, datetime.now(), link),
            )
            conn.commit()
            logging.info(f"Updated link in database: {link}")
    except sqlite3.Error as e:
        logging.error(f"Database error while updating link: {e}")

def load_pending_links(database_name):
    """Load all pending links from the database."""
    pending_links = []
    try:
        with sqlite3.connect(database_name) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT link FROM crawled_data WHERE status = 'pending'")
            pending_links = [row[0] for row in cursor.fetchall()]
    except sqlite3.Error as e:
        logging.error(f"Failed to load pending links from database: {e}")
    return pending_links

def is_database_empty(database_name):
    """Check if the database is empty."""
    try:
        with sqlite3.connect(database_name) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM crawled_data")
            count = cursor.fetchone()[0]
            return count == 0
    except sqlite3.Error as e:
        logging.error(f"Failed to check if database is empty: {e}")
        return True  # Assume empty if there's an error

def check_re_crawl(database_name, link, re_crawl_time):
    """
    Check if a link should be re-crawled based on the re-crawl time.
    Returns True if the link should be re-crawled, False otherwise.
    """
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
        logging.error(f"Failed to check re-crawl status for link {link}: {e}")
        return True  # Assume re-crawl if there's an error
