from dataclasses import dataclass
from typing import Optional


@dataclass
class CrawlerConfig:
    # Target and strategy settings
    respect_robots: bool = True
    no_duplicates: bool = True
    crawl_delay: int = 30
    resume: bool = False
    re_crawl_time: float = 3.0

    # Path settings
    logs_dir: str = "logs"
    db_dir: str = "db"

    # Execution tuning
    batch_size: int = 100
    workers: int = 1
    parser_engine: str = "auto"
    normalize_whitespace: bool = True

    # Plagiarism check configuration
    plagiarism_db: str = "db/plagiarism_index.db"
    plagiarism_threshold: float = 0.8

    # Network settings
    proxy: Optional[str] = None
    keep_alive: Optional[bool] = None
    user_agent: str = "Echidna/1.0 (+https://github.com/svagionitis/echidna)"
    processor: str = "news"

    # JavaScript rendering settings
    js_rendering: bool = False
    js_driver: str = "auto"  # 'playwright', 'selenium', 'puppeteer', 'auto'
    auto_detect_js: bool = True

    @classmethod
    def from_args(cls, args) -> "CrawlerConfig":
        """Build config from parsed CLI argparse.Namespace."""
        return cls(
            respect_robots=args.respect_robots,
            no_duplicates=args.no_duplicates,
            crawl_delay=args.crawl_delay,
            resume=args.resume,
            re_crawl_time=args.re_crawl_time,
            logs_dir=args.logs_dir,
            db_dir=args.db_dir,
            batch_size=args.batch_size,
            workers=args.workers,
            parser_engine=args.parser,
            normalize_whitespace=args.normalize_whitespace,
            plagiarism_db=args.plagiarism_db,
            plagiarism_threshold=args.plagiarism_threshold,
            proxy=args.proxy,
            processor=args.processor,
            keep_alive=args.keep_alive,
            js_rendering=getattr(args, "js_rendering", False),
            js_driver=getattr(args, "js_driver", "auto"),
            auto_detect_js=getattr(args, "auto_detect_js", True),
        )

    def merge_with_dict(self, site_dict: dict) -> "CrawlerConfig":
        """
        Merge a site configuration dictionary (loaded from JSON) into a new
        config instance, using this config's values as fallbacks.
        """
        import copy

        merged = copy.deepcopy(self)
        for field_name in self.__dataclass_fields__:
            # Map JSON config key naming discrepancies if any (e.g. 'parser' vs 'parser_engine')
            key = field_name
            if field_name == "parser_engine" and "parser" in site_dict:
                key = "parser"

            if key in site_dict:
                setattr(merged, field_name, site_dict[key])
        return merged
