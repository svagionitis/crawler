# Code Review: Memory Consumption Analysis

*Senior Python Software Engineer Review — All Modules*

---

## 🔴 Critical Issues

### 1. Job Queue Stores Full HTML Content in Memory (Unbounded Growth)

> [!CAUTION]
> **File**: [similarity.py L333-343](file:///c:/Users/Stavros/workspace/GreekNewsScraper/Crawler.git/similarity.py#L333-L343) and [crawler_app.py L187-194](file:///c:/Users/Stavros/workspace/GreekNewsScraper/Crawler.git/crawler_app.py#L187-L194)
>
> When running in async mode (the default), `index_and_check()` pushes the **entire `html_content` string** and `extracted_text` into the `queue.Queue` as a dict. The background worker then holds this job in memory until it is processed.
>
> **Impact**: If crawl workers produce pages faster than the single background similarity thread can consume them, the queue grows unboundedly. With typical news pages at 200-500 KB of HTML each, 1,000 queued jobs = **200-500 MB of RAM** consumed by the queue alone. With 20+ parallel site crawlers sharing one queue, this can spike to gigabytes.

**Remediation**: Don't pass raw content through the queue. Instead, write `html_content` and `extracted_text` to the `global_signatures` table *in the caller thread* (which already has a DB connection), and only push lightweight metadata (url, domain, title, date, threshold, logger_name) through the queue. The background worker then reads content from the DB if needed.

Alternatively, cap the queue: `queue.Queue(maxsize=50)` will apply backpressure when the consumer falls behind, blocking the producer instead of consuming unbounded memory.

```python
# Current: pushes ~500KB per job
self.queue.put({
    "url": url,
    "html_content": html_content,      # 200-500 KB!
    "extracted_text": extracted_text,   # 10-50 KB
    ...
})

# Proposed: push only metadata (~200 bytes per job)
self.queue.put({
    "url": url,
    "domain": domain,
    "title": title,
    "date_crawled": date_crawled,
    "threshold": threshold,
    "logger_name": self.logger.name
})
```

---

### 2. `global_signatures` Stores Full HTML + Text (Unbounded DB Bloat)

> [!CAUTION]
> **File**: [similarity.py L197-201](file:///c:/Users/Stavros/workspace/GreekNewsScraper/Crawler.git/similarity.py#L197-L201) and [similarity.py L313-317](file:///c:/Users/Stavros/workspace/GreekNewsScraper/Crawler.git/similarity.py#L313-L317)
>
> The `global_signatures` table stores `html_content TEXT` and `extracted_text TEXT` for **every crawled page across all domains**. This data is already stored in each per-domain `crawled_data` database. The plagiarism index is a *central* database — it duplicates all content a second time.
>
> **Impact**: After crawling 100,000 pages (realistic for 20+ Greek news sites), the plagiarism DB could reach **50-100 GB** of disk and corresponding SQLite cache memory.

**Remediation**: The `global_signatures` table only needs `url`, `domain`, `title`, `date_crawled`, and `text_signature` (512 bytes) for similarity matching. Remove the `html_content` and `extracted_text` columns entirely — they are never read during similarity calculations and exist only as dead weight.

---

### 3. Auto-Migration `fetchall()` Loads All Signatures into Memory

> [!WARNING]
> **File**: [similarity.py L69-70](file:///c:/Users/Stavros/workspace/GreekNewsScraper/Crawler.git/similarity.py#L69-L70)
>
> The LSH auto-migration uses `cursor.fetchall()` to load every `(url, text_signature)` row from `global_signatures` into memory at once.
>
> **Impact**: With 100,000 signatures at ~600 bytes each, this is ~60 MB. But with the current schema that also stores `html_content` and `extracted_text` (Issue #2), SQLite may load heavier rows into its page cache. The `band_rows` list also grows to 16× the row count (1.6 million tuples).

**Remediation**: Use batched `fetchmany(1000)` and `executemany()` in chunks:
```python
cursor.execute("SELECT url, text_signature FROM global_signatures")
while True:
    rows = cursor.fetchmany(1000)
    if not rows:
        break
    batch = []
    for url, sig in rows:
        if len(sig) == 512:
            # ... compute bands, append to batch
    if batch:
        cursor.executemany("INSERT INTO lsh_buckets ...", batch)
```

---

## 🟡 Moderate Issues

### 4. `crawl_page()` Holds 3 Copies of Page Content Simultaneously

> [!IMPORTANT]
> **File**: [crawler_app.py L143-191](file:///c:/Users/Stavros/workspace/GreekNewsScraper/Crawler.git/crawler_app.py#L143-L191)
>
> During `crawl_page()`, the following all coexist on the stack:
> 1. `content` — raw HTML string (200-500 KB)
> 2. `soup` — BeautifulSoup parse tree (~3-5× the HTML size, so 1-2.5 MB)
> 3. `extracted["text"]` — extracted article text
> 4. The same `content` is then passed to `update_link_in_db()` and `indexer.index_and_check()` (the queue holds another reference)
>
> **Impact**: Peak per-page memory is ~3-5 MB. With 4 worker threads, that's 12-20 MB of concurrent page processing — manageable but wasteful.

**Remediation**: Set `soup = None` after links and content have been extracted to allow GC to reclaim the parse tree before the DB write and similarity check:
```python
new_links = extract_links(..., soup=soup, ...) if soup else set()
extracted = extract_article_content(..., soup=soup, ...)
del soup  # Release ~2 MB parse tree before DB writes
```

---

### 5. Thread-Local Connection Cache Never Closes Connections

> [!IMPORTANT]
> **File**: [database.py L13-24](file:///c:/Users/Stavros/workspace/GreekNewsScraper/Crawler.git/database.py#L13-L24)
>
> `get_connection()` caches SQLite connections in `threading.local()` but never closes them. When crawling 20+ sites in parallel (each with its own domain DB plus the shared plagiarism DB), each worker thread accumulates connections that are never released.
>
> **Impact**: SQLite connections hold memory-mapped WAL pages. With multiple DBs open per thread across multiple threads, this creates persistent memory pressure from page cache.

**Remediation**: Add a `close_connections()` function and call it when threads exit:
```python
def close_connections():
    if hasattr(_local, "connections"):
        for conn in _local.connections.values():
            conn.close()
        _local.connections.clear()
```

---

## 🟢 Minor Issues

### 6. `compute_minhash()` Creates a Full Shingle Set in Memory

> [!TIP]
> **File**: [similarity.py L104-107](file:///c:/Users/Stavros/workspace/GreekNewsScraper/Crawler.git/similarity.py#L104-L107)
>
> For a 10,000-character article, `set()` stores ~10,000 unique 3-character strings. Each Python string object has ~50 bytes of overhead, so a single article generates ~500 KB of shingle objects.

**Remediation**: Hash shingles inline without storing them in a set. Use a seen-hash set of integers instead of string objects:
```python
seen = set()
for i in range(len(text) - 2):
    shingle = text[i : i + 3]
    shingle_hash = int(hashlib.sha256(shingle.encode("utf-8")).hexdigest()[:8], 16)
    if shingle_hash in seen:
        continue
    seen.add(shingle_hash)
    for j in range(num_permutations):
        val = (coeff_a[j] * shingle_hash + coeff_b[j]) % prime
        if val < signature[j]:
            signature[j] = val
```

### 7. Base64-Encoding Binary Content Inflates Memory 33%

> [!TIP]
> **File**: [utils.py L46-47](file:///c:/Users/Stavros/workspace/GreekNewsScraper/Crawler.git/utils.py#L46-L47)
>
> Non-text responses (images, PDFs) are base64-encoded and stored as strings. Base64 inflates data by 33%, and then the string is written to SQLite's TEXT column in `update_link_in_db()`.
>
> **Impact**: A 5 MB image becomes a 6.7 MB string in memory and on disk. This compounds across all non-text responses.

**Remediation**: Consider skipping non-HTML content entirely (the crawler is designed for news articles), or store binary content as `BLOB` without base64 encoding.

---

## Summary Priority Matrix

| # | Severity | Issue | Memory Impact | Fix Effort |
|---|----------|-------|---------------|------------|
| 1 | 🔴 Critical | Queue stores full HTML | Unbounded (GBs) | Medium |
| 2 | 🔴 Critical | `global_signatures` duplicates all content | 50-100 GB disk | Medium |
| 3 | 🟠 High | Auto-migration `fetchall()` | 60 MB+ spike | Low |
| 4 | 🟡 Moderate | 3 copies of page content on stack | 12-20 MB | Low |
| 5 | 🟡 Moderate | Thread-local connections never closed | Persistent cache | Low |
| 6 | 🟢 Minor | Shingle set materialization | 500 KB/page | Low |
| 7 | 🟢 Minor | Base64 inflation of binary content | 33% overhead | Low |
