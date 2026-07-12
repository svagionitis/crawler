import os
import logging
from abc import ABC, abstractmethod
from bs4 import BeautifulSoup

# Optional imports for advanced article text extraction
try:
    import trafilatura
    from trafilatura.metadata import extract_metadata as trafilatura_extract_metadata

    HAS_TRAFILATURA = True
except ImportError:
    HAS_TRAFILATURA = False

try:
    import newspaper  # noqa: F401

    HAS_NEWSPAPER = True
except ImportError:
    HAS_NEWSPAPER = False


class BaseExtractor(ABC):
    """Abstract base class for content extraction strategies."""

    @property
    @abstractmethod
    def name(self) -> str:
        """The name of the extractor strategy."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the underlying parser library is installed and available."""
        pass

    @abstractmethod
    def extract(
        self,
        html_content: str,
        url: str | None = None,
        soup: BeautifulSoup | None = None,
        logger: logging.Logger | None = None,
    ) -> dict:
        """Extract the title, text, authors, publication date, and keywords from HTML content.

        Returns:
            dict: Dictionary containing title, text, authors, date, keywords, and parser_used.
        """
        pass


class NewspaperExtractor(BaseExtractor):
    """Content extraction strategy using newspaper3k."""

    @property
    def name(self) -> str:
        return "newspaper"

    def is_available(self) -> bool:
        return HAS_NEWSPAPER

    def extract(
        self,
        html_content: str,
        url: str | None = None,
        soup: BeautifulSoup | None = None,
        logger: logging.Logger | None = None,
    ) -> dict:
        if logger is None:
            logger = logging.getLogger(__name__)

        import tempfile

        # newspaper3k does not create its own temp directory on Windows, which
        # causes a WinError 3 ("path not found") on first use. Create it here
        # so the library can always find it.
        _newspaper_tmp = os.path.join(
            tempfile.gettempdir(), ".newspaper_scraper", "article_resources"
        )
        os.makedirs(_newspaper_tmp, exist_ok=True)

        from newspaper import Article

        article_url = url if url else "https://example.com"
        article = Article(article_url)
        article.set_html(html_content)
        article.parse()

        title = article.title
        text = article.text
        authors = ", ".join(article.authors) if article.authors else None

        date_str = None
        if article.publish_date:
            if hasattr(article.publish_date, "isoformat"):
                date_str = article.publish_date.isoformat()
            else:
                date_str = str(article.publish_date)

        keywords_str = None
        try:
            article.nlp()
            if article.keywords:
                keywords_str = ", ".join(article.keywords)
        except Exception:
            # Fallback if punkt dataset is missing
            pass

        return {
            "title": title.strip() if title else None,
            "text": text.strip() if text else None,
            "authors": authors.strip() if authors else None,
            "date": date_str.strip() if date_str else None,
            "keywords": keywords_str.strip() if keywords_str else None,
            "parser_used": self.name,
        }


class TrafilaturaExtractor(BaseExtractor):
    """Content extraction strategy using trafilatura."""

    @property
    def name(self) -> str:
        return "trafilatura"

    def is_available(self) -> bool:
        return HAS_TRAFILATURA

    def extract(
        self,
        html_content: str,
        url: str | None = None,
        soup: BeautifulSoup | None = None,
        logger: logging.Logger | None = None,
    ) -> dict:
        if logger is None:
            logger = logging.getLogger(__name__)

        text = trafilatura.extract(
            html_content, include_comments=False, no_fallback=False
        )

        metadata = None
        try:
            metadata = trafilatura_extract_metadata(html_content)
        except Exception:
            pass

        title = None
        authors = None
        date_str = None
        keywords_str = None

        if metadata:
            title = metadata.title
            authors = metadata.author
            date_str = metadata.date
            kws = []
            if metadata.categories:
                kws.extend(metadata.categories)
            if metadata.tags:
                kws.extend(metadata.tags)
            if kws:
                keywords_str = ", ".join(list(set(kws)))

        return {
            "title": title.strip() if title else None,
            "text": text.strip() if text else None,
            "authors": authors.strip() if authors else None,
            "date": date_str.strip() if date_str else None,
            "keywords": keywords_str.strip() if keywords_str else None,
            "parser_used": self.name,
        }


