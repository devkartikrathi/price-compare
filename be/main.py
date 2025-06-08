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

# Load environment variables
load_dotenv()

# Pydantic Models
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

# Updated CSS Extraction Schemas with better selectors
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

# Browser Configuration
browser_config = BrowserConfig(
    headless=True,
    viewport_width=1920,
    viewport_height=1080,
    verbose=True,  # Enable verbose logging
    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    java_script_enabled=True,
)

def detect_platform(url: str) -> str:
    """Detect whether the URL is from Amazon or Flipkart"""
    if "amazon." in url.lower():
        return "amazon"
    elif "flipkart." in url.lower():
        return "flipkart"
    else:
        return "unknown"

def scrape_product_details(url: str) -> Dict:
    """Scrape detailed product information from a product URL using Firecrawl"""
    try:
        print(f"🔍 Scraping details for: {url[:80]}...")
        
        api_key = os.getenv("FIRECRAWL_API_KEY")
        if not api_key:
            print("❌ FIRECRAWL_API_KEY not set")
            return {"error": "FIRECRAWL_API_KEY not set", "url": url}
        
        app = FirecrawlApp(api_key=api_key)
        platform = detect_platform(url)
        
        print(f"📱 Platform detected: {platform}")
        
        if platform == "amazon":
            result = app.scrape_url(
                url,
                formats=['json'],
                jsonOptions={'schema': AmazonProduct.model_json_schema()}
            )
        elif platform == "flipkart":
            result = app.scrape_url(
                url,
                formats=['json'],
                jsonOptions={'schema': FlipkartProduct.model_json_schema()}
            )
        else:
            print(f"❌ Unsupported platform: {platform}")
            return {"error": "Unsupported platform", "url": url}
        
        # Extract JSON data from result
        if hasattr(result, 'json') and result.json:
            print(f"✅ Successfully scraped {platform} product details")
            return {"platform": platform, "url": url, "data": result.json}
        elif isinstance(result, dict) and 'json' in result and result['json']:
            print(f"✅ Successfully scraped {platform} product details")
            return {"platform": platform, "url": url, "data": result['json']}
        else:
            print(f"❌ Failed to extract product data from {platform}")
            return {"error": "Failed to extract product data", "url": url}
    
    except Exception as e:
        print(f"❌ Exception while scraping {url}: {str(e)}")
        return {"error": str(e), "url": url}

async def scrape_product_listings(product_query: str, max_products_per_platform: int = 5) -> List[Dict]:
    """Scrape product listings from Amazon and Flipkart using Crawl4AI"""
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
    }

    listings = []
    processed_urls = set()  # Track processed URLs to avoid duplicates
    
    async with AsyncWebCrawler(config=browser_config) as crawler:
        for platform_name, info in platforms.items():
            try:
                print(f"\n🌐 Starting to scrape {platform_name.upper()}...")
                print(f"🔗 URL: {info['search_url']}")
                
                crawl_config = CrawlerRunConfig(
                    extraction_strategy=JsonCssExtractionStrategy(info['schema'], verbose=False),
                    cache_mode=CacheMode.BYPASS,
                    wait_for="body",
                    page_timeout=30000,
                    js_code="""
                    // Wait for content to load and scroll a bit
                    await new Promise(resolve => setTimeout(resolve, 3000));
                    window.scrollTo(0, 500);
                    await new Promise(resolve => setTimeout(resolve, 1000));
                    """
                )
                
                result = await crawler.arun(url=info['search_url'], config=crawl_config)
                
                if result.success and result.extracted_content:
                    print(f"✅ {platform_name} page loaded successfully")
                    
                    try:
                        raw_data = json.loads(result.extracted_content) if isinstance(result.extracted_content, str) else result.extracted_content
                        print(f"📊 Raw data extracted from {platform_name}: {len(raw_data)} items")
                        
                        # Debug: Print first item structure
                        if raw_data:
                            print(f"🔍 Sample item from {platform_name}: {raw_data[0]}")
                        
                        count = 0
                        for item in raw_data:
                            if count >= max_products_per_platform:
                                break
                            
                            title = item.get('title', '').strip()
                            if not title:
                                print(f"⚠️  Skipping item with no title: {item}")
                                continue
                            
                            # Process URL
                            url = item.get('url', '')
                            if platform_name == "amazon":
                                if not url.startswith('http'):
                                    url = info['base_url'] + url
                                asin_match = re.search(r'/dp/([A-Z0-9]{10})', url)
                                if asin_match:
                                    url = f"{info['base_url']}/dp/{asin_match.group(1)}"
                                else:
                                    # Try to get ASIN from the item
                                    asin = item.get('asin_direct', '')
                                    if asin:
                                        url = f"{info['base_url']}/dp/{asin}"
                                    else:
                                        print(f"⚠️  No valid Amazon URL/ASIN for: {title}")
                                        continue
                            else:  # flipkart
                                if not url.startswith('http'):
                                    url = info['base_url'] + url
                            
                            # Check for duplicates
                            if url in processed_urls:
                                print(f"⚠️  Skipping duplicate URL: {url}")
                                continue
                            
                            processed_urls.add(url)
                            
                            listing_item = {
                                'title': title,
                                'price_str': item.get('price', ''),
                                'rating_str': item.get('rating'),
                                'url': url,
                                'platform': platform_name.capitalize()
                            }
                            
                            listings.append(listing_item)
                            count += 1
                            print(f"✅ Added {platform_name} product #{count}: {title[:50]}...")
                    
                    except json.JSONDecodeError as e:
                        print(f"❌ JSON decode error for {platform_name}: {e}")
                        print(f"Raw content preview: {str(result.extracted_content)[:200]}")
                
                else:
                    print(f"❌ Failed to scrape {platform_name}")
                    if hasattr(result, 'error_message'):
                        print(f"Error message: {result.error_message}")
            
            except Exception as e:
                print(f"❌ Exception while scraping {platform_name}: {e}")
                import traceback
                traceback.print_exc()
                continue
    
    print(f"\n📈 SCRAPING SUMMARY:")
    amazon_count = len([l for l in listings if l['platform'] == 'Amazon'])
    flipkart_count = len([l for l in listings if l['platform'] == 'Flipkart'])
    print(f"   Amazon products found: {amazon_count}")
    print(f"   Flipkart products found: {flipkart_count}")
    print(f"   Total unique listings: {len(listings)}")
    
    return listings

