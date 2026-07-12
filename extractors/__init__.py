import os
import json
import urllib.parse
import re

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

_SITE_EXTRACTORS = []


def _make_extract_method(domain_name):
    def extract_method(
        self,
        html_content,
        url=None,
        soup=None,
        parser_engine="auto",
        normalize_whitespace=True,
        logger=None,
    ):
        if logger:
            logger.info(f"Using site-specific extractor for {domain_name}")
        return GenericExtractor().extract(
            html_content,
            url=url,
            soup=soup,
            parser_engine=parser_engine,
            normalize_whitespace=normalize_whitespace,
            logger=logger,
        )

    return extract_method


# Dynamically generate and register extractors for all domains in news-sites-gr.json
try:
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "config",
        "news-sites-gr.json",
    )
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            config_data = json.load(f)
            for site in config_data.get("sites", []):
                url = site.get("url")
                if url:
                    parsed = urllib.parse.urlparse(url)
                    netloc = parsed.netloc.lower()
                    # Strip www.
                    domain = netloc[4:] if netloc.startswith("www.") else netloc
                    if not domain:
                        continue

                    # Create a clean camel-cased class name, e.g., TovimaExtractor
                    clean_domain = re.sub(r"[^a-zA-Z0-9]", " ", domain)
                    class_name = (
                        "".join(part.capitalize() for part in clean_domain.split())
                        + "Extractor"
                    )

                    # Build regex to match URL with or without subdomains/paths
                    regex = (
                        rf"^https?://(?:[a-zA-Z0-9\-]+\.)?{re.escape(domain)}(?:/.*)?$"
                    )

                    class_dict = {
                        "_VALID_URL": regex,
                        "name": domain,
                        "extract": _make_extract_method(domain),
                    }

                    # Create subclass dynamically
                    dynamic_cls = type(class_name, (BaseSiteExtractor,), class_dict)
                    _SITE_EXTRACTORS.append(dynamic_cls)
except Exception:
    pass


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
