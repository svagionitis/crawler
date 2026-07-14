# News Extractor Comparison Tool

This tool is designed to help you compare the quality, metadata completeness, and latency of different content extraction engines (`newspaper3k`, `trafilatura`, and the `BeautifulSoup4` fallback) side-by-side on the exact same crawled HTML content.

## Setup & Pre-requisites

Make sure your virtual environment is active and all parser libraries are installed:
```bash
pip install newspaper3k trafilatura beautifulsoup4
```

## How to Run

1. **Auto-Detect first Crawled DB**:
   If you have crawled databases saved under the standard `db/` folder:
   ```bash
   python scratch/compare_parsers.py
   ```

2. **Specify a Database File**:
   You can pass the path to a specific SQLite database to analyze its crawled content:
   ```bash
   python scratch/compare_parsers.py db/crawled_data_kathimerini.gr.db
   ```

## Output

The script generates a beautifully styled interactive dashboard:
* **File Location**: `scratch/parser_comparison_report.html`
* **Features**:
  * Shows title, authors, publication date, and character counts extracted by each engine.
  * Measures engine speed in milliseconds.
  * Shows a side-by-side visual text preview of the extracted content.
  * Simply open `scratch/parser_comparison_report.html` in any web browser to evaluate the results.
