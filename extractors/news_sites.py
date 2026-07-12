# This file is auto-generated containing site-specific extractors for all configured domains.

import logging
from bs4 import BeautifulSoup
from .base import BaseSiteExtractor
from .generic import GenericExtractor


class Site1voiceGrExtractor(BaseSiteExtractor):
    _VALID_URL = r"^https?://(?:[a-zA-Z0-9\-]+\.)?1voice\.gr(?:/.*)?$"

    @property
    def name(self) -> str:
        return "1voice.gr"

    def extract(
        self,
        html_content: str,
        url: str | None = None,
        soup: BeautifulSoup | None = None,
        parser_engine: str = "auto",
        normalize_whitespace: bool = True,
        logger: logging.Logger | None = None,
    ) -> dict:
        if logger:
            logger.info("Using site-specific extractor for 1voice.gr")
        return GenericExtractor().extract(
            html_content,
            url=url,
            soup=soup,
            parser_engine=parser_engine,
            normalize_whitespace=normalize_whitespace,
            logger=logger,
        )


class AlphanewsLiveExtractor(BaseSiteExtractor):
    _VALID_URL = r"^https?://(?:[a-zA-Z0-9\-]+\.)?alphanews\.live(?:/.*)?$"

    @property
    def name(self) -> str:
        return "alphanews.live"

    def extract(
        self,
        html_content: str,
        url: str | None = None,
        soup: BeautifulSoup | None = None,
        parser_engine: str = "auto",
        normalize_whitespace: bool = True,
        logger: logging.Logger | None = None,
    ) -> dict:
        if logger:
            logger.info("Using site-specific extractor for alphanews.live")
        return GenericExtractor().extract(
            html_content,
            url=url,
            soup=soup,
            parser_engine=parser_engine,
            normalize_whitespace=normalize_whitespace,
            logger=logger,
        )


class AlphatvGrExtractor(BaseSiteExtractor):
    _VALID_URL = r"^https?://(?:[a-zA-Z0-9\-]+\.)?alphatv\.gr(?:/.*)?$"

    @property
    def name(self) -> str:
        return "alphatv.gr"

    def extract(
        self,
        html_content: str,
        url: str | None = None,
        soup: BeautifulSoup | None = None,
        parser_engine: str = "auto",
        normalize_whitespace: bool = True,
        logger: logging.Logger | None = None,
    ) -> dict:
        if logger:
            logger.info("Using site-specific extractor for alphatv.gr")
        return GenericExtractor().extract(
            html_content,
            url=url,
            soup=soup,
            parser_engine=parser_engine,
            normalize_whitespace=normalize_whitespace,
            logger=logger,
        )


class AntennaGrExtractor(BaseSiteExtractor):
    _VALID_URL = r"^https?://(?:[a-zA-Z0-9\-]+\.)?antenna\.gr(?:/.*)?$"

    @property
    def name(self) -> str:
        return "antenna.gr"

    def extract(
        self,
        html_content: str,
        url: str | None = None,
        soup: BeautifulSoup | None = None,
        parser_engine: str = "auto",
        normalize_whitespace: bool = True,
        logger: logging.Logger | None = None,
    ) -> dict:
        if logger:
            logger.info("Using site-specific extractor for antenna.gr")
        return GenericExtractor().extract(
            html_content,
            url=url,
            soup=soup,
            parser_engine=parser_engine,
            normalize_whitespace=normalize_whitespace,
            logger=logger,
        )


class AtticatimesGrExtractor(BaseSiteExtractor):
    _VALID_URL = r"^https?://(?:[a-zA-Z0-9\-]+\.)?atticatimes\.gr(?:/.*)?$"

    @property
    def name(self) -> str:
        return "atticatimes.gr"

    def extract(
        self,
        html_content: str,
        url: str | None = None,
        soup: BeautifulSoup | None = None,
        parser_engine: str = "auto",
        normalize_whitespace: bool = True,
        logger: logging.Logger | None = None,
    ) -> dict:
        if logger:
            logger.info("Using site-specific extractor for atticatimes.gr")
        return GenericExtractor().extract(
            html_content,
            url=url,
            soup=soup,
            parser_engine=parser_engine,
            normalize_whitespace=normalize_whitespace,
            logger=logger,
        )


