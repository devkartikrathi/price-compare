import os
import asyncio
import json
import re
import logging
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from dotenv import load_dotenv
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode, LLMConfig
from crawl4ai.extraction_strategy import JsonCssExtractionStrategy, LLMExtractionStrategy
from crewai import Agent, Task, Crew, Process
from crewai.tools import BaseTool
from crewai import LLM as CrewAILLM
import traceback
from firecrawl import FirecrawlApp

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Pydantic Models
class ProductOffers(BaseModel):
    """Schema for extracting product offers and discounts"""
    credit_card_offers: List[str] = Field(default_factory=list, description="List of credit card specific offers")
    bank_offers: List[str] = Field(default_factory=list, description="Bank specific discount offers")
    cashback_offers: List[str] = Field(default_factory=list, description="Cashback offers available")
    exchange_offers: List[str] = Field(default_factory=list, description="Exchange/trade-in offers")
    coupon_offers: List[str] = Field(default_factory=list, description="Coupon codes and discounts")
    emi_offers: List[str] = Field(default_factory=list, description="EMI and financing options")
    special_discounts: List[str] = Field(default_factory=list, description="Special discounts and promotions")

class ProductDetails(BaseModel):
    """Schema for extracting detailed product information"""
    title: str = Field(description="Product title/name")
    price: str = Field(description="Current price of the product")
    original_price: Optional[str] = Field(description="Original/MRP price if different from current price")
    rating: Optional[str] = Field(description="Product rating")
    seller: Optional[str] = Field(description="Seller/vendor name")
    availability: Optional[str] = Field(description="Stock availability status")
    delivery_info: Optional[str] = Field(description="Delivery information")
    key_features: List[str] = Field(default_factory=list, description="Key product features")
    specifications: Dict[str, str] = Field(default_factory=dict, description="Product specifications")
    offers: ProductOffers = Field(default_factory=ProductOffers, description="All available offers")

class BasicDetails(BaseModel):
    description_summary: Optional[str] = None
    key_features: List[str] = Field(default_factory=list)
    variant_info: Optional[str] = None
    seller_name: Optional[str] = None
    credit_card_offers: List[str] = Field(default_factory=list)

class Product(BaseModel):
    title: str
    price: str
    rating: Optional[str] = None
    seller: Optional[str] = None
    url: str
    platform: str
    basic_details: Optional[str] = None
    original_price: Optional[float] = None
    effective_price: Optional[float] = None
    discount_applied: Optional[str] = None
    offers_text: Optional[str] = None
    detailed_offers: Optional[ProductOffers] = None

class ProductOutput(BaseModel):
    title: str
    platform: str
    price: str
    original_price: float
    effective_price: float
    discount_applied: str
    url: str
    rating: Optional[str] = None
    seller: Optional[str] = None

# CSS Extraction Schemas for Listings (keeping original for Crawl4AI)
amazon_css_listing_schema = {
    "name": "AmazonProductListing",
    "baseSelector": 'div[data-component-type="s-search-result"]',
    "fields": [
        {"name": "title", "selector": "h2 a span.a-text-normal, span.a-size-medium.a-color-base.a-text-normal, span.a-size-base-plus.a-color-base.a-text-normal", "type": "text", "optional": True},
        {"name": "price", "selector": "span.a-price > span.a-offscreen, span.a-price-whole", "type": "text", "optional": True},
        {"name": "rating", "selector": "span.a-icon-alt", "type": "text", "optional": True},
        {"name": "url", "selector": 'h2 a.a-link-normal[href*="/dp/"], h2 a.s-link-style[href*="/dp/"], a.a-link-normal.s-underline-text[href*="/dp/"]', "type": "attribute", "attribute": "href", "optional": True},
        {"name": "asin_direct", "selector": "", "type": "attribute", "attribute": "data-asin", "optional": True},
    ]
}

