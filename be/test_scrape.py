import asyncio
import re
import json
from typing import List, Dict, Optional
from crawl4ai import AsyncWebCrawler, LLMConfig
from crawl4ai.extraction_strategy import LLMExtractionStrategy
from pydantic import BaseModel, Field
import os
from dotenv import load_dotenv

load_dotenv()

class Product(BaseModel):
    title: str = Field(description="Product name/title")
    price: str = Field(description="Current price of the product")
    url: str = Field(description="Product URL/link")
    platform: str = Field(description="Platform name (Blinkit/Zepto)")

class ProductList(BaseModel):
    products: List[Product] = Field(description="List of products found")

# Platform configurations
PLATFORMS = {
    "blinkit": {
        "search_url": "https://blinkit.com/s/?q={query}",
        "base_url": "https://blinkit.com",
        "name": "Blinkit"
    },
    "zepto": {
        "search_url": "https://www.zeptonow.com/search?query={query}",
        "base_url": "https://www.zeptonow.com",
        "name": "Zepto"
    }
}

# JavaScript for enhanced page interaction
ENHANCED_JS = """
async function enhancePageForScraping() {
    console.log('Starting page enhancement...');
    
    // Wait for initial load
    await new Promise(resolve => setTimeout(resolve, 3000));
    
    // Handle location/permission modals
    try {
        const modals = document.querySelectorAll(
            '[role="dialog"], [class*="modal"], [class*="popup"], [class*="overlay"]'
        );
        
        for (const modal of modals) {
            const closeButtons = modal.querySelectorAll(
                'button, [role="button"], [class*="close"], [class*="cancel"], [class*="skip"]'
            );
            
            for (const btn of closeButtons) {
                const text = btn.textContent?.toLowerCase() || '';
                if (text.includes('close') || text.includes('cancel') || 
                    text.includes('skip') || text.includes('later') ||
                    btn.getAttribute('aria-label')?.toLowerCase().includes('close')) {
                    try {
                        btn.click();
                        console.log('Closed modal');
                        await new Promise(resolve => setTimeout(resolve, 1000));
                    } catch (e) {
                        console.log('Failed to close modal:', e);
                    }
                }
            }
        }
    } catch (e) {
        console.log('Modal handling error:', e);
    }
    
    // Set default location if location input exists
    try {
        const locationInputs = document.querySelectorAll(
            'input[placeholder*="location" i], input[placeholder*="pincode" i], input[placeholder*="area" i]'
        );
        
        for (const input of locationInputs) {
            input.value = '110001';
            input.dispatchEvent(new Event('input', { bubbles: true }));
            input.dispatchEvent(new Event('change', { bubbles: true }));
            await new Promise(resolve => setTimeout(resolve, 500));
        }
    } catch (e) {
        console.log('Location input error:', e);
    }
    
    await new Promise(resolve => setTimeout(resolve, 2000));
    
    // Progressive scrolling to load lazy content
    const maxHeight = Math.max(document.body.scrollHeight, 4000);
    const scrollSteps = 4;
    
    for (let i = 0; i < scrollSteps; i++) {
        const scrollY = (i + 1) * (maxHeight / scrollSteps);
        window.scrollTo({ top: scrollY, behavior: 'smooth' });
        console.log(`Scrolled to: ${scrollY}`);
        
        // Trigger events that might load more content
        window.dispatchEvent(new Event('scroll'));
        window.dispatchEvent(new Event('resize'));
        
        await new Promise(resolve => setTimeout(resolve, 2000));
        
        // Look for and click "Load More" buttons
        const loadMoreButtons = document.querySelectorAll('button, [role="button"]');
        for (const btn of loadMoreButtons) {
            const text = btn.textContent?.toLowerCase() || '';
            if (text.includes('load more') || text.includes('show more') || text.includes('view more')) {
                try {
                    btn.click();
                    console.log('Clicked load more button');
                    await new Promise(resolve => setTimeout(resolve, 1500));
                } catch (e) {
                    console.log('Failed to click load more:', e);
                }
            }
        }
    }
    
    // Scroll back to top
    window.scrollTo({ top: 0, behavior: 'smooth' });
    await new Promise(resolve => setTimeout(resolve, 2000));
    
    // Log available product elements for debugging
    const productSelectors = [
        'div[data-testid*="product"]',
        'div[class*="Product"]',
        'div[class*="product"]',
        'article[class*="product"]',
        'div[class*="Item"]',
        'div[class*="item"]'
    ];
    
    let totalProducts = 0;
    productSelectors.forEach(selector => {
        const elements = document.querySelectorAll(selector);
        if (elements.length > 0) {
            console.log(`Found ${elements.length} elements for: ${selector}`);
            totalProducts += elements.length;
        }
    });
    
    console.log(`Total potential products found: ${totalProducts}`);
    console.log('Page enhancement completed');
    
    return true;
}

// Execute enhancement
enhancePageForScraping();
"""

