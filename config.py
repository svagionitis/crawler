# User agent for the crawler
USER_AGENT = "Crawler/1.0 (+https://example.com/crawler)"

# Default setting to normalize all whitespaces (tabs, newlines) into a single space in extracted text
NORMALIZE_WHITESPACE = True

# Plagiarism and near-duplicate content configuration
PLAGIARISM_INDEX_DB = "db/plagiarism_index.db"
PLAGIARISM_THRESHOLD = 0.8  # Default 80% similarity threshold for near-duplicate checks
