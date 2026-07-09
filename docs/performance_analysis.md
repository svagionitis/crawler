# Performance Analysis: CPU & Memory Usage

## Root Causes Summary

The ~10% CPU and ~300 MB memory footprint comes from several distinct categories of inefficiency. Each is ranked by expected impact.

---

## 🔴 High Impact

### 1. `visited_hashes` Set Grows Unbounded in Memory
**File:** [crawler_app.py](file:///c:/Users/Stavros/workspace/GreekNewsScraper/Crawler.git/crawler_app.py#L243)

```python
visited_hashes = set()  # Grows forever — no eviction, no cap
```

Every crawled page's SHA-256 hash (64-byte hex string) is kept in memory for the entire lifetime of the crawl. For a site with tens of thousands of pages, this set alone can consume hundreds of MBs. Since the database already stores `content_hash`, the DB is the correct source of truth — the in-memory set is redundant.

**Fix:** Delegate duplicate detection entirely to the database using a `UNIQUE` constraint on `content_hash`, and eliminate the in-memory set.

```sql
-- In init_db()
CREATE UNIQUE INDEX IF NOT EXISTS idx_content_hash ON crawled_data (content_hash);
```
```python
# In crawl_page() — just attempt the INSERT and catch the IntegrityError
# No in-memory set needed at all
```

---

### 2. Full HTML Stored in `content` Column — Large DB & Memory Footprint
**File:** [database.py](file:///c:/Users/Stavros/workspace/GreekNewsScraper/Crawler.git/database.py#L115), [crawler_app.py](file:///c:/Users/Stavros/workspace/GreekNewsScraper/Crawler.git/crawler_app.py#L156-L164)

The full raw HTML (often 100–500 KB per page) is stored in the `content` column alongside the already-extracted `extracted_text`. This means:
- SQLite holds two copies of essentially the same information.
- The `content` string is kept in Python memory during the entire `crawl_page` → `update_link_in_db` call chain.

**Fix:** Consider dropping the raw `content` column once extraction is complete, or only storing it when the extracted content is empty (i.e., as a fallback). If you do need to keep it, compress it with `zlib` before storage.

```python
import zlib
compressed = zlib.compress(content.encode("utf-8"))  # ~70-80% size reduction for HTML
```

---

### 3. `extract_links` Parses HTML with BeautifulSoup Twice Per Page
**File:** [utils.py](file:///c:/Users/Stavros/workspace/GreekNewsScraper/Crawler.git/utils.py#L100), [utils.py](file:///c:/Users/Stavros/workspace/GreekNewsScraper/Crawler.git/utils.py#L187)

When a page is crawled:
1. `extract_article_content()` calls `extract_with_bs4()` → creates a `BeautifulSoup` object.
2. `extract_links()` creates *another* `BeautifulSoup` object for the same HTML.

Parsing large HTML pages with BeautifulSoup is CPU-intensive (it builds a full DOM tree in Python). Doing it twice per page is wasteful.

**Fix:** Parse once and pass the `soup` object to both functions.

```python
# In crawl_page / crawl_worker:
soup = BeautifulSoup(content, "html.parser")
extracted = extract_article_content(soup=soup, ...)  # accept pre-parsed soup
new_links = extract_links(base_url, soup=soup, ...)
```

---

### 4. `urlparse` Called Repeatedly in `extract_links` Inside a Loop
**File:** [utils.py](file:///c:/Users/Stavros/workspace/GreekNewsScraper/Crawler.git/utils.py#L105)

```python
for a_tag in soup.find_all("a", href=True):
    link = urljoin(base_url, a_tag["href"])
    if urlparse(link).netloc == urlparse(base_url).netloc:  # ← urlparse(base_url) called per iteration
```

`urlparse(base_url)` is called for *every* `<a>` tag on the page, even though `base_url` never changes.

**Fix:** Hoist the parse outside the loop.

```python
base_netloc = urlparse(base_url).netloc
for a_tag in soup.find_all("a", href=True):
    link = urljoin(base_url, a_tag["href"])
    if urlparse(link).netloc == base_netloc:
        ...
```

---

## 🟡 Medium Impact

### 5. A New SQLite Connection is Opened for Every Single DB Operation
**File:** [database.py](file:///c:/Users/Stavros/workspace/GreekNewsScraper/Crawler.git/database.py#L74) [database.py](file:///c:/Users/Stavros/workspace/GreekNewsScraper/Crawler.git/database.py#L122) [database.py](file:///c:/Users/Stavros/workspace/GreekNewsScraper/Crawler.git/database.py#L157) [database.py](file:///c:/Users/Stavros/workspace/GreekNewsScraper/Crawler.git/database.py#L192)

Every call to `save_links_to_db`, `update_link_in_db`, `load_pending_links`, and `check_re_crawl` opens a fresh `sqlite3.connect()`. With multi-threaded crawling (`--workers > 1`), this creates OS-level contention for the WAL file and wastes CPU on repeated connection setup/teardown.

**Fix:** Use a `threading.local()` connection pool or a single shared connection per thread, and reuse it across calls.

```python
_local = threading.local()

def _get_conn(database_name):
    if not hasattr(_local, "conn") or _local.conn is None:
        _local.conn = sqlite3.connect(database_name, check_same_thread=False)
        _local.conn.execute("PRAGMA journal_mode=WAL")
    return _local.conn
```

---

### 6. `save_links_to_db` Does a SELECT + UPDATE/INSERT Per Link — Should Use UPSERT
**File:** [database.py](file:///c:/Users/Stavros/workspace/GreekNewsScraper/Crawler.git/database.py#L76-L110)

For every discovered link, the code runs a `SELECT` to check existence, then either `UPDATE` or `INSERT`. This is two round-trips per link. With hundreds of links per page, this is a lot of unnecessary I/O.

**Fix:** Use a single `INSERT OR IGNORE` + conditional `UPDATE` via `UPSERT` syntax (SQLite ≥ 3.24):

```sql
INSERT INTO crawled_data (domain, date_inserted, link, status)
VALUES (?, ?, ?, ?)
ON CONFLICT(link) DO UPDATE SET
  date_inserted = excluded.date_inserted
WHERE status = 'pending';
```

---

### 7. `check_re_crawl` Makes a Separate DB Round-Trip Per URL Before Crawling
**File:** [database.py](file:///c:/Users/Stavros/workspace/GreekNewsScraper/Crawler.git/database.py#L184), [crawler_app.py](file:///c:/Users/Stavros/workspace/GreekNewsScraper/Crawler.git/crawler_app.py#L123)

Before each page fetch, `check_re_crawl` queries the DB individually. This could be merged into the `load_pending_links` query itself — only load links that are actually due for a re-crawl.

**Fix:**
```sql
-- In load_pending_links, add the time filter:
SELECT link FROM crawled_data
WHERE status = 'pending'
  AND (date_crawled IS NULL OR
       (julianday('now') - julianday(date_crawled)) * 24 >= ?)
LIMIT ?
```

---

### 8. Busy-Wait Crawl Delay Loop Wastes CPU
**File:** [crawler_app.py](file:///c:/Users/Stavros/workspace/GreekNewsScraper/Crawler.git/crawler_app.py#L206-L210)

```python
remaining = crawl_delay
while remaining > 0 and not shutdown_event.is_set():
    chunk = min(remaining, 0.5)
    time.sleep(chunk)
    remaining -= chunk
```

Sleeping in 0.5-second chunks means the event is polled 2× per second. With multiple workers, this is many unnecessary wake-ups. The correct primitive is `threading.Event.wait(timeout)`, which blocks the OS scheduler until either the timeout fires or the event is set.

**Fix:**
```python
# Replaces the entire while loop
shutdown_event.wait(timeout=crawl_delay)
```

---

## 🟢 Low Impact / Good Practices

### 9. `is_html` Detection Uses `in content.lower()` on the Full Page String
**File:** [crawler_app.py](file:///c:/Users/Stavros/workspace/GreekNewsScraper/Crawler.git/crawler_app.py#L150)

```python
is_html = ("<html" in content.lower() or "<body" in content.lower() or ...)
```

`content.lower()` creates a full copy of the entire HTML page string in memory just for a case-insensitive search. Use `content_type` from the HTTP response headers instead (already available in `fetch_page`).

**Fix:** Return the `Content-Type` from `fetch_page` alongside the content, and use it here.

```python
return response.text, response.headers.get("Content-Type", ""), None
```

### 10. `compute_hash` Encodes the Entire Content Twice
**File:** [utils.py](file:///c:/Users/Stavros/workspace/GreekNewsScraper/Crawler.git/utils.py#L114-L116)

```python
def compute_hash(content):
    return hashlib.sha256(content.encode("utf-8")).hexdigest()
```

This is fine for correctness, but if you switch to streaming hash updates (`.update()`) you can avoid holding both the string and its encoded bytes in memory simultaneously — relevant for large pages.

---

## Prioritized Fix Order

| Priority | Issue | Est. Memory Saving | Est. CPU Saving |
|---|---|---|---|
| 1 | Unbounded `visited_hashes` set | **High** | Low |
| 2 | Store raw HTML + extracted text | **High** | Low |
| 3 | Double BeautifulSoup parse | Low | **High** |
| 4 | `urlparse` in hot loop | Low | Medium |
| 5 | Reconnect SQLite per call | Low | Medium |
| 6 | SELECT+INSERT vs UPSERT | Low | Medium |
| 7 | Merge re-crawl check into SQL | Low | Low |
| 8 | Busy-wait → `Event.wait()` | Low | Low |
| 9 | `content.lower()` copy | Low | Low |