flipkart_css_listing_schema = {
    "name": "FlipkartProductListing",
    "baseSelector": 'div[data-id], div._13oc-S, div.cPHDOP, div._1AtVbE, div.DOjaWF, div._4ddWXP',
    "fields": [
        {"name": "title", "selector": "._4rR01T, .s1Q9rs, .IRpwTa, .KzDlHZ, .wjcEIp, .VU-ZEz, .WKTcLC, ._2WkVRV, a.geBtmU, div._2WkVRV", "type": "text", "optional": True},
        {"name": "price", "selector": "._30jeq3, ._1_WHN1, .Nx9bqj, ._4b7s3u, div._30jeq3._1_WHN1", "type": "text", "optional": True},
        {"name": "rating", "selector": "._3LWZlK, ._1lRcqv, div._3LWZlK", "type": "text", "optional": True},
        {"name": "url", "selector": 'a[href*="/p/"], a[href*="/product/"], a._1fQZEK, a.s1Q9rs, a.IRpwTa, a._2UzuFa, a.geBtmU', "type": "attribute", "attribute": "href", "optional": False}
    ]
}

# Browser Configuration
browser_config = BrowserConfig(
    headless=True,
    viewport_width=1920,
    viewport_height=1080,
    verbose=False,
    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    java_script_enabled=True,
)

class Crawl4AIScraperTool(BaseTool):
    name: str = "Crawl4AIScraper"
    description: str = "Scrapes web pages using Crawl4AI with CSS or LLM extraction."
    _crawler: AsyncWebCrawler
    _css_schema: Optional[Dict]
    _llm_strategy: Optional[LLMExtractionStrategy]

    def __init__(self, crawler: AsyncWebCrawler, css_schema: Optional[Dict] = None, llm_strategy: Optional[LLMExtractionStrategy] = None, **kwargs):
        super().__init__(**kwargs)
        self._crawler = crawler
        self._css_schema = css_schema
        self._llm_strategy = llm_strategy

    async def _arun(self, url: str, strategy_type: str = "css") -> str:
        if not self._crawler:
            logger.error("Crawler not initialized in Crawl4AIScraperTool.")
            return json.dumps({"error": "Crawler not initialized", "url": url})

        if not isinstance(url, str) or not url.startswith(('http://', 'https://')):
            logger.error(f"Invalid URL provided to Crawl4AIScraperTool: {url}")
            return json.dumps({"error": "Invalid URL format", "url": url})

        logger.info(f"Scraping {url} with strategy: {strategy_type}")
        try:
            if strategy_type == "css":
                if not self._css_schema:
                    logger.error("CSS schema is required for css strategy but not provided.")
                    raise ValueError("CSS schema is required for css strategy")
                crawl_config = CrawlerRunConfig(
                    extraction_strategy=JsonCssExtractionStrategy(self._css_schema, verbose=False),
                    cache_mode=CacheMode.BYPASS, wait_for="body", page_timeout=30000
                )
            elif strategy_type == "llm":
                if not self._llm_strategy:
                    logger.error("LLM strategy is required for llm strategy but not provided.")
                    raise ValueError("LLM strategy is required for llm strategy")
                crawl_config = CrawlerRunConfig(
                    extraction_strategy=self._llm_strategy,
                    cache_mode=CacheMode.BYPASS, session_id="detail_page_session",
                    wait_for="body", page_timeout=45000
                )
            else:
                raise ValueError(f"Invalid strategy_type: {strategy_type}")

            result = await self._crawler.arun(url=url, config=crawl_config)
            if result.success:
                logger.debug(f"Successfully scraped {url}. Extracted content type: {type(result.extracted_content)}")
                if isinstance(result.extracted_content, (dict, list)):
                    return json.dumps(result.extracted_content)
                return str(result.extracted_content)
            else:
                logger.error(f"Scraping failed for {url}: {result.error_message} (Status: {result.status_code})")
                return json.dumps({"error": result.error_message, "url": url, "status_code": result.status_code})
        except Exception as e:
            logger.error(f"Error in Crawl4AIScraperTool for {url} (strategy: {strategy_type}): {str(e)}")
            logger.error(traceback.format_exc())
            return json.dumps({"error": str(e), "url": url})

    def _run(self, url: str, strategy_type: str = "css") -> str:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                future = asyncio.ensure_future(self._arun(url, strategy_type))
                result = loop.run_until_complete(future)
            else:
                result = asyncio.run(self._arun(url, strategy_type))
            return result
        except Exception as e:
            logger.error(f"Error in Crawl4AIScraperTool sync _run for {url}: {str(e)}")
            return json.dumps({"error": str(e), "url": url})

