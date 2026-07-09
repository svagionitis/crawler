import hashlib
import sqlite3
import struct
import random
import logging
import queue
import threading
import os
from database import get_connection

# Registry of active database background workers (db_path -> (Queue, Thread))
# Ensures that only one background writer thread processes queries per database file.
_active_workers = {}
_workers_lock = threading.Lock()


def init_similarity_db(db_path, logger=None):
    """Initialize the central similarity index database schema."""
    if logger is None:
        logger = logging.getLogger(__name__)

    conn = get_connection(db_path)
    with conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=30000;")

        cursor = conn.cursor()

        # Create global signatures index table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS global_signatures (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                domain TEXT NOT NULL,
                url TEXT UNIQUE NOT NULL,
                title TEXT,
                html_content TEXT,
                extracted_text TEXT,
                date_crawled DATETIME,
                date_inserted DATETIME DEFAULT CURRENT_TIMESTAMP,
                text_signature BLOB NOT NULL
            )
        """)
        # Create matching pair references
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS plagiarism_matches (
                source_url TEXT NOT NULL,
                target_url TEXT NOT NULL,
                similarity_score REAL NOT NULL,
                match_type TEXT NOT NULL,
                PRIMARY KEY (source_url, target_url)
            )
        """)


def compute_minhash(text, num_permutations=128):
    """Compute 128-integer MinHash signature of clean text using character 3-grams (shingles)."""
    prime = 4294967311  # Large prime close to 2^32

    # Lazy-initialize and cache the hash coefficients on the function object itself.
    # We use a dedicated Random instance to avoid mutating the global random state.
    if not hasattr(compute_minhash, "coeff_a"):
        r = random.Random(42)
        compute_minhash.coeff_a = [r.randint(1, prime - 1) for _ in range(num_permutations)]
        compute_minhash.coeff_b = [r.randint(0, prime - 1) for _ in range(num_permutations)]

    coeff_a = compute_minhash.coeff_a
    coeff_b = compute_minhash.coeff_b

    # Clean text: normalize whitespace and lowercase for similarity robustness
    text = " ".join(text.split()).lower()
    shingles = set()
    for i in range(len(text) - 2):
        shingles.add(text[i : i + 3])

    if not shingles:
        # Return signature filled with maximum value if document contains no shingles
        return struct.pack(f"<{num_permutations}I", *[0xFFFFFFFF] * num_permutations)

    signature = [0xFFFFFFFF] * num_permutations

    for shingle in shingles:
        # Hash shingles into 32-bit integers using a slice of SHA-256
        shingle_hash = int(hashlib.sha256(shingle.encode("utf-8")).hexdigest()[:8], 16)
        for i in range(num_permutations):
            # Universal hashing: h(x) = (a * x + b) % p
            val = (coeff_a[i] * shingle_hash + coeff_b[i]) % prime
            if val < signature[i]:
                signature[i] = val

    # Pack 128 unsigned integers (4 bytes each) into a 512-byte binary blob
    return struct.pack(f"<{num_permutations}I", *signature)


def calculate_similarity(sig1_blob, sig2_blob, num_permutations=128):
    """Calculate Jaccard similarity estimation between two packed MinHash signature blobs."""
    if not sig1_blob or not sig2_blob:
        return 0.0
    sig1 = struct.unpack(f"<{num_permutations}I", sig1_blob)
    sig2 = struct.unpack(f"<{num_permutations}I", sig2_blob)
    matches = sum(1 for val1, val2 in zip(sig1, sig2) if val1 == val2 and val1 != 0xFFFFFFFF)
    return matches / num_permutations


