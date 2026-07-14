import os
import sqlite3
import time
import sys
import glob

# Ensure project root is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from extractors.engines import NewspaperExtractor, TrafilaturaExtractor, Bs4Extractor  # noqa: E402


def run_comparison(
    database_path, limit=5, output_report="scratch/parser_comparison_report.html"
):
    if not os.path.exists(database_path):
        print(f"Error: Database file not found at '{database_path}'")
        return

    print(f"Connecting to database: {database_path}")
    conn = sqlite3.connect(database_path)
    cursor = conn.cursor()

    # Get rows with content
    cursor.execute(
        """
        SELECT link, content
        FROM crawled_data
        WHERE status = 'crawled' AND mime_type LIKE '%html%' AND content IS NOT NULL
        LIMIT ?
        """,
        (limit,),
    )
    rows = cursor.fetchall()

    if not rows:
        print("No crawled pages with HTML content found in database.")
        conn.close()
        return

    print(f"Evaluating {len(rows)} articles across 3 engines...")

    # Instantiate the extractors
    engines = {
        "Newspaper3k": NewspaperExtractor(),
        "Trafilatura": TrafilaturaExtractor(),
        "BeautifulSoup4 (Fallback)": Bs4Extractor(),
    }

    results = []

    for idx, (link, content) in enumerate(rows):
        print(f"[{idx+1}/{len(rows)}] Extracting: {link}")

        # If binary/base64 encoded (which shouldn't be for html text but just in case)
        if (
            isinstance(content, str)
            and content.startswith("ey")
            or (
                isinstance(content, str)
                and len(content) % 4 == 0
                and not content.strip().startswith("<")
            )
        ):
            try:
                import base64

                decoded_content = base64.b64decode(content).decode(
                    "utf-8", errors="ignore"
                )
            except Exception:
                decoded_content = content
        else:
            decoded_content = content

        article_eval = {"link": link, "extractions": {}}

        for name, engine in engines.items():
            if not engine.is_available():
                article_eval["extractions"][name] = {
                    "error": "Engine library not installed",
                    "title": "",
                    "text": "",
                    "authors": "",
                    "date": "",
                    "time_ms": 0,
                }
                continue

            start_time = time.perf_counter()
            try:
                data = engine.extract(decoded_content, url=link)
                elapsed_ms = (time.perf_counter() - start_time) * 1000

                article_eval["extractions"][name] = {
                    "title": data.get("title") or "N/A",
                    "text": data.get("text") or "",
                    "authors": data.get("authors") or "N/A",
                    "date": data.get("date") or "N/A",
                    "time_ms": round(elapsed_ms, 2),
                    "char_count": len(data.get("text") or ""),
                }
            except Exception as e:
                article_eval["extractions"][name] = {
                    "error": str(e),
                    "title": "",
                    "text": "",
                    "authors": "",
                    "date": "",
                    "time_ms": round((time.perf_counter() - start_time) * 1000, 2),
                }

        results.append(article_eval)

    conn.close()

    # Generate beautifully formatted HTML report
    generate_html_report(results, output_report)
    print(
        f"\nSuccess! Comparison report generated at: {os.path.abspath(output_report)}"
    )


def generate_html_report(results, filename):
    html = """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Echidna News Extractor Comparison Report</title>
    <style>
        body { font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background: #0f172a; color: #e2e8f0; margin: 0; padding: 20px; }
        h1 { color: #f8fafc; border-bottom: 2px solid #334155; padding-bottom: 10px; margin-bottom: 30px; }
        .article-card { background: #1e293b; border-radius: 8px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); margin-bottom: 40px; padding: 20px; border: 1px solid #475569; }
        .article-link { color: #38bdf8; font-size: 14px; text-decoration: none; word-break: break-all; }
        .article-link:hover { text-decoration: underline; }
        .grid-container { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 20px; margin-top: 20px; }
        .engine-panel { background: #0f172a; border-radius: 6px; padding: 15px; border: 1px solid #334155; }
        .engine-title { font-size: 18px; font-weight: bold; border-bottom: 1px solid #334155; padding-bottom: 5px; margin-bottom: 10px; display: flex; justify-content: space-between; }
        .engine-title.newspaper { color: #38bdf8; }
        .engine-title.trafilatura { color: #4ade80; }
        .engine-title.bs4 { color: #fbbf24; }
        .stat-badge { font-size: 12px; background: #334155; color: #f1f5f9; padding: 2px 8px; border-radius: 4px; font-weight: normal; }
        .meta-field { font-size: 13px; color: #94a3b8; margin: 5px 0; }
        .meta-value { color: #cbd5e1; font-weight: 500; }
        .text-preview { background: #1e293b; border: 1px solid #334155; padding: 10px; border-radius: 4px; max-height: 250px; overflow-y: auto; font-size: 13px; line-height: 1.5; color: #cbd5e1; white-space: pre-wrap; margin-top: 10px; }
        .error-preview { color: #ef4444; font-style: italic; }
    </style>
</head>
<body>
    <h1>Echidna Parser Comparison Report</h1>
    <p>This report compares article extraction output across different parser engines on identical HTML pages.</p>
"""
    for idx, res in enumerate(results):
        html += f"""
        <div class="article-card">
            <h3>Article #{idx+1}</h3>
            <a class="article-link" href="{res['link']}" target="_blank">{res['link']}</a>
            <div class="grid-container">
        """
        for name, ext in res["extractions"].items():
            class_map = {
                "Newspaper3k": "newspaper",
                "Trafilatura": "trafilatura",
                "BeautifulSoup4 (Fallback)": "bs4",
            }
            engine_class = class_map.get(name, "")

            html += f"""
                <div class="engine-panel">
                    <div class="engine-title {engine_class}">
                        <span>{name}</span>
                        <span class="stat-badge">{ext.get('time_ms', 0)} ms</span>
                    </div>
            """

            if "error" in ext:
                html += f'<div class="error-preview">Error: {ext["error"]}</div>'
            else:
                html += f"""
                    <div class="meta-field">Title: <span class="meta-value">{ext['title']}</span></div>
                    <div class="meta-field">Authors: <span class="meta-value">{ext['authors']}</span></div>
                    <div class="meta-field">Date: <span class="meta-value">{ext['date']}</span></div>
                    <div class="meta-field">Characters: <span class="stat-badge">{ext.get('char_count', 0)}</span></div>
                    <div class="text-preview">{ext['text'][:1200] + ("..." if len(ext['text']) > 1200 else "")}</div>
                """
            html += "</div>"
        html += "</div></div>"

    html += """
</body>
</html>
"""
    with open(filename, "w", encoding="utf-8") as f:
        f.write(html)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        run_comparison(sys.argv[1])
    else:
        # Auto-detect first database in db/ directory if none provided
        db_files = glob.glob("db/crawled_data_*.db")
        if db_files:
            run_comparison(db_files[0])
        else:
            print("Error: No database path specified and none auto-detected in 'db/'.")
            print("Usage: python scratch/compare_parsers.py <path_to_db>")