class DimokratiaGrExtractor(BaseSiteExtractor):
    _VALID_URL = r"^https?://(?:[a-zA-Z0-9\-]+\.)?dimokratia\.gr(?:/.*)?$"

    @property
    def name(self) -> str:
        return "dimokratia.gr"

    def extract(
        self,
        html_content: str,
        url: str | None = None,
        soup: BeautifulSoup | None = None,
        parser_engine: str = "auto",
        normalize_whitespace: bool = True,
        logger: logging.Logger | None = None,
    ) -> dict:
        if logger:
            logger.info("Using site-specific extractor for dimokratia.gr")
        return GenericExtractor().extract(
            html_content,
            url=url,
            soup=soup,
            parser_engine=parser_engine,
            normalize_whitespace=normalize_whitespace,
            logger=logger,
        )


class DocumentonewsGrExtractor(BaseSiteExtractor):
    _VALID_URL = r"^https?://(?:[a-zA-Z0-9\-]+\.)?documentonews\.gr(?:/.*)?$"

    @property
    def name(self) -> str:
        return "documentonews.gr"

    def extract(
        self,
        html_content: str,
        url: str | None = None,
        soup: BeautifulSoup | None = None,
        parser_engine: str = "auto",
        normalize_whitespace: bool = True,
        logger: logging.Logger | None = None,
    ) -> dict:
        if logger:
            logger.info("Using site-specific extractor for documentonews.gr")
        return GenericExtractor().extract(
            html_content,
            url=url,
            soup=soup,
            parser_engine=parser_engine,
            normalize_whitespace=normalize_whitespace,
            logger=logger,
        )


class EfsynGrExtractor(BaseSiteExtractor):
    _VALID_URL = r"^https?://(?:[a-zA-Z0-9\-]+\.)?efsyn\.gr(?:/.*)?$"

    @property
    def name(self) -> str:
        return "efsyn.gr"

    def extract(
        self,
        html_content: str,
        url: str | None = None,
        soup: BeautifulSoup | None = None,
        parser_engine: str = "auto",
        normalize_whitespace: bool = True,
        logger: logging.Logger | None = None,
    ) -> dict:
        if logger:
            logger.info("Using site-specific extractor for efsyn.gr")
        return GenericExtractor().extract(
            html_content,
            url=url,
            soup=soup,
            parser_engine=parser_engine,
            normalize_whitespace=normalize_whitespace,
            logger=logger,
        )


class EkirikasComExtractor(BaseSiteExtractor):
    _VALID_URL = r"^https?://(?:[a-zA-Z0-9\-]+\.)?ekirikas\.com(?:/.*)?$"

    @property
    def name(self) -> str:
        return "ekirikas.com"

    def extract(
        self,
        html_content: str,
        url: str | None = None,
        soup: BeautifulSoup | None = None,
        parser_engine: str = "auto",
        normalize_whitespace: bool = True,
        logger: logging.Logger | None = None,
    ) -> dict:
        if logger:
            logger.info("Using site-specific extractor for ekirikas.com")
        return GenericExtractor().extract(
            html_content,
            url=url,
            soup=soup,
            parser_engine=parser_engine,
            normalize_whitespace=normalize_whitespace,
            logger=logger,
        )


class EleftherostyposGrExtractor(BaseSiteExtractor):
    _VALID_URL = r"^https?://(?:[a-zA-Z0-9\-]+\.)?eleftherostypos\.gr(?:/.*)?$"

    @property
    def name(self) -> str:
        return "eleftherostypos.gr"

    def extract(
        self,
        html_content: str,
        url: str | None = None,
        soup: BeautifulSoup | None = None,
        parser_engine: str = "auto",
        normalize_whitespace: bool = True,
        logger: logging.Logger | None = None,
    ) -> dict:
        if logger:
            logger.info("Using site-specific extractor for eleftherostypos.gr")
        return GenericExtractor().extract(
            html_content,
            url=url,
            soup=soup,
            parser_engine=parser_engine,
            normalize_whitespace=normalize_whitespace,
            logger=logger,
        )


class EloraGrExtractor(BaseSiteExtractor):
    _VALID_URL = r"^https?://(?:[a-zA-Z0-9\-]+\.)?elora\.gr(?:/.*)?$"

    @property
    def name(self) -> str:
        return "elora.gr"

    def extract(
        self,
        html_content: str,
        url: str | None = None,
        soup: BeautifulSoup | None = None,
        parser_engine: str = "auto",
        normalize_whitespace: bool = True,
        logger: logging.Logger | None = None,
    ) -> dict:
        if logger:
            logger.info("Using site-specific extractor for elora.gr")
        return GenericExtractor().extract(
            html_content,
            url=url,
            soup=soup,
            parser_engine=parser_engine,
            normalize_whitespace=normalize_whitespace,
            logger=logger,
        )