async def run_product_pipeline(product_query: str = "iPhone 16", max_products_per_platform: int = 5, max_detail_pages: int = 10):
    """Main pipeline function that combines Crawl4AI listings with Firecrawl details"""

    print(f"🚀 Step 1: Scraping product listings for '{product_query}'...")
    listings = await scrape_product_listings(product_query, max_products_per_platform)
    
    if not listings:
        print("❌ No product listings found")
        return {"error": "No product listings found"}
    
    print(f"\n✅ Found {len(listings)} product listings total")
    
    # Step 2: Get detailed information for each product using Firecrawl
    print(f"\n🚀 Step 2: Scraping detailed information for up to {max_detail_pages} products...")
    
    detailed_products = []
    processed_count = 0
    
    for i, listing in enumerate(listings):
        if processed_count >= max_detail_pages:
            break
        
        print(f"\n📦 Processing product {processed_count + 1}/{min(len(listings), max_detail_pages)}")
        print(f"   Platform: {listing['platform']}")
        print(f"   Title: {listing['title'][:60]}...")
        
        # Get detailed product information
        detail_result = scrape_product_details(listing['url'])
        
        # Combine listing and detail information
        combined_product = {
            "listing_info": listing,
            "detailed_info": detail_result
        }
        
        detailed_products.append(combined_product)
        processed_count += 1
    
    # Step 3: Return final JSON with all product information
    final_result = {
        "query": product_query,
        "total_listings_found": len(listings),
        "detailed_products_processed": len(detailed_products),
        "products": detailed_products
    }
    
    return final_result

def save_results_to_file(results: Dict, filename: str = "product_results.json"):
    """Save results to a JSON file"""
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"💾 Results saved to {filename}")

async def main(product_query: str = "iPhone 16", max_products_per_platform: int = 2, max_detail_pages: int = 4):
    """Main execution function"""
    
    print("="*80)
    print("🛒 PRODUCT SCRAPING PIPELINE")
    print("="*80)
    print(f"🔍 Query: {product_query}")
    print(f"📊 Max products per platform: {max_products_per_platform}")
    print(f"🔍 Max detail pages: {max_detail_pages}")
    print("="*80)
    
    # Run the pipeline
    results = await run_product_pipeline(
        product_query=product_query,
        max_products_per_platform=max_products_per_platform,
        max_detail_pages=max_detail_pages
    )
    
    # Print results summary
    print("\n" + "="*80)
    print("📊 FINAL RESULTS SUMMARY")
    print("="*80)
    
    if "products" in results:
        amazon_products = [p for p in results["products"] if p["listing_info"]["platform"] == "Amazon"]
        flipkart_products = [p for p in results["products"] if p["listing_info"]["platform"] == "Flipkart"]
        
        print(f"🛒 Amazon products: {len(amazon_products)}")
        print(f"🛒 Flipkart products: {len(flipkart_products)}")
        print(f"🛒 Total products: {len(results['products'])}")
        
        # Show sample of each platform
        if amazon_products:
            print(f"\n📱 Sample Amazon product:")
            sample = amazon_products[0]
            print(f"   Title: {sample['listing_info']['title']}")
            print(f"   Price: {sample['listing_info']['price_str']}")
            if 'data' in sample['detailed_info']:
                print(f"   Detailed scraped: ✅")
            else:
                print(f"   Detailed scraped: ❌ ({sample['detailed_info'].get('error', 'Unknown error')})")
        
        if flipkart_products:
            print(f"\n📱 Sample Flipkart product:")
            sample = flipkart_products[0]
            print(f"   Title: {sample['listing_info']['title']}")
            print(f"   Price: {sample['listing_info']['price_str']}")
            if 'data' in sample['detailed_info']:
                print(f"   Detailed scraped: ✅")
            else:
                print(f"   Detailed scraped: ❌ ({sample['detailed_info'].get('error', 'Unknown error')})")
    
    print("\n" + "="*80)
    print("📋 FULL RESULTS (JSON)")
    print("="*80)
    print(json.dumps(results, indent=2, ensure_ascii=False))
    
    # Save to file
    save_results_to_file(results)
    
    return results

if __name__ == "__main__":
    asyncio.run(main())
    
# ================================================================================
# 🛒 PRODUCT SCRAPING PIPELINE
# ================================================================================
# 🔍 Query: iPhone 16
# 📊 Max products per platform: 5
# 🔍 Max detail pages: 10
# ================================================================================
# 🚀 Step 1: Scraping product listings for 'iPhone 16'...
# [INIT].... → Crawl4AI 0.6.3