class GroceryProductScraper:
    def __init__(self):
        self.platforms = PLATFORMS
        
    async def scrape_platform(self, platform_name: str, query: str, max_products: int = 2) -> List[Dict]:
        """Scrape products from a specific platform using Crawl4AI"""
        
        if platform_name not in self.platforms:
            raise ValueError(f"Platform {platform_name} not supported. Available: {list(self.platforms.keys())}")
        
        config = self.platforms[platform_name]
        search_url = config["search_url"].format(query=query.replace(" ", "%20"))
        
        print(f"🔍 Scraping {config['name']} for '{query}'...")
        print(f"📍 URL: {search_url}")
        
        # LLM extraction strategy with detailed instructions
        extraction_strategy = LLMExtractionStrategy(
            llm_config=LLMConfig(
                provider="gpt-4o-mini",
                api_token=os.getenv("OPENAI_API_KEY")
            ),
            schema=ProductList.model_json_schema(),
            extraction_type="schema",
            instruction=f"""
            Extract product information from this {config['name']} search results page.
            
            Look for product listings, cards, or tiles that contain:
            1. Product title/name (avoid generic text like "Welcome", "Login", "Cart", etc.)
            2. Price information (look for ₹ symbol or "Rs" prefix)
            3. Product links/URLs (usually contain /product/, /p/, /pn/, /prn/, /pvid/ in the path)
            
            Rules:
            - Only extract actual products, not navigation elements, ads, or UI components
            - Product titles should be descriptive and relate to the search query
            - Prices should include currency symbol or be clearly identifiable as prices
            - URLs should be complete product page links
            - Maximum {max_products} products
            - Skip items with titles like "Add to Cart", "Login", "Search", "Filter", etc.
            - Platform should be "{config['name']}"
            
            Focus on quality over quantity - better to return fewer accurate products than many incorrect ones.
            """
        )
        
        async with AsyncWebCrawler(
            headless=True,
            browser_type="chromium",
            verbose=True
        ) as crawler:
            try:
                result = await crawler.arun(
                    url=search_url,
                    extraction_strategy=extraction_strategy,
                    js_code=ENHANCED_JS,
                    wait_for="networkidle",
                    page_timeout=60000,
                    delay_before_return_html=5.0,
                    simulate_user=True,
                    override_navigator=True
                )
                
                if result.success and result.extracted_content:
                    try:
                        # Parse the extracted JSON
                        extracted_data = json.loads(result.extracted_content)
                        products = extracted_data.get('products', [])
                        
                        # Clean and validate products
                        cleaned_products = self._clean_products(products, config, max_products)
                        
                        print(f"✅ Successfully extracted {len(cleaned_products)} products from {config['name']}")
                        return cleaned_products
                        
                    except json.JSONDecodeError as e:
                        print(f"❌ JSON parsing error for {config['name']}: {e}")
                        return []
                else:
                    print(f"❌ Failed to scrape {config['name']}: {result.error_message if hasattr(result, 'error_message') else 'Unknown error'}")
                    return []
                    
            except Exception as e:
                print(f"❌ Error scraping {config['name']}: {str(e)}")
                return []
    
    def _clean_products(self, products: List[Dict], config: Dict, max_products: int) -> List[Dict]:
        """Clean and validate extracted products"""
        cleaned = []
        seen_titles = set()
        
        for product in products[:max_products * 2]:  # Process more than needed to filter better ones
            if len(cleaned) >= max_products:
                break
                
            title = product.get('title', '').strip()
            price = product.get('price', '').strip()
            url = product.get('url', '').strip()
            
            # Validate title
            if not title or len(title) < 3:
                continue
                
            # Skip obvious non-product content
            skip_patterns = [
                r'welcome\s+to', r'sign\s+in', r'log\s*in', r'register', r'cart',
                r'add\s+to', r'continue', r'search', r'filter', r'sort', r'menu',
                r'account', r'profile', r'help', r'support', r'contact', r'about',
                r'terms', r'privacy', r'delivery', r'location', r'detect'
            ]
            
            if any(re.search(pattern, title.lower()) for pattern in skip_patterns):
                continue
            
            # Skip duplicates
            if title.lower() in seen_titles:
                continue
            seen_titles.add(title.lower())
            
            # Clean and validate URL
            if url and not url.startswith('http'):
                if url.startswith('/'):
                    url = config['base_url'] + url
                else:
                    url = config['base_url'] + '/' + url
            elif not url:
                url = config['search_url']  # Fallback URL
            
            # Clean price
            if price:
                price = re.sub(r'\s+', ' ', price)
            
            cleaned.append({
                'title': title,
                'price': price,
                'url': url,
                'platform': config['name']
            })
        
        return cleaned[:max_products]
    
    async def scrape_all_platforms(self, query: str, max_products_per_platform: int = 2) -> Dict[str, List[Dict]]:
        """Scrape all platforms for the given query"""
        print(f"🚀 Starting scrape for query: '{query}' (max {max_products_per_platform} per platform)")
        print("=" * 60)
        
        results = {}
        
        for platform_name in self.platforms.keys():
            try:
                products = await self.scrape_platform(platform_name, query, max_products_per_platform)
                results[platform_name] = products
                
                if products:
                    print(f"✅ {self.platforms[platform_name]['name']}: {len(products)} products found")
                    for i, product in enumerate(products, 1):
                        print(f"   {i}. {product['title'][:50]}{'...' if len(product['title']) > 50 else ''}")
                        print(f"      Price: {product['price']} | URL: {product['url'][:50]}...")
                else:
                    print(f"⚠️  {self.platforms[platform_name]['name']}: No products found")
                    
            except Exception as e:
                print(f"❌ {self.platforms[platform_name]['name']}: Error - {str(e)}")
                results[platform_name] = []
            
            print("-" * 40)
        
        return results