class EnikosGrExtractor(BaseSiteExtractor):
    _VALID_URL = r"^https?://(?:[a-zA-Z0-9\-]+\.)?enikos\.gr(?:/.*)?$"

    @property
    def name(self) -> str:
        return "enikos.gr"

    def extract(
        self,
        html_content: str,
        url: str | None = None,
        soup: BeautifulSoup | None = None,
        parser_engine: str = "auto",
        normalize_whitespace: bool = True,
        logger: logging.Logger | None = None,
    ) -> dict:
        if logger:
            logger.info("Using site-specific extractor for enikos.gr")
        return GenericExtractor().extract(
            html_content,
            url=url,
            soup=soup,
            parser_engine=parser_engine,
            normalize_whitespace=normalize_whitespace,
            logger=logger,
        )


class ErtGrExtractor(BaseSiteExtractor):
    _VALID_URL = r"^https?://(?:[a-zA-Z0-9\-]+\.)?ert\.gr(?:/.*)?$"

    @property
    def name(self) -> str:
        return "ert.gr"

    def extract(
        self,
        html_content: str,
        url: str | None = None,
        soup: BeautifulSoup | None = None,
        parser_engine: str = "auto",
        normalize_whitespace: bool = True,
        logger: logging.Logger | None = None,
    ) -> dict:
        if logger:
            logger.info("Using site-specific extractor for ert.gr")
        return GenericExtractor().extract(
            html_content,
            url=url,
            soup=soup,
            parser_engine=parser_engine,
            normalize_whitespace=normalize_whitespace,
            logger=logger,
        )


class ErtnewsGrExtractor(BaseSiteExtractor):
    _VALID_URL = r"^https?://(?:[a-zA-Z0-9\-]+\.)?ertnews\.gr(?:/.*)?$"

    @property
    def name(self) -> str:
        return "ertnews.gr"

    def extract(
        self,
        html_content: str,
        url: str | None = None,
        soup: BeautifulSoup | None = None,
        parser_engine: str = "auto",
        normalize_whitespace: bool = True,
        logger: logging.Logger | None = None,
    ) -> dict:
        if logger:
            logger.info("Using site-specific extractor for ertnews.gr")
        return GenericExtractor().extract(
            html_content,
            url=url,
            soup=soup,
            parser_engine=parser_engine,
            normalize_whitespace=normalize_whitespace,
            logger=logger,
        )


class EspressonewsGrExtractor(BaseSiteExtractor):
    _VALID_URL = r"^https?://(?:[a-zA-Z0-9\-]+\.)?espressonews\.gr(?:/.*)?$"

    @property
    def name(self) -> str:
        return "espressonews.gr"

    def extract(
        self,
        html_content: str,
        url: str | None = None,
        soup: BeautifulSoup | None = None,
        parser_engine: str = "auto",
        normalize_whitespace: bool = True,
        logger: logging.Logger | None = None,
    ) -> dict:
        if logger:
            logger.info("Using site-specific extractor for espressonews.gr")
        return GenericExtractor().extract(
            html_content,
            url=url,
            soup=soup,
            parser_engine=parser_engine,
            normalize_whitespace=normalize_whitespace,
            logger=logger,
        )


class EstianewsGrExtractor(BaseSiteExtractor):
    _VALID_URL = r"^https?://(?:[a-zA-Z0-9\-]+\.)?estianews\.gr(?:/.*)?$"

    @property
    def name(self) -> str:
        return "estianews.gr"

    def extract(
        self,
        html_content: str,
        url: str | None = None,
        soup: BeautifulSoup | None = None,
        parser_engine: str = "auto",
        normalize_whitespace: bool = True,
        logger: logging.Logger | None = None,
    ) -> dict:
        if logger:
            logger.info("Using site-specific extractor for estianews.gr")
        return GenericExtractor().extract(
            html_content,
            url=url,
            soup=soup,
            parser_engine=parser_engine,
            normalize_whitespace=normalize_whitespace,
            logger=logger,
        )


