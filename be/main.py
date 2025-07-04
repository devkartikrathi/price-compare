import os
import asyncio
import json
import re
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from dotenv import load_dotenv
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
from crawl4ai.extraction_strategy import JsonCssExtractionStrategy
from firecrawl import FirecrawlApp

load_dotenv()

class ExtractSchema(BaseModel):
    offer_details: str

class AmazonProduct(BaseModel):
    product_title: str = Field(description="The title of the product")
    price: str = Field(description="The current price of the product, including currency")
    offers: list[str] = Field(description="List of current offers on the product, including bank credit card offers")
    brand: str = Field(description="The brand of the product")
    asin: str = Field(description="The Amazon Standard Identification Number")

class FlipkartProduct(BaseModel):
    product_title: str = Field(description="The title of the product")
    price: str = Field(description="The current price of the product, including currency")
    original_price: str = Field(description="The original price before discount, if available", default="")
    discount: str = Field(description="The discount percentage or amount, if available", default="")
    offers: list[str] = Field(description="List of current offers on the product, including bank offers and exchange offers")
    brand: str = Field(description="The brand of the product")
    rating: str = Field(description="The product rating out of 5", default="")
    reviews_count: str = Field(description="Number of reviews/ratings", default="")

class GenericProduct(BaseModel):
    product_title: str = Field(description="The title of the product")
    price: str = Field(description="The current price of the product, including currency")
    original_price: str = Field(description="The original price before discount, if available", default="")
    discount: str = Field(description="The discount percentage or amount, if available", default="")
    offers: list[str] = Field(description="List of current offers on the product", default_factory=list)
    brand: str = Field(description="The brand of the product", default="")
    rating: str = Field(description="The product rating", default="")
    reviews_count: str = Field(description="Number of reviews/ratings", default="")
    availability: str = Field(description="Product availability status", default="")