# Helper Functions
def parse_price(price_str: Any) -> Optional[float]:
    if not price_str:
        return None
    try:
        clean_price = re.sub(r'[₹,]', '', str(price_str))
        price_match = re.search(r'(\d+\.?\d*)', clean_price)
        if price_match:
            return float(price_match.group(1))
        return None
    except (ValueError, AttributeError, TypeError) as e:
        logger.warning(f"Could not parse price: '{price_str}'. Error: {e}")
        return None

def safe_json_parse(json_str: str) -> Any:
    if not isinstance(json_str, str):
        logger.warning(f"safe_json_parse expected a string, got {type(json_str)}. Returning error dict.")
        return {"error": f"Invalid input type to safe_json_parse: {type(json_str)}"}
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        logger.warning(f"Could not parse JSON: {e}. Returning error dict.")
        return {"error": f"JSONDecodeError: {str(e)}"}

async def scrape_products_enhanced(product_query: str = "iPhone 16", user_credit_cards: List[str] = None, max_products_per_platform: int = 5, max_detail_pages: int = 10):
    """Enhanced scraping function with Firecrawl integration"""
    if user_credit_cards is None:
        user_credit_cards = ["HDFC Bank", "Axis Bank Credit Card", "SBI Card", "ICICI Credit Card"]

    load_dotenv()

    platforms = {
        "amazon": {
            "search_url": f"https://www.amazon.in/s?k={product_query.replace(' ', '+')}",
            "base_url": "https://www.amazon.in",
            "schema": amazon_css_listing_schema
        },
        "flipkart": {
            "search_url": f"https://www.flipkart.com/search?q={product_query.replace(' ', '%20')}",
            "base_url": "https://www.flipkart.com",
            "schema": flipkart_css_listing_schema
        },
    }

    initial_product_listings = []
    async with AsyncWebCrawler(config=browser_config) as crawler:
        for platform_name, info in platforms.items():
            search_url, base_url, schema = info['search_url'], info['base_url'], info['schema']
            css_scraper_tool = Crawl4AIScraperTool(crawler=crawler, css_schema=schema)
            logger.info(f"Fetching listings from {platform_name}: {search_url}")
            
            try:
                raw_listing_data_str = await css_scraper_tool._arun(url=search_url, strategy_type="css")
                listings_data_parsed = safe_json_parse(raw_listing_data_str)
                
                if isinstance(listings_data_parsed, dict) and "error" in listings_data_parsed:
                    logger.error(f"Failed to get listings from {platform_name}: {listings_data_parsed['error']}")
                    continue
                
                if not isinstance(listings_data_parsed, list):
                    logger.error(f"Expected list from {platform_name} listings, got {type(listings_data_parsed)}")
                    continue
                
                logger.info(f"Found {len(listings_data_parsed)} raw items from {platform_name}.")
                
                count = 0
                for item_raw in listings_data_parsed:
                    if count >= max_products_per_platform:
                        break
                    if not isinstance(item_raw, dict):
                        continue
                    
                    product_title = item_raw.get('title', "").strip()
                    full_url = None
                    
                    if platform_name == "amazon":
                        scraped_url_path, direct_asin = item_raw.get('url'), item_raw.get('asin_direct')
                        final_asin = None
                        
                        if scraped_url_path:
                            relative_url = str(scraped_url_path).strip()
                            full_url = (base_url + relative_url) if not relative_url.startswith(('http', '/')) else (base_url + relative_url if relative_url.startswith('/') else relative_url)
                            asin_match = re.search(r'/dp/([A-Z0-9]{10})', full_url)
                            if asin_match:
                                final_asin = asin_match.group(1)
                        
                        if direct_asin and (not final_asin or final_asin != direct_asin):
                            final_asin = str(direct_asin).strip() if not final_asin else final_asin
                        
                        if final_asin:
                            full_url = f"{base_url}/dp/{final_asin.strip()}"
                        
                        if not product_title:
                            product_title = f"Amazon Product ASIN: {final_asin}"
                    else:
                        scraped_url = item_raw.get('url')
                        if not product_title and not scraped_url:
                            continue
                        
                        if not product_title:
                            product_title = f"{platform_name.capitalize()} Product (Title unknown)"
                        
                        if scraped_url:
                            relative_url = str(scraped_url).strip()
                            full_url = (base_url + relative_url) if not relative_url.startswith(('http', '/')) else (base_url + relative_url if relative_url.startswith('/') else relative_url)
                    
                    if full_url and product_title:
                        initial_product_listings.append({
                            'title': product_title,
                            'price_str': item_raw.get('price', ''),
                            'rating_str': item_raw.get('rating'),
                            'url': full_url,
                            'platform': platform_name.capitalize()
                        })
                        count += 1
                        logger.info(f"Added: {product_title[:60]}... from {platform_name}")
            
            except Exception as e:
                logger.error(f"Error scraping {platform_name}: {e}")
                continue

    if not initial_product_listings:
        logger.warning("No initial product listings found")
        return []

    for listing_item in initial_product_listings[:min(len(initial_product_listings), max_detail_pages)]:
        print(listing_item['url'], listing_item['platform'])

