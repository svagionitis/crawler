from bs4 import BeautifulSoup
from utils import extract_links, compute_hash
from database import is_duplicate_content, update_queue_link, get_connection
from .base import BaseContentProcessor


class SupermarketContentProcessor(BaseContentProcessor):
    """Supermarket-specific content processor to extract product metadata (pricing, name, SKU)."""

    def __init__(self):
        self._db_initialized = set()

    def _init_market_table(self, database_name):
        if database_name in self._db_initialized:
            return
        conn = get_connection(database_name)
        with conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS supermarket_products (
                    link TEXT PRIMARY KEY,
                    product_name TEXT,
                    price REAL,
                    sku TEXT,
                    category TEXT,
                    FOREIGN KEY(link) REFERENCES crawled_data(link) ON DELETE CASCADE
                )
                """
            )
            conn.commit()
        self._db_initialized.add(database_name)

    def process_page(self, crawler, url: str, content: str, content_type: str) -> tuple:
        self._init_market_table(crawler.database_name)

        content_hash = compute_hash(content)
        if crawler.no_duplicates and is_duplicate_content(
            crawler.database_name, content_hash, logger=crawler.logger
        ):
            crawler.logger.info(f"Skipping duplicate content: {url}")
            return None, set(), None

        is_html = (content_type and "html" in content_type) or (
            content
            and any(
                tag in content[:1000].lower()
                for tag in ("<html", "<body", "<p", "<div")
            )
        )
        soup = BeautifulSoup(content, "html.parser") if is_html else None
        new_links = (
            extract_links(
                url, content, crawler.robots_parser, soup=soup, logger=crawler.logger
            )
            if soup
            else set()
        )

        # Extract product details
        product_name = None
        price = None
        sku = None
        category = None

        if soup:
            import json

            # 1. Try parsing JSON-LD product markup
            for script in soup.find_all("script", type="application/ld+json"):
                try:
                    data = json.loads(script.string)
                    # Support list of schemas
                    items = data if isinstance(data, list) else [data]
                    for item in items:
                        if item.get("@type") == "Product":
                            product_name = item.get("name")
                            sku = item.get("sku") or item.get("mpn")
                            offers = item.get("offers")
                            if offers:
                                if isinstance(offers, list):
                                    offers = offers[0]
                                price_val = offers.get("price")
                                if price_val is not None:
                                    try:
                                        price = float(price_val)
                                    except ValueError:
                                        pass
                            category = item.get("category")
                            break
                except Exception:
                    pass

            # 2. Fallback to OpenGraph / Meta tags
            if not product_name:
                title_tag = soup.find("meta", property="og:title") or soup.find(
                    "meta", attrs={"name": "title"}
                )
                product_name = (
                    title_tag["content"]
                    if title_tag
                    else (soup.title.string if soup.title else None)
                )
            if price is None:
                price_tag = soup.find(
                    "meta", property="product:price:amount"
                ) or soup.find("meta", property="og:price:amount")
                if price_tag:
                    try:
                        price = float(price_tag["content"])
                    except ValueError:
                        pass
            if not sku:
                sku_tag = soup.find(
                    "meta", property="product:retailer_item_id"
                ) or soup.find("meta", attrs={"name": "sku"})
                sku = sku_tag["content"] if sku_tag else None

        soup = None

        # Extract MIME type from content_type header (excluding charset properties)
        mime_type = content_type.split(";")[0].strip() if content_type else None

        # 1. Update Core Queue
        success = update_queue_link(
            crawler.database_name,
            url,
            content,
            content_hash,
            status="crawled",
            mime_type=mime_type,
            logger=crawler.logger,
        )
        if not success:
            return False, set(), None

        # 2. Update Supermarket Payload
        conn = get_connection(crawler.database_name)
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO supermarket_products (link, product_name, price, sku, category)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(link) DO UPDATE SET
                        product_name = excluded.product_name,
                        price = excluded.price,
                        sku = excluded.sku,
                        category = excluded.category
                    """,
                    (url, product_name, price, sku, category),
                )
                conn.commit()
        except Exception as e:
            crawler.logger.error(f"Failed to save supermarket payload: {e}")

        return content is not None, new_links, None
