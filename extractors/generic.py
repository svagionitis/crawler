import logging
from bs4 import BeautifulSoup
from .base import BaseSiteExtractor


class GenericExtractor(BaseSiteExtractor):
    """Fallback site extractor that uses generic library wrappers (trafilatura/newspaper3k)."""

    _VALID_URL = r".*"  # Matches everything as fallback

    @property
    def name(self) -> str:
        return "generic"

    def extract(
        self,
        html_content: str,
        url: str | None = None,
        soup: BeautifulSoup | None = None,
        parser_engine: str = "auto",
        normalize_whitespace: bool = True,
        logger: logging.Logger | None = None,
    ) -> dict:
        from utils import extract_article_content

        return extract_article_content(
            html_content,
            url=url,
            engine=parser_engine,
            soup=soup,
            normalize_whitespace=normalize_whitespace,
            logger=logger,
        )
