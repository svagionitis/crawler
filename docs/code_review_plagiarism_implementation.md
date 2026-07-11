# Code Review: Plagiarism & Near-Duplicate Detection (Phase 1)

This code review evaluates the architecture, design patterns, and codebase integration of the Plagiarism and Near-Duplicate Detection module (`similarity.py` and `crawler_app.py` integration) from the perspective of a Senior Python Software Engineer.

---

## 🌟 Codebase Accomplishments & Architectural Strengths

### 1. Robust and Deterministic Mathematical Modeling
* **Character 3-Gram Tokenization**: Tokenizing clean lowercased text into character-level 3-grams (shingles) is highly resilient for Greek text near-duplicate detection. It accommodates monotonic/polytonic stress mark variations, punctuation differences, spelling corrections, and word shifts.
* **Hermetic and Isolated Universal Hashing**: Creating a localized `random.Random(42)` generator instance inside the `compute_minhash` function is a great practice. It guarantees identical random coefficients across multiple parallel runs and processes without polluting or modifying the global seed state of the standard `random` module, which might be relied upon elsewhere by developers.
* **High Efficiency via Binary Blob Packing**: Packing the 128-integer MinHash signatures into a compact 512-byte binary representation using `struct.pack('<128I')` saves substantial database space, optimizes memory alignment, and makes SQLite index scans extremely fast.

### 2. Micro-Optimizations & Performance Caching
* **Function Attribute Caching**: The lazy-initialization pattern caching coefficients on the function object (`compute_minhash.coeff_a`) simulates a static variable. It ensures that the array initialization overhead is paid exactly **once** (on the first execution) and skipped for subsequent crawled documents:
  ```python
  if not hasattr(compute_minhash, "coeff_a"):
      r = random.Random(42)
      compute_minhash.coeff_a = [...]
  ```
* **Thread-Safe Cached Connections**: By importing `get_connection()` from the `database` module, the similarity indexer reuses SQLite connection caching via `threading.local()`, avoiding connection churn while keeping database writes isolated.

### 3. Graceful Configuration Design
* **Polymorphic Config Loader**: The parser in `crawler_app.py` supports both lists and dictionaries. It automatically detects if a JSON config file is structured as a plain list or includes global metadata fields, providing clean backward compatibility:
  ```python
  if isinstance(config_data, list):
      sites_list = config_data
  elif isinstance(config_data, dict):
      # Extract outer configuration properties ...
  ```

---

## 🔍 Opportunities for Improvement & Production Bottlenecks

### 1. Scaling Bottleneck: Linear Jaccard Scans ($O(N)$ Complexity)
> [!WARNING]
> **Issue**: In `SimilarityIndexer.index_and_check()`, we perform a full linear scan over all signatures:
> `SELECT url, domain, title, html_content, extracted_text, date_crawled, text_signature FROM global_signatures WHERE url != ?`
>
> If the index grows to 100,000+ documents, fetching all binary signatures from disk and performing unpacking & Jaccard Jaccard calculations in Python will degrade performance, introducing worker bottlenecks.

* **Remediation**: Implement Locality-Sensitive Hashing (LSH) grouping.
  * Divide the 128-integer signature into $B$ bands of $R$ rows (e.g., 16 bands of 8 integers).
  * Build a lookup table in SQLite (`lsh_buckets(band_id INTEGER, bucket_hash TEXT, url TEXT)`) mapping bands to document URLs.
  * When indexing a page, only run the Jaccard comparison against document candidates that share at least one LSH bucket (hash collision). This reduces comparison lookups from $O(N)$ to near $O(1)$.

### 2. Lock Contention on WAL Central DB
> [!IMPORTANT]
> **Issue**: In multithreaded runs, dozens of concurrent worker threads write to the same single central database (`db/plagiarism_index.db`). Although WAL mode and `PRAGMA busy_timeout = 30000` are enabled, massive parallel writes can block threads and cause `sqlite3.OperationalError: database is locked` exceptions under heavy load.