class EthnosGrExtractor(BaseSiteExtractor):
    _VALID_URL = r"^https?://(?:[a-zA-Z0-9\-]+\.)?ethnos\.gr(?:/.*)?$"

    @property
    def name(self) -> str:
        return "ethnos.gr"

    def extract(
        self,
        html_content: str,
        url: str | None = None,
        soup: BeautifulSoup | None = None,
        parser_engine: str = "auto",
        normalize_whitespace: bool = True,
        logger: logging.Logger | None = None,
    ) -> dict:
        if logger:
            logger.info("Using site-specific extractor for ethnos.gr")
        return GenericExtractor().extract(
            html_content,
            url=url,
            soup=soup,
            parser_engine=parser_engine,
            normalize_whitespace=normalize_whitespace,
            logger=logger,
        )


class IapogevmatiniGrExtractor(BaseSiteExtractor):
    _VALID_URL = r"^https?://(?:[a-zA-Z0-9\-]+\.)?iapogevmatini\.gr(?:/.*)?$"

    @property
    def name(self) -> str:
        return "iapogevmatini.gr"

    def extract(
        self,
        html_content: str,
        url: str | None = None,
        soup: BeautifulSoup | None = None,
        parser_engine: str = "auto",
        normalize_whitespace: bool = True,
        logger: logging.Logger | None = None,
    ) -> dict:
        if logger:
            logger.info("Using site-specific extractor for iapogevmatini.gr")
        return GenericExtractor().extract(
            html_content,
            url=url,
            soup=soup,
            parser_engine=parser_engine,
            normalize_whitespace=normalize_whitespace,
            logger=logger,
        )


class IefimeridaGrExtractor(BaseSiteExtractor):
    _VALID_URL = r"^https?://(?:[a-zA-Z0-9\-]+\.)?iefimerida\.gr(?:/.*)?$"

    @property
    def name(self) -> str:
        return "iefimerida.gr"

    def extract(
        self,
        html_content: str,
        url: str | None = None,
        soup: BeautifulSoup | None = None,
        parser_engine: str = "auto",
        normalize_whitespace: bool = True,
        logger: logging.Logger | None = None,
    ) -> dict:
        if logger:
            logger.info("Using site-specific extractor for iefimerida.gr")
        return GenericExtractor().extract(
            html_content,
            url=url,
            soup=soup,
            parser_engine=parser_engine,
            normalize_whitespace=normalize_whitespace,
            logger=logger,
        )


class InGrExtractor(BaseSiteExtractor):
    _VALID_URL = r"^https?://(?:[a-zA-Z0-9\-]+\.)?in\.gr(?:/.*)?$"

    @property
    def name(self) -> str:
        return "in.gr"

    def extract(
        self,
        html_content: str,
        url: str | None = None,
        soup: BeautifulSoup | None = None,
        parser_engine: str = "auto",
        normalize_whitespace: bool = True,
        logger: logging.Logger | None = None,
    ) -> dict:
        if logger:
            logger.info("Using site-specific extractor for in.gr")
        return GenericExtractor().extract(
            html_content,
            url=url,
            soup=soup,
            parser_engine=parser_engine,
            normalize_whitespace=normalize_whitespace,
            logger=logger,
        )


class InkefaloniaGrExtractor(BaseSiteExtractor):
    _VALID_URL = r"^https?://(?:[a-zA-Z0-9\-]+\.)?inkefalonia\.gr(?:/.*)?$"

    @property
    def name(self) -> str:
        return "inkefalonia.gr"

    def extract(
        self,
        html_content: str,
        url: str | None = None,
        soup: BeautifulSoup | None = None,
        parser_engine: str = "auto",
        normalize_whitespace: bool = True,
        logger: logging.Logger | None = None,
    ) -> dict:
        if logger:
            logger.info("Using site-specific extractor for inkefalonia.gr")
        return GenericExtractor().extract(
            html_content,
            url=url,
            soup=soup,
            parser_engine=parser_engine,
            normalize_whitespace=normalize_whitespace,
            logger=logger,
        )


class IpaperGrExtractor(BaseSiteExtractor):
    _VALID_URL = r"^https?://(?:[a-zA-Z0-9\-]+\.)?ipaper\.gr(?:/.*)?$"

    @property
    def name(self) -> str:
        return "ipaper.gr"

    def extract(
        self,
        html_content: str,
        url: str | None = None,
        soup: BeautifulSoup | None = None,
        parser_engine: str = "auto",
        normalize_whitespace: bool = True,
        logger: logging.Logger | None = None,
    ) -> dict:
        if logger:
            logger.info("Using site-specific extractor for ipaper.gr")
        return GenericExtractor().extract(
            html_content,
            url=url,
            soup=soup,
            parser_engine=parser_engine,
            normalize_whitespace=normalize_whitespace,
            logger=logger,
        )