if __name__ == "__main__":
    asyncio.run(scrape_products_enhanced())

# 2025-06-07 21:13:39,618 - __main__ - INFO - Fetching listings from amazon: https://www.amazon.in/s?k=iPhone+16
# 2025-06-07 21:13:39,619 - __main__ - INFO - Scraping https://www.amazon.in/s?k=iPhone+16 with strategy: css
# [FETCH]... ↓ https://www.amazon.in/s?k=iPhone+16                                                                  | ✓ | ⏱: 2.05s 
# [SCRAPE].. ◆ https://www.amazon.in/s?k=iPhone+16                                                                  | ✓ | ⏱: 0.57s 
# [EXTRACT]. ■ Completed for https://www.amazon.in/s?k=iPhone+16... | Time: 0.3683638999937102s 
# [COMPLETE] ● https://www.amazon.in/s?k=iPhone+16                                                                  | ✓ | ⏱: 3.00s 
# 2025-06-07 21:13:42,645 - __main__ - INFO - Found 20 raw items from amazon.
# 2025-06-07 21:13:42,645 - __main__ - INFO - Added: Amazon Product ASIN: B0DGJH8RYG... from amazon
# 2025-06-07 21:13:42,645 - __main__ - INFO - Added: Amazon Product ASIN: B0DGHYDZR9... from amazon
# 2025-06-07 21:13:42,645 - __main__ - INFO - Added: Amazon Product ASIN: B0DGHZWBYB... from amazon
# 2025-06-07 21:13:42,645 - __main__ - INFO - Added: Amazon Product ASIN: B0DGJHBX5Y... from amazon
# 2025-06-07 21:13:42,646 - __main__ - INFO - Added: Amazon Product ASIN: B0DGJC8DG8... from amazon
# 2025-06-07 21:13:42,646 - __main__ - INFO - Fetching listings from flipkart: https://www.flipkart.com/search?q=iPhone%2016
# 2025-06-07 21:13:42,647 - __main__ - INFO - Scraping https://www.flipkart.com/search?q=iPhone%2016 with strategy: css
# [FETCH]... ↓ https://www.flipkart.com/search?q=iPhone 16                                                          | ✓ | ⏱: 1.47s 
# [SCRAPE].. ◆ https://www.flipkart.com/search?q=iPhone 16                                                          | ✓ | ⏱: 0.20s 
# [EXTRACT]. ■ Completed for https://www.flipkart.com/search?q=iPhone%2016... | Time: 0.805523999966681s 
# [COMPLETE] ● https://www.flipkart.com/search?q=iPhone 16                                                          | ✓ | ⏱: 2.48s 
# 2025-06-07 21:13:45,141 - __main__ - INFO - Found 51 raw items from flipkart.
# 2025-06-07 21:13:45,141 - __main__ - INFO - Added: Apple iPhone 16 (Black, 128 GB)... from flipkart
# 2025-06-07 21:13:45,142 - __main__ - INFO - Added: Apple iPhone 16 (Black, 128 GB)... from flipkart
# 2025-06-07 21:13:45,142 - __main__ - INFO - Added: Apple iPhone 16 (Black, 128 GB)... from flipkart
# 2025-06-07 21:13:45,142 - __main__ - INFO - Added: Apple iPhone 16 (Black, 128 GB)... from flipkart
# 2025-06-07 21:13:45,142 - __main__ - INFO - Added: Apple iPhone 16 (Black, 256 GB)... from flipkart
# https://www.amazon.in/dp/B0DGJH8RYG Amazon
# https://www.amazon.in/dp/B0DGHYDZR9 Amazon
# https://www.amazon.in/dp/B0DGHZWBYB Amazon
# https://www.amazon.in/dp/B0DGJHBX5Y Amazon
# https://www.amazon.in/dp/B0DGJC8DG8 Amazon
# https://www.flipkart.com/apple-iphone-16-black-128-gb/p/itmb07d67f995271?pid=MOBH4DQFG8NKFRDY&lid=LSTMOBH4DQFG8NKFRDYNBDOZI&marketplace=FLIPKART&q=iPhone+16&store=tyy%2F4io&spotlightTagId=default_BestsellerId_tyy%2F4io&srno=s_1_1&otracker=search&fm=organic&iid=74a3ea84-8bc2-48dd-a5ce-7acf4a6b9fbb.MOBH4DQFG8NKFRDY.SEARCH&ppt=sp&ppn=sp&ssid=v4q0hv2yz40000001749311023735&qH=8e0ee2dac8c1afb1 Flipkart
# https://www.flipkart.com/apple-iphone-16-black-128-gb/p/itmb07d67f995271?pid=MOBH4DQFG8NKFRDY&lid=LSTMOBH4DQFG8NKFRDYNBDOZI&marketplace=FLIPKART&q=iPhone+16&store=tyy%2F4io&spotlightTagId=default_BestsellerId_tyy%2F4io&srno=s_1_1&otracker=search&fm=organic&iid=74a3ea84-8bc2-48dd-a5ce-7acf4a6b9fbb.MOBH4DQFG8NKFRDY.SEARCH&ppt=sp&ppn=sp&ssid=v4q0hv2yz40000001749311023735&qH=8e0ee2dac8c1afb1 Flipkart
# https://www.flipkart.com/apple-iphone-16-black-128-gb/p/itmb07d67f995271?pid=MOBH4DQFG8NKFRDY&lid=LSTMOBH4DQFG8NKFRDYNBDOZI&marketplace=FLIPKART&q=iPhone+16&store=tyy%2F4io&spotlightTagId=default_BestsellerId_tyy%2F4io&srno=s_1_1&otracker=search&fm=organic&iid=74a3ea84-8bc2-48dd-a5ce-7acf4a6b9fbb.MOBH4DQFG8NKFRDY.SEARCH&ppt=sp&ppn=sp&ssid=v4q0hv2yz40000001749311023735&qH=8e0ee2dac8c1afb1 Flipkart
# https://www.flipkart.com/apple-iphone-16-black-128-gb/p/itmb07d67f995271?pid=MOBH4DQFG8NKFRDY&lid=LSTMOBH4DQFG8NKFRDYNBDOZI&marketplace=FLIPKART&q=iPhone+16&store=tyy%2F4io&spotlightTagId=default_BestsellerId_tyy%2F4io&srno=s_1_1&otracker=search&fm=organic&iid=74a3ea84-8bc2-48dd-a5ce-7acf4a6b9fbb.MOBH4DQFG8NKFRDY.SEARCH&ppt=sp&ppn=sp&ssid=v4q0hv2yz40000001749311023735&qH=8e0ee2dac8c1afb1 Flipkart
# https://www.flipkart.com/apple-iphone-16-black-256-gb/p/itm86da1977dcdf1?pid=MOBH4DQFZCJJXUFG&lid=LSTMOBH4DQFZCJJXUFGO5DY3W&marketplace=FLIPKART&q=iPhone+16&store=tyy%2F4io&srno=s_1_2&otracker=search&fm=organic&iid=74a3ea84-8bc2-48dd-a5ce-7acf4a6b9fbb.MOBH4DQFZCJJXUFG.SEARCH&ppt=None&ppn=None&ssid=v4q0hv2yz40000001749311023735&qH=8e0ee2dac8c1afb1 Flipkart