class BS4Extractor(BaseExtractor):
    """Content extraction strategy using standard BeautifulSoup (fallback boilerplate remover)."""

    @property
    def name(self) -> str:
        return "bs4"

    def is_available(self) -> bool:
        return True

    def extract(
        self,
        html_content: str,
        url: str | None = None,
        soup: BeautifulSoup | None = None,
        logger: logging.Logger | None = None,
    ) -> dict:
        if logger is None:
            logger = logging.getLogger(__name__)

        # Warning: if a pre-parsed soup is provided, this function will decompose
        # boilerplate elements in-place. Links must be extracted beforehand.
        if soup is None:
            soup = BeautifulSoup(html_content, "html.parser")

        title = None
        if soup.title and soup.title.string:
            title = soup.title.string.strip()
        if not title:
            h1 = soup.find("h1")
            if h1:
                title = h1.get_text(strip=True)

        authors = None
        author_meta = (
            soup.find("meta", attrs={"name": "author"})
            or soup.find("meta", attrs={"property": "article:author"})
            or soup.find("meta", attrs={"name": "twitter:creator"})
        )
        if author_meta and author_meta.get("content"):
            authors = author_meta["content"].strip()

        date_str = None
        date_meta = (
            soup.find("meta", attrs={"property": "article:published_time"})
            or soup.find("meta", attrs={"name": "pubdate"})
            or soup.find("meta", attrs={"name": "publish-date"})
            or soup.find("meta", attrs={"property": "og:article:published_time"})
        )
        if date_meta and date_meta.get("content"):
            date_str = date_meta["content"].strip()

        keywords_str = None
        keywords_meta = soup.find("meta", attrs={"name": "keywords"}) or soup.find(
            "meta", attrs={"name": "news_keywords"}
        )
        if keywords_meta and keywords_meta.get("content"):
            keywords_str = keywords_meta["content"].strip()

        # Decompose boilerplate elements
        for element in soup(
            ["script", "style", "nav", "footer", "header", "aside", "form", "iframe"]
        ):
            element.decompose()

        text_blocks = []
        paragraphs = soup.find_all("p")
        if paragraphs:
            for p in paragraphs:
                p_text = p.get_text(strip=True)
                if len(p_text) > 10:
                    text_blocks.append(p_text)
            text = "\n\n".join(text_blocks)
        else:
            text = soup.get_text("\n", strip=True)

        return {
            "title": title.strip() if title else None,
            "text": text.strip() if text else None,
            "authors": authors.strip() if authors else None,
            "date": date_str.strip() if date_str else None,
            "keywords": keywords_str.strip() if keywords_str else None,
            "parser_used": self.name,
        }


class AutoExtractor(BaseExtractor):
    """Composite extraction strategy that chains Newspaper, Trafilatura, and BS4 fallbacks."""

    def __init__(self):
        self._extractors = [
            NewspaperExtractor(),
            TrafilaturaExtractor(),
            BS4Extractor(),
        ]

    @property
    def name(self) -> str:
        return "auto"

    def is_available(self) -> bool:
        return True

    def extract(
        self,
        html_content: str,
        url: str | None = None,
        soup: BeautifulSoup | None = None,
        logger: logging.Logger | None = None,
    ) -> dict:
        if logger is None:
            logger = logging.getLogger(__name__)

        # Try to find the first available parser in preference order
        for extractor in self._extractors:
            if extractor.is_available() and extractor.name != "bs4":
                try:
                    return extractor.extract(
                        html_content, url=url, soup=soup, logger=logger
                    )
                except Exception as e:
                    logger.error(
                        f"Error during content extraction with engine {extractor.name}: {e}. "
                        "Attempting next fallback."
                    )

        # Fallback to BS4 if other methods fail or are not installed
        try:
            return BS4Extractor().extract(
                html_content, url=url, soup=soup, logger=logger
            )
        except Exception as e_fallback:
            logger.error(f"Critical error in fallback bs4 parser: {e_fallback}")

        return {
            "title": None,
            "text": None,
            "authors": None,
            "date": None,
            "keywords": None,
            "parser_used": None,
        }


def get_extractor(name: str) -> BaseExtractor:
    """Factory to retrieve an extractor instance by strategy name."""
    name = name.lower().strip()
    if name == "newspaper":
        return NewspaperExtractor()
    elif name == "trafilatura":
        return TrafilaturaExtractor()
    elif name == "bs4":
        return BS4Extractor()
    elif name == "auto":
        return AutoExtractor()
    else:
        # Fallback for unknown engines
        return BS4Extractor()