class KathimeriniGrExtractor(BaseSiteExtractor):
    _VALID_URL = r"^https?://(?:[a-zA-Z0-9\-]+\.)?kathimerini\.gr(?:/.*)?$"

    @property
    def name(self) -> str:
        return "kathimerini.gr"

    def extract(
        self,
        html_content: str,
        url: str | None = None,
        soup: BeautifulSoup | None = None,
        parser_engine: str = "auto",
        normalize_whitespace: bool = True,
        logger: logging.Logger | None = None,
    ) -> dict:
        if logger:
            logger.info("Using site-specific extractor for kathimerini.gr")
        return GenericExtractor().extract(
            html_content,
            url=url,
            soup=soup,
            parser_engine=parser_engine,
            normalize_whitespace=normalize_whitespace,
            logger=logger,
        )


class KefaloniapressGrExtractor(BaseSiteExtractor):
    _VALID_URL = r"^https?://(?:[a-zA-Z0-9\-]+\.)?kefaloniapress\.gr(?:/.*)?$"

    @property
    def name(self) -> str:
        return "kefaloniapress.gr"

    def extract(
        self,
        html_content: str,
        url: str | None = None,
        soup: BeautifulSoup | None = None,
        parser_engine: str = "auto",
        normalize_whitespace: bool = True,
        logger: logging.Logger | None = None,
    ) -> dict:
        if logger:
            logger.info("Using site-specific extractor for kefaloniapress.gr")
        return GenericExtractor().extract(
            html_content,
            url=url,
            soup=soup,
            parser_engine=parser_engine,
            normalize_whitespace=normalize_whitespace,
            logger=logger,
        )


class KontranewsGrExtractor(BaseSiteExtractor):
    _VALID_URL = r"^https?://(?:[a-zA-Z0-9\-]+\.)?kontranews\.gr(?:/.*)?$"

    @property
    def name(self) -> str:
        return "kontranews.gr"

    def extract(
        self,
        html_content: str,
        url: str | None = None,
        soup: BeautifulSoup | None = None,
        parser_engine: str = "auto",
        normalize_whitespace: bool = True,
        logger: logging.Logger | None = None,
    ) -> dict:
        if logger:
            logger.info("Using site-specific extractor for kontranews.gr")
        return GenericExtractor().extract(
            html_content,
            url=url,
            soup=soup,
            parser_engine=parser_engine,
            normalize_whitespace=normalize_whitespace,
            logger=logger,
        )


class KoutipandorasGrExtractor(BaseSiteExtractor):
    _VALID_URL = r"^https?://(?:[a-zA-Z0-9\-]+\.)?koutipandoras\.gr(?:/.*)?$"

    @property
    def name(self) -> str:
        return "koutipandoras.gr"

    def extract(
        self,
        html_content: str,
        url: str | None = None,
        soup: BeautifulSoup | None = None,
        parser_engine: str = "auto",
        normalize_whitespace: bool = True,
        logger: logging.Logger | None = None,
    ) -> dict:
        if logger:
            logger.info("Using site-specific extractor for koutipandoras.gr")
        return GenericExtractor().extract(
            html_content,
            url=url,
            soup=soup,
            parser_engine=parser_engine,
            normalize_whitespace=normalize_whitespace,
            logger=logger,
        )


class LifoGrExtractor(BaseSiteExtractor):
    _VALID_URL = r"^https?://(?:[a-zA-Z0-9\-]+\.)?lifo\.gr(?:/.*)?$"

    @property
    def name(self) -> str:
        return "lifo.gr"

    def extract(
        self,
        html_content: str,
        url: str | None = None,
        soup: BeautifulSoup | None = None,
        parser_engine: str = "auto",
        normalize_whitespace: bool = True,
        logger: logging.Logger | None = None,
    ) -> dict:
        if logger:
            logger.info("Using site-specific extractor for lifo.gr")
        return GenericExtractor().extract(
            html_content,
            url=url,
            soup=soup,
            parser_engine=parser_engine,
            normalize_whitespace=normalize_whitespace,
            logger=logger,
        )