# 🌐 Starting to scrape AMAZON...
# 🔗 URL: https://www.amazon.in/s?k=iPhone+16&ref=nb_sb_noss
# [FETCH]... ↓ https://www.amazon.in/s?k=iPhone+16&ref=nb_sb_noss                                                   | ✓ | ⏱: 6.06s 
# [SCRAPE].. ◆ https://www.amazon.in/s?k=iPhone+16&ref=nb_sb_noss                                                   | ✓ | ⏱: 0.62s 
# [EXTRACT]. ■ Completed for https://www.amazon.in/s?k=iPhone+16&ref=nb_sb_noss... | Time: 0.6427810000022873s 
# [COMPLETE] ● https://www.amazon.in/s?k=iPhone+16&ref=nb_sb_noss                                                   | ✓ | ⏱: 7.33s 
# ✅ amazon page loaded successfully
# 📊 Raw data extracted from amazon: 30 items
# 🔍 Sample item from amazon: {'rating': '4.4 out of 5 stars.'}
# ⚠️  Skipping item with no title: {'rating': '4.4 out of 5 stars.'}
# ⚠️  Skipping item with no title: {'rating': '4.4 out of 5 stars.'}
# ⚠️  Skipping item with no title: {'rating': '4.4 out of 5 stars.'}
# ⚠️  Skipping item with no title: {'rating': '4.4 out of 5 stars.'}
# ⚠️  No valid Amazon URL/ASIN for: iPhone 16 128 GB: 5G Mobile Phone with Camera Control, A18 Chip and a Big Boost in Battery Life. Works with AirPods; Black
# ⚠️  No valid Amazon URL/ASIN for: iPhone 16 Pro 128 GB: 5G Mobile Phone with Camera Control, 4K 120 fps Dolby Vision and a Huge Leap in Battery Life. Works with AirPods; Natural Titanium
# ✅ Added amazon product #1: iPhone 16 128 GB: 5G Mobile Phone with Camera Cont...
# ✅ Added amazon product #2: iPhone 16 Pro Max 256 GB: 5G Mobile Phone with Cam...
# ✅ Added amazon product #3: iPhone 16 128 GB: 5G Mobile Phone with Camera Cont...
# ⚠️  No valid Amazon URL/ASIN for: iPhone 16e 128 GB: Built for Apple Intelligence, A18 Chip, Supersized Battery Life, 48MP Fusion. Camera, 15.40 cm (6.1″) Super Retina XDR Display; Blaack
# ⚠️  No valid Amazon URL/ASIN for: iPhone 16e 128 GB: Built for Apple Intelligence, A18 Chip, Supersized Battery Life, 48MP Fusion. Camera, 15.40 cm (6.1″) Super Retina XDR Display; Blaack
# ⚠️  No valid Amazon URL/ASIN for: Apple iPhone 15 (128 GB) - Blue
# ⚠️  No valid Amazon URL/ASIN for: iPhone 16 Pro 128 GB: 5G Mobile Phone with Camera Control, 4K 120 fps Dolby Vision and a Huge Leap in Battery Life. Works with AirPods; Natural Titaniium
# ⚠️  No valid Amazon URL/ASIN for: iPhone 16 Pro Max 256 GB: 5G Mobile Phone with Camera Control, 4K 120 fps Dolby Vision and a Huge Leap in Battery Life. Works with AirPods; Desert Tittanium
# ⚠️  No valid Amazon URL/ASIN for: iPhone 16 512 GB: 5G Mobile Phone with Camera Control, A18 Chip and a Big Boost in Battery Life. Works with AirPods; Ultramarine
# ✅ Added amazon product #4: iPhone 16 128 GB: 5G Mobile Phone with Camera Cont...
# ✅ Added amazon product #5: iPhone 16 Pro 256 GB: 5G Mobile Phone with Camera ...

