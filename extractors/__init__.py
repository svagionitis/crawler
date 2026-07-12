from .engines import (
    BaseExtractor,
    NewspaperExtractor,
    TrafilaturaExtractor,
    BS4Extractor,
    AutoExtractor,
    get_extractor,
)
from .base import BaseSiteExtractor
from .generic import GenericExtractor
from .news_sites import ALL_SITE_EXTRACTORS

# Registry of site-specific extractors.
_SITE_EXTRACTORS = ALL_SITE_EXTRACTORS


def get_site_extractor(url: str) -> BaseSiteExtractor:
    """Find a suitable site extractor for the given URL, defaulting to GenericExtractor."""
    for extractor_cls in _SITE_EXTRACTORS:
        if extractor_cls.suitable(url):
            return extractor_cls()
    return GenericExtractor()


__all__ = [
    "BaseExtractor",
    "NewspaperExtractor",
    "TrafilaturaExtractor",
    "BS4Extractor",
    "AutoExtractor",
    "get_extractor",
    "BaseSiteExtractor",
    "GenericExtractor",
    "get_site_extractor",
]
