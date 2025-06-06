import logging
import json
import re
import os
from typing import Any, Optional, Dict
from dotenv import load_dotenv

def setup_logging():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    return logging.getLogger(__name__)

logger = setup_logging()

def load_api_keys() -> Dict[str, str]:
    load_dotenv()
    return {
        "gemini": os.getenv("GEMINI_API_KEY"),
        "anthropic": os.getenv("ANTHROPIC_API_KEY"),
        "openai": os.getenv("OPENAI_API_KEY"),
    }

def parse_price(price_str: Any) -> Optional[float]:
    if not price_str:
        return None
    try:
        clean_price = re.sub(r'[₹,]', '', str(price_str))
        price_match = re.search(r'(\d+\.?\d*)', clean_price)
        return float(price_match.group(1)) if price_match else None
    except (ValueError, AttributeError, TypeError) as e:
        logger.warning(f"Could not parse price: '{price_str}'. Error: {e}")
        return None

def safe_json_parse(json_str: str) -> Any:
    if not isinstance(json_str, str):
        return {"error": f"Invalid input type, expected string, got {type(json_str)}"}
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        logger.warning(f"JSONDecodeError: {e}. String was: '{json_str[:100]}...'")
        return {"error": f"JSONDecodeError: {e}"}

def normalize_url(platform_name: str, base_url: str, item_data: Dict) -> Optional[str]:
    scraped_url = item_data.get('url')
    full_url = None

    if platform_name == "amazon":
        direct_asin = item_data.get('asin_direct')
        final_asin = None
        if scraped_url:
            asin_match = re.search(r'/dp/([A-Z0-9]{10})', str(scraped_url))
            if asin_match:
                final_asin = asin_match.group(1)
        if direct_asin:
            final_asin = str(direct_asin).strip()
        if final_asin:
            full_url = f"{base_url}/dp/{final_asin}"
    elif scraped_url:
        relative_url = str(scraped_url).strip()
        if not relative_url.startswith('http'):
            full_url = base_url + relative_url
        else:
            full_url = relative_url
            
    return full_url

def display_final_results(results: list, query: str):
    logger.info("=" * 50 + f"\nFINAL RESULTS for '{query}' (Top {min(len(results), 10)})\n" + "=" * 50)
    if not results:
        logger.warning("No final results available to display.")
        return

    for i, p in enumerate(results[:10], 1):
        if isinstance(p, dict):
            price_str = f"₹{p.get('effective_price'):,.2f}" if isinstance(p.get('effective_price'), (int, float)) else "N/A"
            logger.info(f"Product {i}: {p.get('title', 'N/A')[:60]} ({p.get('platform', 'N/A')})")
            logger.info(f"  Original: {p.get('price', 'N/A')} -> Effective: {price_str}")
            logger.info(f"  Discount: {p.get('discount_applied', 'None')}")
            logger.info(f"  URL: {p.get('url', 'N/A')}")
            logger.info("-" * 50)