# 🌐 Starting to scrape FLIPKART...
# 🔗 URL: https://www.flipkart.com/search?q=iPhone%2016
# [FETCH]... ↓ https://www.flipkart.com/search?q=iPhone 16                                                          | ✓ | ⏱: 5.53s 
# [SCRAPE].. ◆ https://www.flipkart.com/search?q=iPhone 16                                                          | ✓ | ⏱: 0.18s 
# [EXTRACT]. ■ Completed for https://www.flipkart.com/search?q=iPhone%2016... | Time: 0.7851784999947995s 
# [COMPLETE] ● https://www.flipkart.com/search?q=iPhone 16                                                          | ✓ | ⏱: 6.51s 
# ✅ flipkart page loaded successfully
# 📊 Raw data extracted from flipkart: 51 items
# 🔍 Sample item from flipkart: {'title': 'Apple iPhone 16 (Black, 128 GB)', 'price': '₹74,900', 'url': '/apple-iphone-16-black-128-gb/p/itmb07d67f995271?pid=MOBH4DQFG8NKFRDY&lid=LSTMOBH4DQFG8NKFRDYNBDOZI&marketplace=FLIPKART&q=iPhone+16&store=tyy%2F4io&spotlightTagId=default_BestsellerId_tyy%2F4io&srno=s_1_1&otracker=search&fm=organic&iid=c111715d-0551-4030-9e77-e494ad176729.MOBH4DQFG8NKFRDY.SEARCH&ppt=sp&ppn=sp&ssid=l3f0en9g8g0000001749372704906&qH=8e0ee2dac8c1afb1'}
# ✅ Added flipkart product #1: Apple iPhone 16 (Black, 128 GB)...
# ⚠️  Skipping duplicate URL: https://www.flipkart.com/apple-iphone-16-black-128-gb/p/itmb07d67f995271?pid=MOBH4DQFG8NKFRDY&lid=LSTMOBH4DQFG8NKFRDYNBDOZI&marketplace=FLIPKART&q=iPhone+166&store=tyy%2F4io&spotlightTagId=default_BestsellerId_tyy%2F4io&srno=s_1_1&otracker=search&fm=organic&iid=c111715d-0551-4030-9e77-e494ad176729.MOBH4DQFG8NKFRDY.SEARCH&ppt=sp&ppn=sp&ssid=l3f0en9g8g0000001749372704906&qH=8e0ee2dac8c1afb1
# ⚠️  Skipping duplicate URL: https://www.flipkart.com/apple-iphone-16-black-128-gb/p/itmb07d67f995271?pid=MOBH4DQFG8NKFRDY&lid=LSTMOBH4DQFG8NKFRDYNBDOZI&marketplace=FLIPKART&q=iPhone+166&store=tyy%2F4io&spotlightTagId=default_BestsellerId_tyy%2F4io&srno=s_1_1&otracker=search&fm=organic&iid=c111715d-0551-4030-9e77-e494ad176729.MOBH4DQFG8NKFRDY.SEARCH&ppt=sp&ppn=sp&ssid=l3f0en9g8g0000001749372704906&qH=8e0ee2dac8c1afb1
# ⚠️  Skipping duplicate URL: https://www.flipkart.com/apple-iphone-16-black-128-gb/p/itmb07d67f995271?pid=MOBH4DQFG8NKFRDY&lid=LSTMOBH4DQFG8NKFRDYNBDOZI&marketplace=FLIPKART&q=iPhone+166&store=tyy%2F4io&spotlightTagId=default_BestsellerId_tyy%2F4io&srno=s_1_1&otracker=search&fm=organic&iid=c111715d-0551-4030-9e77-e494ad176729.MOBH4DQFG8NKFRDY.SEARCH&ppt=sp&ppn=sp&ssid=l3f0en9g8g0000001749372704906&qH=8e0ee2dac8c1afb1
# ✅ Added flipkart product #2: Apple iPhone 16 (Pink, 256 GB)...
# ⚠️  Skipping duplicate URL: https://www.flipkart.com/apple-iphone-16-pink-256-gb/p/itm0d8c695cded44?pid=MOBH4DQF28XAYM2S&lid=LSTMOBH4DQF28XAYM2S3JPA23&marketplace=FLIPKART&q=iPhone+16&&store=tyy%2F4io&srno=s_1_2&otracker=search&fm=organic&iid=c111715d-0551-4030-9e77-e494ad176729.MOBH4DQF28XAYM2S.SEARCH&ppt=None&ppn=None&ssid=l3f0en9g8g0000001749372704906&qH=8e0ee2dac8c1afb1
# ✅ Added flipkart product #3: Apple iPhone 16 (Black, 256 GB)...
# ⚠️  Skipping duplicate URL: https://www.flipkart.com/apple-iphone-16-black-256-gb/p/itm86da1977dcdf1?pid=MOBH4DQFZCJJXUFG&lid=LSTMOBH4DQFZCJJXUFGO5DY3W&marketplace=FLIPKART&q=iPhone+166&store=tyy%2F4io&srno=s_1_3&otracker=search&fm=organic&iid=c111715d-0551-4030-9e77-e494ad176729.MOBH4DQFZCJJXUFG.SEARCH&ppt=None&ppn=None&ssid=l3f0en9g8g0000001749372704906&qH=8e0ee2dac8c1afb1
# ✅ Added flipkart product #4: Apple iPhone 16 (Teal, 128 GB)...
# ⚠️  Skipping duplicate URL: https://www.flipkart.com/apple-iphone-16-teal-128-gb/p/itmce4bb3f55cc2f?pid=MOBH4DQFSY9ETDUU&lid=LSTMOBH4DQFSY9ETDUUI6AN3O&marketplace=FLIPKART&q=iPhone+16&&store=tyy%2F4io&srno=s_1_4&otracker=search&fm=organic&iid=c111715d-0551-4030-9e77-e494ad176729.MOBH4DQFSY9ETDUU.SEARCH&ppt=None&ppn=None&ssid=l3f0en9g8g0000001749372704906&qH=8e0ee2dac8c1afb1
# ✅ Added flipkart product #5: Apple iPhone 16 (White, 128 GB)...

# 📈 SCRAPING SUMMARY:
#    Amazon products found: 5
#    Flipkart products found: 5
#    Total unique listings: 10

# ✅ Found 10 product listings total

# 🚀 Step 2: Scraping detailed information for up to 10 products...

# 📦 Processing product 1/10
#    Platform: Amazon
#    Title: iPhone 16 128 GB: 5G Mobile Phone with Camera Control, A18 C...
# 🔍 Scraping details for: https://www.amazon.in/dp/B0DGJH8RYG...
# 📱 Platform detected: amazon
# ✅ Successfully scraped amazon product details

# 📦 Processing product 2/10
#    Platform: Amazon
#    Title: iPhone 16 Pro Max 256 GB: 5G Mobile Phone with Camera Contro...
# 🔍 Scraping details for: https://www.amazon.in/dp/B0DGHYDZR9...
# 📱 Platform detected: amazon
# ✅ Successfully scraped amazon product details

# 📦 Processing product 3/10
#    Platform: Amazon
#    Title: iPhone 16 128 GB: 5G Mobile Phone with Camera Control, A18 C...
# 🔍 Scraping details for: https://www.amazon.in/dp/B0DGHZWBYB...
# 📱 Platform detected: amazon
# ✅ Successfully scraped amazon product details