* **Remediation**:
  * Decouple central similarity writes by pushing signature indexing tasks to a background thread queue (Producer-Consumer queue), allowing a single worker thread to perform write transactions in batches.

### 3. Exception Isolation (Fault Tolerance)
> [!CAUTION]
> **Issue**: If `indexer.index_and_check()` throws an operational exception (e.g. SQLite database locked, disk full, or transaction timeout), it is currently unhandled inside `crawl_page()`. This will crash the entire page crawl worker flow for that thread.

* **Remediation**: Wrap similarity check calls inside a `try/except` block inside `crawler_app.py` so that index errors are logged as warnings but do not interrupt the core crawling loop:
  ```python
  try:
      matches = self.indexer.index_and_check(...)
  except Exception as e:
      self.logger.error(f"Failed to check similarity index for {current_url}: {e}")
  ```

### 4. Memory Footprint of `cursor.fetchall()`
> [!TIP]
> **Issue**: Fetching all signatures, HTML content strings, and extracted text blocks using `cursor.fetchall()` loads all columns into memory at once. If documents contain large HTML page source code, this will dramatically increase memory consumption.

* **Remediation**:
  * Un-nest the SQL query. Instead of loading `html_content` and `extracted_text` for *all* signatures during similarity scoring, only fetch the `url` and `text_signature` columns for calculations.
  * Once a match is confirmed (Jaccard score $\ge$ threshold), query the database again to load the content strings for only the matching document.
  * Stream rows in batches using generator yields or `cursor.fetchmany(1000)` instead of pulling the whole dataset.

---

## 🛠️ Proposed Optimization Diff

Applying the memory optimization and exception safety fixes:

```diff
# in crawler_app.py: SiteCrawler.crawl_page()
-        if extracted.get("text"):
-            # Check for plagiarism / near-duplicates against the central index
-            matches = self.indexer.index_and_check(
-                url=current_url,
-                domain=self.domain,
-                title=extracted["title"] or "",
-                html_content=content,
-                extracted_text=extracted["text"],
-                date_crawled=datetime.now(),
-                threshold=self.plagiarism_threshold
-            )
-            for match in matches:
-                self.logger.warning(
-                    f"🚨 Plagiarism/Duplicate Detected! {current_url} is "
-                    f"{match['score']*100:.1f}% similar to {match['url']} ({match['title']})"
-                )
+        if extracted.get("text"):
+            try:
+                # Check for plagiarism / near-duplicates against the central index
+                matches = self.indexer.index_and_check(
+                    url=current_url,
+                    domain=self.domain,
+                    title=extracted["title"] or "",
+                    html_content=content,
+                    extracted_text=extracted["text"],
+                    date_crawled=datetime.now(),
+                    threshold=self.plagiarism_threshold
+                )
+                for match in matches:
+                    self.logger.warning(
+                        f"🚨 Plagiarism/Duplicate Detected! {current_url} is "
+                        f"{match['score']*100:.1f}% similar to {match['url']} ({match['title']})"
+                    )
+            except Exception as e:
+                self.logger.error(f"Error checking similarity for {current_url}: {e}")
```

```diff
# in similarity.py: SimilarityIndexer.index_and_check()
         with conn:
             # Query existing signatures to compare.
+            # Performance Optimization: Only select text_signature to avoid loading massive html_content into memory.
             cursor = conn.execute(
-                "SELECT url, domain, title, html_content, extracted_text, date_crawled, text_signature FROM global_signatures WHERE url != ?",
+                "SELECT url, domain, title, date_crawled, text_signature FROM global_signatures WHERE url != ?",
                 (url,)
             )
             rows = cursor.fetchall()

-            for other_url, other_domain, other_title, other_html, other_text, other_date, other_sig in rows:
+            for other_url, other_domain, other_title, other_date, other_sig in rows:
                 score = calculate_similarity(sig, other_sig)
                 if score >= threshold:
                     matches.append({
                         "url": other_url,
                         "domain": other_domain,
                         "title": other_title,
-                        "html_content": other_html,
-                        "extracted_text": other_text,
                         "date_crawled": other_date,
                         "score": score
                     })
```