async def main():
    """Main function to demonstrate the scraper"""
    scraper = GroceryProductScraper()
    
    # Get user input
    query = input("🔍 Enter product to search (e.g., 'iPhone 16'): ").strip()
    if not query:
        query = "iPhone 16"  # Default query
        
    try:
        max_products = int(input("📊 Max products per platform (default 2): ") or "2")
    except ValueError:
        max_products = 2
    
    print(f"\n🎯 Searching for '{query}' with max {max_products} products per platform...")
    print("=" * 60)
    
    # Scrape all platforms
    results = await scraper.scrape_all_platforms(query, max_products)
    
    # Display summary
    print("\n📋 SCRAPING SUMMARY")
    print("=" * 60)
    
    total_products = 0
    for platform, products in results.items():
        total_products += len(products)
        print(f"{scraper.platforms[platform]['name']}: {len(products)} products")
    
    print(f"Total products found: {total_products}")
    
    # Save results to JSON file
    output_file = f"grocery_products_{query.replace(' ', '_').lower()}.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 Results saved to: {output_file}")
    
    # Display detailed results
    if total_products > 0:
        print(f"\n🛍️  DETAILED RESULTS FOR '{query.upper()}'")
        print("=" * 60)
        
        for platform, products in results.items():
            if products:
                print(f"\n🏪 {scraper.platforms[platform]['name'].upper()}")
                print("-" * 30)
                for i, product in enumerate(products, 1):
                    print(f"{i}. Title: {product['title']}")
                    print(f"   Price: {product['price']}")
                    print(f"   URL: {product['url']}")
                    print()

if __name__ == "__main__":
    # You need to set your OpenAI API key as environment variable
    # export OPENAI_API_KEY="your-api-key-here"
    asyncio.run(main())