# 📦 Processing product 4/10
#    Platform: Amazon
#    Title: iPhone 16 128 GB: 5G Mobile Phone with Camera Control, A18 C...
# 🔍 Scraping details for: https://www.amazon.in/dp/B0DGJHBX5Y...
# 📱 Platform detected: amazon
# ✅ Successfully scraped amazon product details

# 📦 Processing product 5/10
#    Platform: Amazon
#    Title: iPhone 16 Pro 256 GB: 5G Mobile Phone with Camera Control, 4...
# 🔍 Scraping details for: https://www.amazon.in/dp/B0DGJC8DG8...
# 📱 Platform detected: amazon
# ✅ Successfully scraped amazon product details

# 📦 Processing product 6/10
#    Platform: Flipkart
#    Title: Apple iPhone 16 (Black, 128 GB)...
# 🔍 Scraping details for: https://www.flipkart.com/apple-iphone-16-black-128-gb/p/itmb07d67f995271?pid=MOB...
# 📱 Platform detected: flipkart
# ✅ Successfully scraped flipkart product details

# 📦 Processing product 7/10
#    Platform: Flipkart
#    Title: Apple iPhone 16 (Pink, 256 GB)...
# 🔍 Scraping details for: https://www.flipkart.com/apple-iphone-16-pink-256-gb/p/itm0d8c695cded44?pid=MOBH...
# 📱 Platform detected: flipkart
# ✅ Successfully scraped flipkart product details

# 📦 Processing product 8/10
#    Platform: Flipkart
#    Title: Apple iPhone 16 (Black, 256 GB)...
# 🔍 Scraping details for: https://www.flipkart.com/apple-iphone-16-black-256-gb/p/itm86da1977dcdf1?pid=MOB...
# 📱 Platform detected: flipkart
# ✅ Successfully scraped flipkart product details

# 📦 Processing product 9/10
#    Platform: Flipkart
#    Title: Apple iPhone 16 (Teal, 128 GB)...
# 🔍 Scraping details for: https://www.flipkart.com/apple-iphone-16-teal-128-gb/p/itmce4bb3f55cc2f?pid=MOBH...
# 📱 Platform detected: flipkart
# ✅ Successfully scraped flipkart product details

# 📦 Processing product 10/10
#    Platform: Flipkart
#    Title: Apple iPhone 16 (White, 128 GB)...
# 🔍 Scraping details for: https://www.flipkart.com/apple-iphone-16-white-128-gb/p/itm7c0281cd247be?pid=MOB...
# 📱 Platform detected: flipkart
# ✅ Successfully scraped flipkart product details

# ================================================================================
# 📊 FINAL RESULTS SUMMARY
# ================================================================================
# 🛒 Amazon products: 5
# 🛒 Flipkart products: 5
# 🛒 Total products: 10

# 📱 Sample Amazon product:
#    Title: iPhone 16 128 GB: 5G Mobile Phone with Camera Control, A18 Chip and a Big Boost in Battery Life. Works with AirPods; Teal
#    Price: ₹73,500
#    Detailed scraped: ✅

# 📱 Sample Flipkart product:
#    Title: Apple iPhone 16 (Black, 128 GB)
#    Price: ₹74,900
#    Detailed scraped: ✅

