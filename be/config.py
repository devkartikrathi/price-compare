from crawl4ai import BrowserConfig

# --- Browser Configuration ---
BROWSER_CONFIG = BrowserConfig(
    headless=True,
    viewport_width=1920,
    viewport_height=1080,
    verbose=False,
    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    java_script_enabled=True,
)

# --- CSS Extraction Schemas ---
AMAZON_CSS_LISTING_SCHEMA = {
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

FLIPKART_CSS_LISTING_SCHEMA = {
    "name": "FlipkartProductListing",
    "baseSelector": 'div[data-id], div._13oc-S, div.cPHDOP, div._1AtVbE, div.DOjaWF, div._4ddWXP',
    "fields": [
        {"name": "title", "selector": "._4rR01T, .s1Q9rs, .IRpwTa, .KzDlHZ, .wjcEIp, .VU-ZEz, .WKTcLC, ._2WkVRV, a.geBtmU, div._2WkVRV", "type": "text", "optional": True},
        {"name": "price", "selector": "._30jeq3, ._1_WHN1, .Nx9bqj, ._4b7s3u, div._30jeq3._1_WHN1", "type": "text", "optional": True},
        {"name": "rating", "selector": "._3LWZlK, ._1lRcqv, div._3LWZlK", "type": "text", "optional": True},
        {"name": "url", "selector": 'a[href*="/p/"], a[href*="/product/"], a._1fQZEK, a.s1Q9rs, a.IRpwTa, a._2UzuFa, a.geBtmU', "type": "attribute", "attribute": "href", "optional": False}
    ]
}

# --- Platform Definitions ---
PLATFORMS = {
    "amazon": {
        "search_url_template": "https://www.amazon.in/s?k={query}",
        "base_url": "https://www.amazon.in",
        "schema": AMAZON_CSS_LISTING_SCHEMA
    },
    "flipkart": {
        "search_url_template": "https://www.flipkart.com/search?q={query}",
        "base_url": "https://www.flipkart.com",
        "schema": FLIPKART_CSS_LISTING_SCHEMA
    },
}

# --- LLM and Agent Configuration ---
LLM_EXTRACTION_INSTRUCTION = """
Extract credit card offers and the seller's name from this product page. Focus on offers like:
- "X% off with [BANK NAME] card"
- "₹X off with [BANK NAME] credit card"
- "Additional discount on [BANK NAME] cards"
Return the data in a clean JSON format.
"""

AGENT_ROLE = "E-commerce Discount Analyzer"
AGENT_GOAL = "Analyze product data with a user's credit card offers to find the best effective prices."
AGENT_BACKSTORY = "You are an expert in parsing e-commerce product information and calculating discounted prices based on available bank offers."

# --- Default scraping parameters ---
DEFAULT_USER_CARDS = ["HDFC Bank", "Axis Bank Credit Card", "SBI Card", "ICICI Credit Card"]
MAX_PRODUCTS_PER_PLATFORM = 3
MAX_DETAIL_PAGES_TO_SCRAPE = 6