class MakeleioGrExtractor(BaseSiteExtractor):
    _VALID_URL = r"^https?://(?:[a-zA-Z0-9\-]+\.)?makeleio\.gr(?:/.*)?$"

    @property
    def name(self) -> str:
        return "makeleio.gr"

    def extract(
        self,
        html_content: str,
        url: str | None = None,
        soup: BeautifulSoup | None = None,
        parser_engine: str = "auto",
        normalize_whitespace: bool = True,
        logger: logging.Logger | None = None,
    ) -> dict:
        if logger:
            logger.info("Using site-specific extractor for makeleio.gr")
        return GenericExtractor().extract(
            html_content,
            url=url,
            soup=soup,
            parser_engine=parser_engine,
            normalize_whitespace=normalize_whitespace,
            logger=logger,
        )


class MegatvComExtractor(BaseSiteExtractor):
    _VALID_URL = r"^https?://(?:[a-zA-Z0-9\-]+\.)?megatv\.com(?:/.*)?$"

    @property
    def name(self) -> str:
        return "megatv.com"

    def extract(
        self,
        html_content: str,
        url: str | None = None,
        soup: BeautifulSoup | None = None,
        parser_engine: str = "auto",
        normalize_whitespace: bool = True,
        logger: logging.Logger | None = None,
    ) -> dict:
        if logger:
            logger.info("Using site-specific extractor for megatv.com")
        return GenericExtractor().extract(
            html_content,
            url=url,
            soup=soup,
            parser_engine=parser_engine,
            normalize_whitespace=normalize_whitespace,
            logger=logger,
        )


class NaftemporikiGrExtractor(BaseSiteExtractor):
    _VALID_URL = r"^https?://(?:[a-zA-Z0-9\-]+\.)?naftemporiki\.gr(?:/.*)?$"

    @property
    def name(self) -> str:
        return "naftemporiki.gr"

    def extract(
        self,
        html_content: str,
        url: str | None = None,
        soup: BeautifulSoup | None = None,
        parser_engine: str = "auto",
        normalize_whitespace: bool = True,
        logger: logging.Logger | None = None,
    ) -> dict:
        if logger:
            logger.info("Using site-specific extractor for naftemporiki.gr")
        return GenericExtractor().extract(
            html_content,
            url=url,
            soup=soup,
            parser_engine=parser_engine,
            normalize_whitespace=normalize_whitespace,
            logger=logger,
        )


class News247GrExtractor(BaseSiteExtractor):
    _VALID_URL = r"^https?://(?:[a-zA-Z0-9\-]+\.)?news247\.gr(?:/.*)?$"

    @property
    def name(self) -> str:
        return "news247.gr"

    def extract(
        self,
        html_content: str,
        url: str | None = None,
        soup: BeautifulSoup | None = None,
        parser_engine: str = "auto",
        normalize_whitespace: bool = True,
        logger: logging.Logger | None = None,
    ) -> dict:
        if logger:
            logger.info("Using site-specific extractor for news247.gr")
        return GenericExtractor().extract(
            html_content,
            url=url,
            soup=soup,
            parser_engine=parser_engine,
            normalize_whitespace=normalize_whitespace,
            logger=logger,
        )


class NewsbombGrExtractor(BaseSiteExtractor):
    _VALID_URL = r"^https?://(?:[a-zA-Z0-9\-]+\.)?newsbomb\.gr(?:/.*)?$"

    @property
    def name(self) -> str:
        return "newsbomb.gr"

    def extract(
        self,
        html_content: str,
        url: str | None = None,
        soup: BeautifulSoup | None = None,
        parser_engine: str = "auto",
        normalize_whitespace: bool = True,
        logger: logging.Logger | None = None,
    ) -> dict:
        if logger:
            logger.info("Using site-specific extractor for newsbomb.gr")
        return GenericExtractor().extract(
            html_content,
            url=url,
            soup=soup,
            parser_engine=parser_engine,
            normalize_whitespace=normalize_whitespace,
            logger=logger,
        )


class ProtothemaGrExtractor(BaseSiteExtractor):
    _VALID_URL = r"^https?://(?:[a-zA-Z0-9\-]+\.)?protothema\.gr(?:/.*)?$"

    @property
    def name(self) -> str:
        return "protothema.gr"

    def extract(
        self,
        html_content: str,
        url: str | None = None,
        soup: BeautifulSoup | None = None,
        parser_engine: str = "auto",
        normalize_whitespace: bool = True,
        logger: logging.Logger | None = None,
    ) -> dict:
        if logger:
            logger.info("Using site-specific extractor for protothema.gr")
        return GenericExtractor().extract(
            html_content,
            url=url,
            soup=soup,
            parser_engine=parser_engine,
            normalize_whitespace=normalize_whitespace,
            logger=logger,
        )