# ================================================================================
# 📋 FULL RESULTS (JSON)
# ================================================================================
# {
#   "query": "iPhone 16",
#   "total_listings_found": 10,
#   "detailed_products_processed": 10,
#   "products": [
#     {
#       "listing_info": {
#         "title": "iPhone 16 128 GB: 5G Mobile Phone with Camera Control, A18 Chip and a Big Boost in Battery Life. Works with AirPods; Teal",
#         "price_str": "₹73,500",
#         "rating_str": "4.4 out of 5 stars",
#         "url": "https://www.amazon.in/dp/B0DGJH8RYG",
#         "platform": "Amazon"
#       },
#       "detailed_info": {
#         "platform": "amazon",
#         "url": "https://www.amazon.in/dp/B0DGJH8RYG",
#         "data": {
#           "product_title": "iPhone 16 128 GB: 5G Mobile Phone with Camera Control, A18 Chip and a Big Boost in Battery Life. Works with AirPods; Teal",
#           "price": "₹73,500.00",
#           "offers": [
#             "Upto ₹4,000.00 discount on select Credit Cards",
#             "Upto ₹3,311.61 EMI interest savings on select Credit Cards",
#             "Upto ₹2,205.00 cashback as Amazon Pay Balance when you pay with Amazon Pay ICICI Bank Credit Cards",
#             "Get GST invoice and save up to 28% on business purchases."
#           ],
#           "brand": "Apple",
#           "asin": "B0DGJH8RYG"
#         }
#       }
#     },
#     {
#       "listing_info": {
#         "title": "iPhone 16 Pro Max 256 GB: 5G Mobile Phone with Camera Control, 4K 120 fps Dolby Vision and a Huge Leap in Battery Life. Works with AirPods; Desert Titanium",
#         "price_str": "₹1,35,900",
#         "rating_str": "4.3 out of 5 stars",
#         "url": "https://www.amazon.in/dp/B0DGHYDZR9",
#         "platform": "Amazon"
#       },
#       "detailed_info": {
#         "platform": "amazon",
#         "url": "https://www.amazon.in/dp/B0DGHYDZR9",
#         "data": {
#           "product_title": "iPhone 16 Pro Max 256 GB: 5G Mobile Phone with Camera Control, 4K 120 fps Dolby Vision and a Huge Leap in Battery Life. Works with AirPods; Desert Titanium",
#           "price": "₹1,35,900.00",
#           "offers": [
#             "Upto ₹6,123.10 EMI interest savings on select Credit Cards",
#             "Upto ₹3,000.00 discount on select Credit Cards",
#             "Upto ₹4,077.00 cashback as Amazon Pay Balance when you pay with Amazon Pay ICICI Bank Credit Cards",
#             "Get GST invoice and save up to 28% on business purchases."
#           ],
#           "brand": "Apple",
#           "asin": "B0DGHYDZR9"
#         }
#       }
#     },
#     {
#       "listing_info": {
#         "title": "iPhone 16 128 GB: 5G Mobile Phone with Camera Control, A18 Chip and a Big Boost in Battery Life. Works with AirPods; White",
#         "price_str": "₹73,500",
#         "rating_str": "4.4 out of 5 stars",
#         "url": "https://www.amazon.in/dp/B0DGHZWBYB",
#         "platform": "Amazon"
#       },
#       "detailed_info": {
#         "platform": "amazon",
#         "url": "https://www.amazon.in/dp/B0DGHZWBYB",
#         "data": {
#           "product_title": "iPhone 16 128 GB: 5G Mobile Phone with Camera Control, A18 Chip and a Big Boost in Battery Life. Works with AirPods; White",
#           "price": "₹73,500.00",
#           "offers": [
#             "Upto ₹4,000.00 discount on select Credit Cards",
#             "Upto ₹3,311.61 EMI interest savings on select Credit Cards",
#             "Upto ₹2,205.00 cashback as Amazon Pay Balance when you pay with Amazon Pay ICICI Bank Credit Cards",
#             "Get GST invoice and save up to 28% on business purchases."
#           ],
#           "brand": "Apple",
#           "asin": "B0DGHZWBYB"
#         }
#       }
#     },
#     {
#       "listing_info": {
#         "title": "iPhone 16 128 GB: 5G Mobile Phone with Camera Control, A18 Chip and a Big Boost in Battery Life. Works with AirPods; Black",
#         "price_str": "₹73,500",
#         "rating_str": "4.4 out of 5 stars",
#         "url": "https://www.amazon.in/dp/B0DGJHBX5Y",
#         "platform": "Amazon"
#       },
#       "detailed_info": {
#         "platform": "amazon",
#         "url": "https://www.amazon.in/dp/B0DGJHBX5Y",
#         "data": {
#           "product_title": "iPhone 16 128 GB: 5G Mobile Phone with Camera Control, A18 Chip and a Big Boost in Battery Life. Works with AirPods; Black",
#           "price": "₹73,500.00",
#           "offers": [
#             "Upto ₹4,000.00 discount on select Credit Cards",
#             "Upto ₹3,311.61 EMI interest savings on select Credit Cards",
#             "Upto ₹2,205.00 cashback as Amazon Pay Balance when you pay with Amazon Pay ICICI Bank Credit Cards",
#             "Get GST invoice and save up to 28% on business purchases."
#           ],
#           "brand": "Apple",
#           "asin": "B0DGJHBX5Y"
#         }
#       }
#     },
#     {
#       "listing_info": {
#         "title": "iPhone 16 Pro 256 GB: 5G Mobile Phone with Camera Control, 4K 120 fps Dolby Vision and a Huge Leap in Battery Life. Works with AirPods; Black Titanium",
#         "price_str": "₹1,22,900",
#         "rating_str": "4.4 out of 5 stars",
#         "url": "https://www.amazon.in/dp/B0DGJC8DG8",
#         "platform": "Amazon"
#       },
#       "detailed_info": {
#         "platform": "amazon",
#         "url": "https://www.amazon.in/dp/B0DGJC8DG8",
#         "data": {
#           "product_title": "iPhone 16 Pro 256 GB: 5G Mobile Phone with Camera Control, 4K 120 fps Dolby Vision and a Huge Leap in Battery Life. Works with AirPods; Black Titanium",    
#           "price": "₹1,22,900.00",
#           "offers": [
#             "Upto ₹3,000.00 discount on select Credit Cards",
#             "Upto ₹5,537.39 EMI interest savings on select Credit Cards",
#             "Upto ₹3,687.00 cashback as Amazon Pay Balance when you pay with Amazon Pay ICICI Bank Credit Cards",
#             "Get GST invoice and save up to 28% on business purchases."
#           ],
#           "brand": "Apple",
#           "asin": "B0DGJC8DG8"
#         }
#       }
#     },
#     {
#       "listing_info": {
#         "title": "Apple iPhone 16 (Black, 128 GB)",
#         "price_str": "₹74,900",
#         "rating_str": null,
#         "url": "https://www.flipkart.com/apple-iphone-16-black-128-gb/p/itmb07d67f995271?pid=MOBH4DQFG8NKFRDY&lid=LSTMOBH4DQFG8NKFRDYNBDOZI&marketplace=FLIPKART&q=iPhone+16&store=tyy%2F4io&spotlightTagId=default_BestsellerId_tyy%2F4io&srno=s_1_1&otracker=search&fm=organic&iid=c111715d-0551-4030-9e77-e494ad176729.MOBH4DQFG8NKFRDY.SEARCH&ppt=sp&ppn=sp&ssid=l3f0en9g8g0000001749372704906&qH=8e0ee2dac8c1afb1",
#         "platform": "Flipkart"
#       },
#       "detailed_info": {
#         "platform": "flipkart",
#         "url": "https://www.flipkart.com/apple-iphone-16-black-128-gb/p/itmb07d67f995271?pid=MOBH4DQFG8NKFRDY&lid=LSTMOBH4DQFG8NKFRDYNBDOZI&marketplace=FLIPKART&q=iPhone+16&store=tyy%2F4io&spotlightTagId=default_BestsellerId_tyy%2F4io&srno=s_1_1&otracker=search&fm=organic&iid=c111715d-0551-4030-9e77-e494ad176729.MOBH4DQFG8NKFRDY.SEARCH&ppt=sp&ppn=sp&ssid=l3f0en9g8g0000001749372704906&qH=8e0ee2dac8c1afb1",
#         "data": {
#           "product_title": "Apple iPhone 16 (Black, 128 GB)",
#           "price": "₹74,900",
#           "original_price": "₹79,900",
#           "discount": "6% off",
#           "offers": [
#             "5% Unlimited Cashback on Flipkart Axis Bank Credit Card",
#             "₹2500 Off On Flipkart Axis Bank Credit Card Non EMI Transactions.",
#             "₹4000 Off On All Banks Credit Card Transactions.",
#             "Get extra ₹5000 off (price inclusive of cashback/coupon)"
#           ],
#           "brand": "Apple",
#           "rating": "4.6",
#           "reviews_count": "725"
#         }
#       }
#     },
#     {
#       "listing_info": {
#         "title": "Apple iPhone 16 (Pink, 256 GB)",
#         "price_str": "₹84,900",
#         "rating_str": null,
#         "url": "https://www.flipkart.com/apple-iphone-16-pink-256-gb/p/itm0d8c695cded44?pid=MOBH4DQF28XAYM2S&lid=LSTMOBH4DQF28XAYM2S3JPA23&marketplace=FLIPKART&q=iPhone+16&store=tyy%2F4io&srno=s_1_2&otracker=search&fm=organic&iid=c111715d-0551-4030-9e77-e494ad176729.MOBH4DQF28XAYM2S.SEARCH&ppt=None&ppn=None&ssid=l3f0en9g8g0000001749372704906&qH=8e0ee2dac8c1afb1",   
#         "platform": "Flipkart"
#       },
#       "detailed_info": {
#         "platform": "flipkart",
#         "url": "https://www.flipkart.com/apple-iphone-16-pink-256-gb/p/itm0d8c695cded44?pid=MOBH4DQF28XAYM2S&lid=LSTMOBH4DQF28XAYM2S3JPA23&marketplace=FLIPKART&q=iPhone+16&store=tyy%2F4io&srno=s_1_2&otracker=search&fm=organic&iid=c111715d-0551-4030-9e77-e494ad176729.MOBH4DQF28XAYM2S.SEARCH&ppt=None&ppn=None&ssid=l3f0en9g8g0000001749372704906&qH=8e0ee2dac8c1afb1",   
#         "data": {
#           "product_title": "Apple iPhone 16 (Pink, 256 GB)",
#           "price": "₹84,900",
#           "original_price": "₹89,900",
#           "discount": "5% off",
#           "offers": [
#             "5% Unlimited Cashback on Flipkart Axis Bank Credit Card",
#             "₹2500 Off On Flipkart Axis Bank Credit Card Non EMI Transactions.",
#             "₹4000 Off On All Banks Credit Card Transactions.",
#             "Get extra ₹5000 off (price inclusive of cashback/coupon)"
#           ],
#           "brand": "Apple",
#           "rating": "4.6",
#           "reviews_count": "17,203 Ratings & 725 Reviews"
#         }
#       }
#     },
#     {
#       "listing_info": {
#         "title": "Apple iPhone 16 (Black, 256 GB)",
#         "price_str": "₹84,900",
#         "rating_str": null,
#         "url": "https://www.flipkart.com/apple-iphone-16-black-256-gb/p/itm86da1977dcdf1?pid=MOBH4DQFZCJJXUFG&lid=LSTMOBH4DQFZCJJXUFGO5DY3W&marketplace=FLIPKART&q=iPhone+16&store=tyy%2F4io&srno=s_1_3&otracker=search&fm=organic&iid=c111715d-0551-4030-9e77-e494ad176729.MOBH4DQFZCJJXUFG.SEARCH&ppt=None&ppn=None&ssid=l3f0en9g8g0000001749372704906&qH=8e0ee2dac8c1afb1",  
#         "platform": "Flipkart"
#       },
#       "detailed_info": {
#         "platform": "flipkart",
#         "url": "https://www.flipkart.com/apple-iphone-16-black-256-gb/p/itm86da1977dcdf1?pid=MOBH4DQFZCJJXUFG&lid=LSTMOBH4DQFZCJJXUFGO5DY3W&marketplace=FLIPKART&q=iPhone+16&store=tyy%2F4io&srno=s_1_3&otracker=search&fm=organic&iid=c111715d-0551-4030-9e77-e494ad176729.MOBH4DQFZCJJXUFG.SEARCH&ppt=None&ppn=None&ssid=l3f0en9g8g0000001749372704906&qH=8e0ee2dac8c1afb1",  
#         "data": {
#           "product_title": "Apple iPhone 16 (Black, 256 GB)",
#           "price": "₹84,900",
#           "original_price": "₹89,900",
#           "discount": "5% off",
#           "offers": [
#             "5% Unlimited Cashback on Flipkart Axis Bank Credit Card",
#             "₹2500 Off On Flipkart Axis Bank Credit Card Non EMI Transactions.",
#             "₹4000 Off On All Banks Credit Card Transactions.",
#             "Get extra ₹5000 off (price inclusive of cashback/coupon)"
#           ],
#           "brand": "Apple",
#           "rating": "4.6",
#           "reviews_count": "17,203"
#         }
#       }
#     },
#     {
#       "listing_info": {
#         "title": "Apple iPhone 16 (Teal, 128 GB)",
#         "price_str": "₹74,900",
#         "rating_str": null,
#         "url": "https://www.flipkart.com/apple-iphone-16-teal-128-gb/p/itmce4bb3f55cc2f?pid=MOBH4DQFSY9ETDUU&lid=LSTMOBH4DQFSY9ETDUUI6AN3O&marketplace=FLIPKART&q=iPhone+16&store=tyy%2F4io&srno=s_1_4&otracker=search&fm=organic&iid=c111715d-0551-4030-9e77-e494ad176729.MOBH4DQFSY9ETDUU.SEARCH&ppt=None&ppn=None&ssid=l3f0en9g8g0000001749372704906&qH=8e0ee2dac8c1afb1",   
#         "platform": "Flipkart"
#       },
#       "detailed_info": {
#         "platform": "flipkart",
#         "url": "https://www.flipkart.com/apple-iphone-16-teal-128-gb/p/itmce4bb3f55cc2f?pid=MOBH4DQFSY9ETDUU&lid=LSTMOBH4DQFSY9ETDUUI6AN3O&marketplace=FLIPKART&q=iPhone+16&store=tyy%2F4io&srno=s_1_4&otracker=search&fm=organic&iid=c111715d-0551-4030-9e77-e494ad176729.MOBH4DQFSY9ETDUU.SEARCH&ppt=None&ppn=None&ssid=l3f0en9g8g0000001749372704906&qH=8e0ee2dac8c1afb1",   
#         "data": {
#           "product_title": "Apple iPhone 16 (Teal, 128 GB)",
#           "price": "₹74,900",
#           "original_price": "₹79,900",
#           "discount": "6% off",
#           "offers": [
#             "5% Unlimited Cashback on Flipkart Axis Bank Credit Card",
#             "₹2500 Off On Flipkart Axis Bank Credit Card Non EMI Transactions.",
#             "₹4000 Off On All Banks Credit Card Transactions.",
#             "Get extra ₹5000 off (price inclusive of cashback/coupon)"
#           ],
#           "brand": "Apple",
#           "rating": "4.6",
#           "reviews_count": "17,203 Ratings & 725 Reviews"
#         }
#       }
#     },
#     {
#       "listing_info": {
#         "title": "Apple iPhone 16 (White, 128 GB)",
#         "price_str": "₹74,900",
#         "rating_str": null,
#         "url": "https://www.flipkart.com/apple-iphone-16-white-128-gb/p/itm7c0281cd247be?pid=MOBH4DQF849HCG6G&lid=LSTMOBH4DQF849HCG6GXHBPXY&marketplace=FLIPKART&q=iPhone+16&store=tyy%2        "url": "https://www.flipkart.com/apple-iphone-16-white-128-gb/p/itm7c0281cd247be?pid=MOBH4DQF849HCG6G&lid=LSTMOBH4DQF849HCG6GXHBPXY&marketplace=FLIPKART&q=iPhone+16&store=tyy%2F4io&spotlightTagId=default_BestsellerId_tyy%2F4io&srno=s_1_5&otracker=search&fm=organic&iid=c111715d-0551-4030-9e77-e494ad176729.MOBH4DQF849HCG6G.SEARCH&ppt=sp&ppn=sp&ssid=l3f0en9g8g0000001749372704906&qH=8e0ee2dac8c1afb1",
#         "platform": "Flipkart"
# 000001749372704906&qH=8e0ee2dac8c1afb1",
#         "platform": "Flipkart"
#       },
#         "platform": "Flipkart"
#       },
#       },
#       "detailed_info": {
#       "detailed_info": {
#         "platform": "flipkart",
#         "platform": "flipkart",
#         "url": "https://www.flipkart.com/apple-iphone-16-white-128-gb/p/itm7c0281cd247be?pid=MOBH4DQF849HCG6G&lid=LSTMOBH4DQF849HCG6GXHBPXY&marketplace=FLIPKART&q=iPhone+16&store=tyy%2        "url": "https://www.flipkart.com/apple-iphone-16-white-128-gb/p/itm7c0281cd247be?pid=MOBH4DQF849HCG6G&lid=LSTMOBH4DQF849HCG6GXHBPXY&marketplace=FLIPKART&q=iPhone+16&store=tyy%2F4io&spotlightTagId=default_BestsellerId_tyy%2F4io&srno=s_1_5&otracker=search&fm=organic&iid=c111715d-0551-4030-9e77-e494ad176729.MOBH4DQF849HCG6G.SEARCH&ppt=sp&ppn=sp&ssid=l3f0en9g8g0F4io&spotlightTagId=default_BestsellerId_tyy%2F4io&srno=s_1_5&otracker=search&fm=organic&iid=c111715d-0551-4030-9e77-e494ad176729.MOBH4DQF849HCG6G.SEARCH&ppt=sp&ppn=sp&ssid=l3f0en9g8g0000001749372704906&qH=8e0ee2dac8c1afb1",
#         "data": {
#           "product_title": "Apple iPhone 16 (White, 128 GB)",
#           "price": "₹74,900",
#           "original_price": "₹79,900",
#           "discount": "6% off",
#           "offers": [
#             "5% Unlimited Cashback on Flipkart Axis Bank Credit Card",
#             "₹2500 Off On Flipkart Axis Bank Credit Card Non EMI Transactions.",
#             "₹4000 Off On All Banks Credit Card Transactions.",
#             "Get extra ₹5000 off (price inclusive of cashback/coupon)"
#           ],
#           "brand": "Apple",
#           "rating": "4.6",
#           "reviews_count": "725"
#         }
#       }
#     }
#   ]
# }
# 💾 Results saved to product_results.json