amazon_css_listing_schema = {
    "name": "AmazonProductListing",
    "baseSelector": 'div[data-component-type="s-search-result"], div[data-asin]',
    "fields": [
        {"name": "title", "selector": "h2 a span, .a-size-medium.a-color-base, .a-size-base-plus, h2 span", "type": "text", "optional": True},
        {"name": "price", "selector": ".a-price .a-offscreen, .a-price-whole", "type": "text", "optional": True},
        {"name": "rating", "selector": ".a-icon-alt", "type": "text", "optional": True},
        {"name": "url", "selector": 'h2 a[href*="/dp/"], a[href*="/dp/"]', "type": "attribute", "attribute": "href", "optional": True},
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

bigbasket_css_listing_schema = {
    "name": "BigBasketProductListing",
    "baseSelector": '.SKUDeck___StyledDiv-sc-1e5d9gk-0, .product, div[qa="product"]',
    "fields": [
        {"name": "title", "selector": '.truncate___StyledP-sc-11x0qrx-0, .product-name, h3', "type": "text", "optional": True},
        {"name": "price", "selector": '.Pricing___StyledDiv-sc-pldi2d-0, .discounted-price, .price', "type": "text", "optional": True},
        {"name": "original_price", "selector": '.Label___StyledLabel-sc-15v1nk5-0, .list-price', "type": "text", "optional": True},
        {"name": "url", "selector": 'a', "type": "attribute", "attribute": "href", "optional": True}
    ]
}

browser_config = BrowserConfig(
    headless=True,
    viewport_width=1920,
    viewport_height=1080,
    verbose=True,
    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    java_script_enabled=True,
)

def detect_platform(url: str) -> str:
    url_lower = url.lower()
    if "amazon." in url_lower:
        return "amazon"
    elif "flipkart." in url_lower:
        return "flipkart"
    elif "bigbasket." in url_lower:
        return "bigbasket"
    else:
        return "unknown"

def clean_data_for_json(data):
    if isinstance(data, dict):
        cleaned = {}
        for key, value in data.items():
            try:
                json.dumps(value)
                cleaned[key] = clean_data_for_json(value)
            except (TypeError, ValueError):
                print(f"⚠️  Skipping non-serializable field: {key}")
                continue
        return cleaned
    elif isinstance(data, list):
        cleaned = []
        for item in data:
            try:
                json.dumps(item)
                cleaned.append(clean_data_for_json(item))
            except (TypeError, ValueError):
                continue
        return cleaned
    else:
        return data

def scrape_product_details(url: str) -> Dict:
    app = FirecrawlApp(api_key=os.getenv("FIRECRAWL_API_KEY"))
    data = app.extract([url
    ], prompt='Extract the offer details from the page', schema=ExtractSchema.model_json_schema()).data
    return data

async def scrape_product_listings(product_query: str, max_products_per_platform: int = 5) -> List[Dict]:
    platforms = {
        "amazon": {
            "search_url": f"https://www.amazon.in/s?k={product_query.replace(' ', '+')}&ref=nb_sb_noss",
            "base_url": "https://www.amazon.in",
            "schema": amazon_css_listing_schema
        },
        "flipkart": {
            "search_url": f"https://www.flipkart.com/search?q={product_query.replace(' ', '%20')}",
            "base_url": "https://www.flipkart.com",
            "schema": flipkart_css_listing_schema
        },
        "bigbasket": {
            "search_url": f"https://www.bigbasket.com/ps/?q={product_query.replace(' ', '%20')}",
            "base_url": "https://www.bigbasket.com",
            "schema": bigbasket_css_listing_schema
        }
    }

    listings = []
    processed_urls = set()
    
    async with AsyncWebCrawler(config=browser_config) as crawler:
        for platform_name, info in platforms.items():
            print(f"🔍 Scraping {platform_name.capitalize()}...")
            js_code = """
            await new Promise(resolve => setTimeout(resolve, 3000));
            window.scrollTo(0, 500);
            await new Promise(resolve => setTimeout(resolve, 1000));
            """

            if platform_name in ["blinkit", "zepto", "swiggy"]:
                js_code += """
                await new Promise(resolve => setTimeout(resolve, 2000));
                """

            crawl_config = CrawlerRunConfig(
                extraction_strategy=JsonCssExtractionStrategy(info['schema'], verbose=False),
                cache_mode=CacheMode.BYPASS,
                wait_for="body",
                page_timeout=40000, 
                js_code=js_code
            )
            
            result = await crawler.arun(url=info['search_url'], config=crawl_config)
            
            if result.success and result.extracted_content:
                raw_data = json.loads(result.extracted_content) if isinstance(result.extracted_content, str) else result.extracted_content

                count = 0
                for item in raw_data:
                    if count >= max_products_per_platform:
                        break

                    title = item.get('title', '').strip()
                    if not title:
                        continue

                    url = item.get('url', '')

                    if platform_name == "amazon":
                        if not url.startswith('http'):
                            url = info['base_url'] + url
                        asin_match = re.search(r'/dp/([A-Z0-9]{10})', url)
                        if asin_match:
                            url = f"{info['base_url']}/dp/{asin_match.group(1)}"
                        else:
                            asin = item.get('asin_direct', '')
                            if asin:
                                url = f"{info['base_url']}/dp/{asin}"
                            else:
                                continue
                    else:
                        if url and not url.startswith('http'):
                            url = info['base_url'] + url
                    
                    if not url or url in processed_urls:
                        continue
                    
                    processed_urls.add(url)
                    
                    listing_item = {
                        'title': title,
                        'price_str': item.get('price', ''),
                        'original_price_str': item.get('original_price', ''),
                        'rating_str': item.get('rating'),
                        'url': url,
                        'platform': platform_name.capitalize()
                    }
                    
                    listings.append(listing_item)
                    count += 1
    return listings

async def run_product_pipeline(product_query: str = "iPhone 16", max_products_per_platform: int = 5):  
    listings = await scrape_product_listings(product_query, max_products_per_platform)
    detailed_products = []
    for listing in listings:
        detail_result = scrape_product_details(listing['url'])
        cleaned_listing = clean_data_for_json(listing)
        
        combined_product = {
            "listing_info": cleaned_listing,
            "detailed_info": detail_result
        }
        detailed_products.append(combined_product)
        
    final_result = {
        "query": product_query,
        "total_listings_found": len(listings),
        "detailed_products_processed": len(detailed_products),
        "products": detailed_products
    }
    return clean_data_for_json(final_result)

if __name__ == "__main__":
    print(asyncio.run(run_product_pipeline("iPhone 15 128GB", 3)))