class RealGrExtractor(BaseSiteExtractor):
    _VALID_URL = r"^https?://(?:[a-zA-Z0-9\-]+\.)?real\.gr(?:/.*)?$"

    @property
    def name(self) -> str:
        return "real.gr"

    def extract(
        self,
        html_content: str,
        url: str | None = None,
        soup: BeautifulSoup | None = None,
        parser_engine: str = "auto",
        normalize_whitespace: bool = True,
        logger: logging.Logger | None = None,
    ) -> dict:
        if logger:
            logger.info("Using site-specific extractor for real.gr")
        return GenericExtractor().extract(
            html_content,
            url=url,
            soup=soup,
            parser_engine=parser_engine,
            normalize_whitespace=normalize_whitespace,
            logger=logger,
        )


class RizospastisGrExtractor(BaseSiteExtractor):
    _VALID_URL = r"^https?://(?:[a-zA-Z0-9\-]+\.)?rizospastis\.gr(?:/.*)?$"

    @property
    def name(self) -> str:
        return "rizospastis.gr"

    def extract(
        self,
        html_content: str,
        url: str | None = None,
        soup: BeautifulSoup | None = None,
        parser_engine: str = "auto",
        normalize_whitespace: bool = True,
        logger: logging.Logger | None = None,
    ) -> dict:
        if logger:
            logger.info("Using site-specific extractor for rizospastis.gr")
        return GenericExtractor().extract(
            html_content,
            url=url,
            soup=soup,
            parser_engine=parser_engine,
            normalize_whitespace=normalize_whitespace,
            logger=logger,
        )


class SkaiGrExtractor(BaseSiteExtractor):
    _VALID_URL = r"^https?://(?:[a-zA-Z0-9\-]+\.)?skai\.gr(?:/.*)?$"

    @property
    def name(self) -> str:
        return "skai.gr"

    def extract(
        self,
        html_content: str,
        url: str | None = None,
        soup: BeautifulSoup | None = None,
        parser_engine: str = "auto",
        normalize_whitespace: bool = True,
        logger: logging.Logger | None = None,
    ) -> dict:
        if logger:
            logger.info("Using site-specific extractor for skai.gr")
        return GenericExtractor().extract(
            html_content,
            url=url,
            soup=soup,
            parser_engine=parser_engine,
            normalize_whitespace=normalize_whitespace,
            logger=logger,
        )


class StarGrExtractor(BaseSiteExtractor):
    _VALID_URL = r"^https?://(?:[a-zA-Z0-9\-]+\.)?star\.gr(?:/.*)?$"

    @property
    def name(self) -> str:
        return "star.gr"

    def extract(
        self,
        html_content: str,
        url: str | None = None,
        soup: BeautifulSoup | None = None,
        parser_engine: str = "auto",
        normalize_whitespace: bool = True,
        logger: logging.Logger | None = None,
    ) -> dict:
        if logger:
            logger.info("Using site-specific extractor for star.gr")
        return GenericExtractor().extract(
            html_content,
            url=url,
            soup=soup,
            parser_engine=parser_engine,
            normalize_whitespace=normalize_whitespace,
            logger=logger,
        )


class TaneaGrExtractor(BaseSiteExtractor):
    _VALID_URL = r"^https?://(?:[a-zA-Z0-9\-]+\.)?tanea\.gr(?:/.*)?$"

    @property
    def name(self) -> str:
        return "tanea.gr"

    def extract(
        self,
        html_content: str,
        url: str | None = None,
        soup: BeautifulSoup | None = None,
        parser_engine: str = "auto",
        normalize_whitespace: bool = True,
        logger: logging.Logger | None = None,
    ) -> dict:
        if logger:
            logger.info("Using site-specific extractor for tanea.gr")
        return GenericExtractor().extract(
            html_content,
            url=url,
            soup=soup,
            parser_engine=parser_engine,
            normalize_whitespace=normalize_whitespace,
            logger=logger,
        )