def _similarity_worker_loop(db_path, job_queue):
    """Background worker thread that processes central similarity requests sequentially to avoid lock contention."""
    conn = get_connection(db_path)
    while True:
        job = job_queue.get()
        if job is None:
            job_queue.task_done()
            break

        try:
            url = job["url"]
            domain = job["domain"]
            title = job["title"]
            html_content = job["html_content"]
            extracted_text = job["extracted_text"]
            date_crawled = job["date_crawled"]
            threshold = job["threshold"]
            logger = logging.getLogger(job["logger_name"])

            sig = compute_minhash(extracted_text)
            matches = []
            with conn:
                # Query existing signatures to compare.
                # Performance Optimization: Only load metadata to avoid memory-intensive HTML content strings.
                cursor = conn.execute(
                    "SELECT url, domain, title, date_crawled, text_signature FROM global_signatures WHERE url != ?",
                    (url,)
                )
                rows = cursor.fetchall()

                for other_url, other_domain, other_title, other_date, other_sig in rows:
                    score = calculate_similarity(sig, other_sig)
                    if score >= threshold:
                        matches.append({
                            "url": other_url,
                            "domain": other_domain,
                            "title": other_title,
                            "date_crawled": other_date,
                            "score": score
                        })

                # Save the new signature and clean text + html to global index database
                conn.execute("""
                    INSERT OR REPLACE INTO global_signatures (domain, url, title, html_content, extracted_text, date_crawled, text_signature)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (domain, url, title, html_content, extracted_text, date_crawled, sig))

                # Record plagiarism matching pairs
                for match in matches:
                    conn.execute("""
                        INSERT OR IGNORE INTO plagiarism_matches (source_url, target_url, similarity_score, match_type)
                        VALUES (?, ?, ?, ?)
                    """, (url, match["url"], match["score"], "near_duplicate"))

            # Log any detected duplicate warnings
            for match in matches:
                logger.warning(
                    f"🚨 Plagiarism/Duplicate Detected! {url} is "
                    f"{match['score']*100:.1f}% similar to {match['url']} ({match['title']})"
                )

        except Exception as e:
            print(f"Error in similarity indexing background thread for {db_path}: {e}")
        finally:
            job_queue.task_done()


class SimilarityIndexer:
    """Manages cross-domain signature checking and plagiarism detection database records."""

    def __init__(self, index_db_path="db/plagiarism_index.db", sync=False, logger=None):
        self.db_path = os.path.abspath(index_db_path)
        self.sync = sync
        self.logger = logger or logging.getLogger(__name__)
        init_similarity_db(self.db_path, logger=self.logger)

        if not self.sync:
            with _workers_lock:
                if self.db_path not in _active_workers:
                    job_queue = queue.Queue()
                    t = threading.Thread(
                        target=_similarity_worker_loop,
                        args=(self.db_path, job_queue),
                        daemon=True
                    )
                    t.start()
                    _active_workers[self.db_path] = (job_queue, t)
                self.queue = _active_workers[self.db_path][0]

    def index_and_check(self, url, domain, title, html_content, extracted_text, date_crawled, threshold=0.8):
        """Index the text signature and find existing matches above the similarity threshold.

        Returns:
            list: List of matching documents (only populated if running in sync=True mode).
        """
        if not extracted_text:
            return []

        if self.sync:
            sig = compute_minhash(extracted_text)
            conn = get_connection(self.db_path)
            matches = []
            with conn:
                cursor = conn.execute(
                    "SELECT url, domain, title, date_crawled, text_signature FROM global_signatures WHERE url != ?",
                    (url,)
                )
                rows = cursor.fetchall()

                for other_url, other_domain, other_title, other_date, other_sig in rows:
                    score = calculate_similarity(sig, other_sig)
                    if score >= threshold:
                        matches.append({
                            "url": other_url,
                            "domain": other_domain,
                            "title": other_title,
                            "date_crawled": other_date,
                            "score": score
                        })

                conn.execute("""
                    INSERT OR REPLACE INTO global_signatures (domain, url, title, html_content, extracted_text, date_crawled, text_signature)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (domain, url, title, html_content, extracted_text, date_crawled, sig))

                for match in matches:
                    conn.execute("""
                        INSERT OR IGNORE INTO plagiarism_matches (source_url, target_url, similarity_score, match_type)
                        VALUES (?, ?, ?, ?)
                    """, (url, match["url"], match["score"], "near_duplicate"))
            return matches
        else:
            self.queue.put({
                "url": url,
                "domain": domain,
                "title": title,
                "html_content": html_content,
                "extracted_text": extracted_text,
                "date_crawled": date_crawled,
                "threshold": threshold,
                "logger_name": self.logger.name
            })
            return []

    @staticmethod
    def shutdown():
        """Blocks until all active similarity queues have finished processing and joins them."""
        with _workers_lock:
            for db_path, (job_queue, _) in list(_active_workers.items()):
                job_queue.join()
