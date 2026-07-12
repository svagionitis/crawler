import re
import logging
from abc import ABC, abstractmethod
from bs4 import BeautifulSoup


class BaseSiteExtractor(ABC):
    """Abstract base class for site-specific content extractors (InfoExtractor pattern)."""

    _VALID_URL = None  # Regular expression matching the URLs this extractor handles

    @classmethod
    def suitable(cls, url: str) -> bool:
        """Return True if this extractor is suitable for the given URL."""
        if cls._VALID_URL is None:
            return False
        return re.match(cls._VALID_URL, url) is not None

    @property
    @abstractmethod
    def name(self) -> str:
        """The name of the site extractor."""
        pass

    @abstractmethod
    def extract(
        self,
        html_content: str,
        url: str | None = None,
        soup: BeautifulSoup | None = None,
        parser_engine: str = "auto",
        normalize_whitespace: bool = True,
        logger: logging.Logger | None = None,
    ) -> dict:
        """Extract metadata (title, text, authors, date, keywords, parser_used) from page content."""
        pass