class TomanifestoGrExtractor(BaseSiteExtractor):
    _VALID_URL = r"^https?://(?:[a-zA-Z0-9\-]+\.)?tomanifesto\.gr(?:/.*)?$"

    @property
    def name(self) -> str:
        return "tomanifesto.gr"

    def extract(
        self,
        html_content: str,
        url: str | None = None,
        soup: BeautifulSoup | None = None,
        parser_engine: str = "auto",
        normalize_whitespace: bool = True,
        logger: logging.Logger | None = None,
    ) -> dict:
        if logger:
            logger.info("Using site-specific extractor for tomanifesto.gr")
        return GenericExtractor().extract(
            html_content,
            url=url,
            soup=soup,
            parser_engine=parser_engine,
            normalize_whitespace=normalize_whitespace,
            logger=logger,
        )


class TovimaGrExtractor(BaseSiteExtractor):
    _VALID_URL = r"^https?://(?:[a-zA-Z0-9\-]+\.)?tovima\.gr(?:/.*)?$"

    @property
    def name(self) -> str:
        return "tovima.gr"

    def extract(
        self,
        html_content: str,
        url: str | None = None,
        soup: BeautifulSoup | None = None,
        parser_engine: str = "auto",
        normalize_whitespace: bool = True,
        logger: logging.Logger | None = None,
    ) -> dict:
        if logger:
            logger.info("Using site-specific extractor for tovima.gr")
        return GenericExtractor().extract(
            html_content,
            url=url,
            soup=soup,
            parser_engine=parser_engine,
            normalize_whitespace=normalize_whitespace,
            logger=logger,
        )


class TvopenGrExtractor(BaseSiteExtractor):
    _VALID_URL = r"^https?://(?:[a-zA-Z0-9\-]+\.)?tvopen\.gr(?:/.*)?$"

    @property
    def name(self) -> str:
        return "tvopen.gr"

    def extract(
        self,
        html_content: str,
        url: str | None = None,
        soup: BeautifulSoup | None = None,
        parser_engine: str = "auto",
        normalize_whitespace: bool = True,
        logger: logging.Logger | None = None,
    ) -> dict:
        if logger:
            logger.info("Using site-specific extractor for tvopen.gr")
        return GenericExtractor().extract(
            html_content,
            url=url,
            soup=soup,
            parser_engine=parser_engine,
            normalize_whitespace=normalize_whitespace,
            logger=logger,
        )


class ZouglaGrExtractor(BaseSiteExtractor):
    _VALID_URL = r"^https?://(?:[a-zA-Z0-9\-]+\.)?zougla\.gr(?:/.*)?$"

    @property
    def name(self) -> str:
        return "zougla.gr"

    def extract(
        self,
        html_content: str,
        url: str | None = None,
        soup: BeautifulSoup | None = None,
        parser_engine: str = "auto",
        normalize_whitespace: bool = True,
        logger: logging.Logger | None = None,
    ) -> dict:
        if logger:
            logger.info("Using site-specific extractor for zougla.gr")
        return GenericExtractor().extract(
            html_content,
            url=url,
            soup=soup,
            parser_engine=parser_engine,
            normalize_whitespace=normalize_whitespace,
            logger=logger,
        )


ALL_SITE_EXTRACTORS = [
    Site1voiceGrExtractor,
    AlphanewsLiveExtractor,
    AlphatvGrExtractor,
    AntennaGrExtractor,
    AtticatimesGrExtractor,
    DimokratiaGrExtractor,
    DocumentonewsGrExtractor,
    EfsynGrExtractor,
    EkirikasComExtractor,
    EleftherostyposGrExtractor,
    EloraGrExtractor,
    EnikosGrExtractor,
    ErtGrExtractor,
    ErtnewsGrExtractor,
    EspressonewsGrExtractor,
    EstianewsGrExtractor,
    EthnosGrExtractor,
    IapogevmatiniGrExtractor,
    IefimeridaGrExtractor,
    InGrExtractor,
    InkefaloniaGrExtractor,
    IpaperGrExtractor,
    KathimeriniGrExtractor,
    KefaloniapressGrExtractor,
    KontranewsGrExtractor,
    KoutipandorasGrExtractor,
    LifoGrExtractor,
    MakeleioGrExtractor,
    MegatvComExtractor,
    NaftemporikiGrExtractor,
    News247GrExtractor,
    NewsbombGrExtractor,
    ProtothemaGrExtractor,
    RealGrExtractor,
    RizospastisGrExtractor,
    SkaiGrExtractor,
    StarGrExtractor,
    TaneaGrExtractor,
    TomanifestoGrExtractor,
    TovimaGrExtractor,
    TvopenGrExtractor,
    ZouglaGrExtractor,
]
