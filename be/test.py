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
    discount: Optional[str] = Field(description="Discount percentage or amount, if available", default="")

class GenericProduct(BaseModel):
    product_title: str = Field(description="The title of the product or menu item")
    price: str = Field(description="The current price, including currency")
    original_price: str = Field(description="The original price before discount, if available", default="")
    discount: str = Field(description="The discount percentage or amount, if available", default="")
    offers: list[str] = Field(description="List of current offers", default_factory=list)
    brand: str = Field(description="The brand or restaurant name", default="")
    rating: str = Field(description="The rating, if available", default="")
    reviews_count: str = Field(description="Number of reviews/ratings", default="")
    availability: str = Field(description="Availability status", default="")

blinkit_css_listing_schema = {
    "name": "BlinkitProductListing",
    "baseSelector": 'div.product-card',  # Verify with browser inspection
    "fields": [
        {"name": "title", "selector": ".product-name", "type": "text", "optional": True},
        {"name": "price", "selector": ".product-action .price", "type": "text", "optional": True},
        {"name": "url", "selector": "a", "type": "attribute", "attribute": "href", "optional": True},
        {"name": "discount", "selector": ".product-action .discount", "type": "text", "optional": True},
    ]
}

zepto_css_listing_schema = {
    "name": "ZeptoProductListing",
    "baseSelector": 'div.item',  # Verify with browser inspection
    "fields": [
        {"name": "title", "selector": ".item-title", "type": "text", "optional": True},
        {"name": "price", "selector": ".item-price", "type": "text", "optional": True},
        {"name": "url", "selector": "a", "type": "attribute", "attribute": "href", "optional": True},
        {"name": "discount", "selector": ".item-discount", "type": "text", "optional": True},
    ]
}

talabat_css_listing_schema = {
    "name": "TalabatMenuListing",
    "baseSelector": 'div.menu-item',  # Verify with browser inspection
    "fields": [
        {"name": "title", "selector": ".item-name", "type": "text", "optional": True},
        {"name": "price", "selector": ".item-price", "type": "text", "optional": True},
        {"name": "url", "selector": "a", "type": "attribute", "attribute": "href", "optional": True},
        {"name": "discount", "selector": ".item-offer", "type": "text", "optional": True},
    ]
}

noon_css_listing_schema = {
    "name": "NoonProductListing",
    "baseSelector": 'div.product-card',  # Verify with browser inspection
    "fields": [
        {"name": "title", "selector": ".product-title", "type": "text", "optional": True},
        {"name": "price", "selector": ".price-now", "type": "text", "optional": True},
        {"name": "url", "selector": "a", "type": "attribute", "attribute": "href", "optional": True},
        {"name": "discount", "selector": ".price-discount", "type": "text", "optional": True},
    ]
}

deliveroo_css_listing_schema = {
    "name": "DeliverooMenuListing",
    "baseSelector": 'div.menu-item',  # Verify with browser inspection
    "fields": [
        {"name": "title", "selector": ".item-title", "type": "text", "optional": True},
        {"name": "price", "selector": ".item-price", "type": "text", "optional": True},
        {"name": "url", "selector": "a", "type": "attribute", "attribute": "href", "optional": True},
        {"name": "discount", "selector": ".item-offer", "type": "text", "optional": True},
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
    if "blinkit." in url_lower:
        return "blinkit"
    elif "zeptonow." in url_lower:
        return "zepto"
    elif "talabat." in url_lower:
        return "talabat"
    elif "noon." in url_lower:
        return "noon"
    elif "deliveroo." in url_lower:
        return "deliveroo"
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
    data = app.extract([url], prompt='Extract the offer details and discount from the page', schema=ExtractSchema.model_json_schema()).data
    return data

async def scrape_product_listings(product_query: str, max_products_per_platform: int = 5) -> List[Dict]:
    platforms = {
        "blinkit": {
            "search_url": f"https://www.blinkit.com/s/?q={product_query.replace(' ', '+')}&pincode=110001",  # Delhi pincode
            "base_url": "https://www.blinkit.com",
            "schema": blinkit_css_listing_schema
        },
        "zepto": {
            "search_url": f"https://www.zeptonow.com/search?q={product_query.replace(' ', '+')}&pincode=400001",  # Mumbai pincode
            "base_url": "https://www.zeptonow.com",
            "schema": zepto_css_listing_schema
        },
        "talabat": {
            "search_url": f"https://www.talabat.com/uae/search?query={product_query.replace(' ', '+')}&city=Dubai",
            "base_url": "https://www.talabat.com",
            "schema": talabat_css_listing_schema
        },
        "noon": {
            "search_url": f"https://www.noon.com/uae-en/search/?q={product_query.replace(' ', '+')}",
            "base_url": "https://www.noon.com",
            "schema": noon_css_listing_schema
        },
        "deliveroo": {
            "search_url": f"https://deliveroo.co.uk/search?q={product_query.replace(' ', '+')}&postcode=SW1A1AA",  # London postcode
            "base_url": "https://deliveroo.co.uk",
            "schema": deliveroo_css_listing_schema
        },
    }

    listings = []
    processed_urls = set()
    
    async with AsyncWebCrawler(config=browser_config) as crawler:
        for platform_name, info in platforms.items():
            print(f"🔍 Scraping {platform_name.capitalize()}...")
            js_code = f"""
            // Set location cookies for {platform_name}
            document.cookie = "city={platform_name.capitalize()}; path=/";
            await new Promise(resolve => setTimeout(resolve, 5000));
            window.scrollTo(0, 1000);
            await new Promise(resolve => setTimeout(resolve, 2000));
            """

            crawl_config = CrawlerRunConfig(
                extraction_strategy=JsonCssExtractionStrategy(info['schema'], verbose=True),
                cache_mode=CacheMode.BYPASS,
                wait_for="body",
                page_timeout=60000,  # Increased to 60 seconds
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
                    if not url.startswith('http'):
                        url = info['base_url'] + url
                    
                    if not url or url in processed_urls:
                        continue
                    
                    processed_urls.add(url)
                    
                    listing_item = {
                        'title': title,
                        'price_str': item.get('price', ''),
                        'discount_str': item.get('discount', ''),
                        'url': url,
                        'platform': platform_name.capitalize()
                    }
                    
                    listings.append(listing_item)
                    count += 1
            else:
                print(f"❌ Failed to scrape {platform_name}: {result.error_message if result.error_message else 'No data extracted'}")
    return listings

async def run_product_pipeline(product_query: str = "milk", max_products_per_platform: int = 5):  
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
    result = asyncio.run(run_product_pipeline("milk", 2))
    print(json.dumps(result, indent=2))