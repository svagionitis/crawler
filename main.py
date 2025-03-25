import argparse
from Crawler import Crawler

def main():
    parser = argparse.ArgumentParser(description="Crawl a news site and save data to SQLite.")
    parser.add_argument(
        "--url",
        required=True,
        help="The URL of the news site to crawl.")
    parser.add_argument(
        "--respect-robots",
        action="store_true",
        help="Respect robots.txt when crawling.",
    )
    parser.add_argument(
        "--no-duplicates",
        action="store_true",
        help="Skip saving duplicate content.",
    )
    parser.add_argument(
        "--crawl-delay",
        type=int,
        default=30,
        help="Crawl delay in seconds (default: 30). If robots.txt specifies a delay, it will override this.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume crawling from an existing database.",
    )
    parser.add_argument(
        "--re-crawl-time",
        type=int,
        default=3,
        help="Time in hours after which a link should be re-crawled (default: 3).",
    )
    parser.add_argument(
        "--logs-dir",
        type=str,
        default="logs",
        help="Directory to save log files (default: logs).",
    )
    parser.add_argument(
        "--db-dir",
        type=str,
        default="db",
        help="Directory to save database files (default: db).",
    )
    args = parser.parse_args()

    # Initialize and start the crawler
    crawler = Crawler(args.url, args.respect_robots, args.no_duplicates, args.crawl_delay,
                      args.resume, args.re_crawl_time, args.logs_dir, args.db_dir)
    crawler.start_crawling()

if __name__ == "__main__":
    main()
