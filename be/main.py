# import os
# import asyncio
# import json
# import re
# import logging
# from pydantic import BaseModel, Field
# from typing import List, Optional, Dict, Any
# from dotenv import load_dotenv
# from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode, LLMConfig
# from crawl4ai.extraction_strategy import JsonCssExtractionStrategy, LLMExtractionStrategy
# from crewai import Agent, Task, Crew, Process
# from crewai.tools import BaseTool
# from crewai import LLM as CrewAILLM
# import traceback

# # Logger setup
# logger = logging.getLogger(__name__)
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# # Pydantic Models
# class BasicDetails(BaseModel):
#     description_summary: Optional[str] = None
#     key_features: List[str] = Field(default_factory=list)
#     variant_info: Optional[str] = None
#     seller_name: Optional[str] = None
#     credit_card_offers: List[str] = Field(default_factory=list)

# class Product(BaseModel):
#     title: str
#     price: str
#     rating: Optional[str] = None
#     seller: Optional[str] = None
#     url: str
#     platform: str
#     basic_details: Optional[str] = None
#     original_price: Optional[float] = None
#     effective_price: Optional[float] = None
#     discount_applied: Optional[str] = None

# class ProductOutput(BaseModel):
#     title: str
#     platform: str
#     price: str
#     original_price: float
#     effective_price: float
#     discount_applied: str
#     url: str
#     rating: Optional[str] = None
#     seller: Optional[str] = None

# # CSS Extraction Schemas
# amazon_css_listing_schema = {
#     "name": "AmazonProductListing",
#     "baseSelector": 'div[data-component-type="s-search-result"]',
#     "fields": [
#         {"name": "title", "selector": "h2 a span.a-text-normal, span.a-size-medium.a-color-base.a-text-normal, span.a-size-base-plus.a-color-base.a-text-normal", "type": "text", "optional": True},
#         {"name": "price", "selector": "span.a-price > span.a-offscreen, span.a-price-whole", "type": "text", "optional": True},
#         {"name": "rating", "selector": "span.a-icon-alt", "type": "text", "optional": True},
#         {"name": "url", "selector": 'h2 a.a-link-normal[href*="/dp/"], h2 a.s-link-style[href*="/dp/"], a.a-link-normal.s-underline-text[href*="/dp/"]', "type": "attribute", "attribute": "href", "optional": True},
#         {"name": "asin_direct", "selector": "", "type": "attribute", "attribute": "data-asin", "optional": True},
#     ]
# }

# flipkart_css_listing_schema = {
#     "name": "FlipkartProductListing",
#     "baseSelector": 'div[data-id], div._13oc-S, div.cPHDOP, div._1AtVbE, div.DOjaWF, div._4ddWXP',
#     "fields": [
#         {"name": "title", "selector": "._4rR01T, .s1Q9rs, .IRpwTa, .KzDlHZ, .wjcEIp, .VU-ZEz, .WKTcLC, ._2WkVRV, a.geBtmU, div._2WkVRV", "type": "text", "optional": True},
#         {"name": "price", "selector": "._30jeq3, ._1_WHN1, .Nx9bqj, ._4b7s3u, div._30jeq3._1_WHN1", "type": "text", "optional": True},
#         {"name": "rating", "selector": "._3LWZlK, ._1lRcqv, div._3LWZlK", "type": "text", "optional": True},
#         {"name": "url", "selector": 'a[href*="/p/"], a[href*="/product/"], a._1fQZEK, a.s1Q9rs, a.IRpwTa, a._2UzuFa, a.geBtmU', "type": "attribute", "attribute": "href", "optional": False}
#     ]
# }

# # Browser Configuration
# browser_config = BrowserConfig(
#     headless=True,
#     viewport_width=1920,
#     viewport_height=1080,
#     verbose=False,
#     user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
#     java_script_enabled=True,
# )

# # Crawl4AI Scraper Tool
# class Crawl4AIScraperTool(BaseTool):
#     name: str = "Crawl4AIScraper"
#     description: str = "Scrapes web pages using Crawl4AI with CSS or LLM extraction."
#     _crawler: AsyncWebCrawler
#     _css_schema: Optional[Dict]
#     _llm_strategy: Optional[LLMExtractionStrategy]

#     def __init__(self, crawler: AsyncWebCrawler, css_schema: Optional[Dict] = None, llm_strategy: Optional[LLMExtractionStrategy] = None, **kwargs):
#         super().__init__(**kwargs)
#         self._crawler = crawler
#         self._css_schema = css_schema
#         self._llm_strategy = llm_strategy

#     async def _arun(self, url: str, strategy_type: str = "css") -> str:
#         if not self._crawler:
#             logger.error("Crawler not initialized in Crawl4AIScraperTool.")
#             return json.dumps({"error": "Crawler not initialized", "url": url})

#         if not isinstance(url, str) or not url.startswith(('http://', 'https://')):
#             logger.error(f"Invalid URL provided to Crawl4AIScraperTool: {url}")
#             return json.dumps({"error": "Invalid URL format", "url": url})

#         logger.info(f"Scraping {url} with strategy: {strategy_type}")
#         try:
#             if strategy_type == "css":
#                 if not self._css_schema:
#                     logger.error("CSS schema is required for css strategy but not provided.")
#                     raise ValueError("CSS schema is required for css strategy")
#                 crawl_config = CrawlerRunConfig(
#                     extraction_strategy=JsonCssExtractionStrategy(self._css_schema, verbose=False),
#                     cache_mode=CacheMode.BYPASS, wait_for="body", page_timeout=30000
#                 )
#             elif strategy_type == "llm":
#                 if not self._llm_strategy:
#                     logger.error("LLM strategy is required for llm strategy but not provided.")
#                     raise ValueError("LLM strategy is required for llm strategy")
#                 crawl_config = CrawlerRunConfig(
#                     extraction_strategy=self._llm_strategy,
#                     cache_mode=CacheMode.BYPASS, session_id="detail_page_session",
#                     wait_for="body", page_timeout=45000
#                 )
#             else:
#                 raise ValueError(f"Invalid strategy_type: {strategy_type}")

#             result = await self._crawler.arun(url=url, config=crawl_config)
#             if result.success:
#                 logger.debug(f"Successfully scraped {url}. Extracted content type: {type(result.extracted_content)}")
#                 if isinstance(result.extracted_content, (dict, list)):
#                     return json.dumps(result.extracted_content)
#                 return str(result.extracted_content)
#             else:
#                 logger.error(f"Scraping failed for {url}: {result.error_message} (Status: {result.status_code})")
#                 return json.dumps({"error": result.error_message, "url": url, "status_code": result.status_code})
#         except Exception as e:
#             logger.error(f"Error in Crawl4AIScraperTool for {url} (strategy: {strategy_type}): {str(e)}")
#             logger.error(traceback.format_exc())
#             return json.dumps({"error": str(e), "url": url})

#     def _run(self, url: str, strategy_type: str = "css") -> str:
#         try:
#             loop = asyncio.get_event_loop()
#             if loop.is_running():
#                 future = asyncio.ensure_future(self._arun(url, strategy_type))
#                 result = loop.run_until_complete(future)
#             else:
#                 result = asyncio.run(self._arun(url, strategy_type))
#             return result
#         except Exception as e:
#             logger.error(f"Error in Crawl4AIScraperTool sync _run for {url}: {str(e)}")
#             return json.dumps({"error": str(e), "url": url})

# # Helper Functions
# def parse_price(price_str: Any) -> Optional[float]:
#     if not price_str:
#         return None
#     try:
#         clean_price = re.sub(r'[₹,]', '', str(price_str))
#         price_match = re.search(r'(\d+\.?\d*)', clean_price)
#         if price_match:
#             return float(price_match.group(1))
#         return None
#     except (ValueError, AttributeError, TypeError) as e:
#         logger.warning(f"Could not parse price: '{price_str}'. Error: {e}")
#         return None

# def safe_json_parse(json_str: str) -> Any:
#     if not isinstance(json_str, str):
#         logger.warning(f"safe_json_parse expected a string, got {type(json_str)}. Returning error dict.")
#         return {"error": f"Invalid input type to safe_json_parse: {type(json_str)}"}
#     try:
#         return json.loads(json_str)
#     except json.JSONDecodeError as e:
#         logger.warning(f"Could not parse JSON: {e}. Returning error dict.")
#         return {"error": f"JSONDecodeError: {str(e)}"}

# # Fallback discount calculation (when LLM fails)
# def calculate_discount_fallback(products: List[Product], user_credit_cards: List[str]) -> List[Dict]:
#     """Fallback method to calculate discounts when LLM extraction fails"""
#     results = []
    
#     for product in products:
#         original_price = product.original_price or parse_price(product.price)
#         if not original_price:
#             continue
            
#         effective_price = original_price
#         discount_applied = "None"
        
#         # Try to extract offers from basic_details if available
#         try:
#             if product.basic_details:
#                 details = json.loads(product.basic_details)
#                 offers = details.get('credit_card_offers', [])
                
#                 best_discount = 0
#                 best_offer = None
                
#                 for offer in offers:
#                     # Check if any user card matches this offer
#                     for card in user_credit_cards:
#                         card_name = card.lower().replace(' ', '')
#                         if any(part in offer.lower() for part in card_name.split()):
#                             # Extract discount amount
#                             percentage_match = re.search(r'(\d+)%', offer)
#                             amount_match = re.search(r'₹(\d+)', offer)
                            
#                             discount_value = 0
#                             if percentage_match:
#                                 discount_value = float(percentage_match.group(1))
#                                 calculated_discount = original_price * (discount_value / 100)
#                             elif amount_match:
#                                 calculated_discount = float(amount_match.group(1))
#                                 discount_value = (calculated_discount / original_price) * 100
#                             else:
#                                 continue
                                
#                             if calculated_discount > best_discount:
#                                 best_discount = calculated_discount
#                                 best_offer = offer
                
#                 if best_discount > 0:
#                     effective_price = original_price - best_discount
#                     discount_applied = best_offer
                    
#         except Exception as e:
#             logger.warning(f"Error processing discount for {product.title}: {e}")
        
#         results.append({
#             "title": product.title,
#             "platform": product.platform,
#             "price": product.price,
#             "original_price": original_price,
#             "effective_price": effective_price,
#             "discount_applied": discount_applied,
#             "url": product.url,
#             "rating": product.rating,
#             "seller": product.seller
#         })
    
#     # Sort by effective price
#     results.sort(key=lambda x: x['effective_price'])
#     return results

# # Main Scraping Function
# async def scrape_products(product_query: str = "iPhone 15 128GB", user_credit_cards: List[str] = None, max_products_per_platform: int = 3, max_detail_pages: int = 6):
#     if user_credit_cards is None:
#         user_credit_cards = ["HDFC Bank", "Axis Bank Credit Card", "SBI Card", "ICICI Credit Card"]

#     load_dotenv()
#     gemini_api_key = os.getenv("GEMINI_API_KEY")
#     anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
#     openai_api_key = os.getenv("OPENAI_API_KEY")
#     if not gemini_api_key:
#         logger.error("GEMINI_API_KEY not found in environment variables.")
#         return []
#     if not anthropic_api_key:
#         logger.error("ANTHROPIC_API_KEY not found in environment variables.")
#         return []
#     if not openai_api_key:
#         logger.error("OPENAI_API_KEY not found in environment variables.")
#         return []

#     platforms = {
#         "amazon": {
#             "search_url": f"https://www.amazon.in/s?k={product_query.replace(' ', '+')}",
#             "base_url": "https://www.amazon.in",
#             "schema": amazon_css_listing_schema
#         },
#         "flipkart": {
#             "search_url": f"https://www.flipkart.com/search?q={product_query.replace(' ', '%20')}",
#             "base_url": "https://www.flipkart.com",
#             "schema": flipkart_css_listing_schema
#         },
#     }

#     # Initialize LLM components with better error handling
#     llm_config_crawl4ai = None
#     llm_strategy_detail_page = None
    
#     try:
#         llm_config_crawl4ai = LLMConfig(provider="gemini/gemini-2.0-flash-lite", api_token=gemini_api_key)
        
#         llm_extraction_instruction = """
#         Extract credit card offers from this product page. Look for offers like:
#         - "X% off with [BANK NAME] card"
#         - "₹X off with [BANK NAME] credit card"
#         - "Additional discount on [BANK NAME] cards"
        
#         Return JSON with: {"credit_card_offers": ["offer1", "offer2"], "seller_name": "seller"}
#         """
        
#         llm_strategy_detail_page = LLMExtractionStrategy(
#             llm_config=llm_config_crawl4ai,     
#             schema=BasicDetails.model_json_schema(), 
#             extraction_type="schema",
#             instruction=llm_extraction_instruction, 
#             chunk_token_threshold=50000, 
#             apply_chunking=True,
#             input_format="html", 
#             verbose=False
#         )
#     except Exception as e:
#         logger.warning(f"Failed to initialize LLM components: {e}. Will use fallback method.")

#     initial_product_listings = []
#     async with AsyncWebCrawler(config=browser_config) as crawler:
#         for platform_name, info in platforms.items():
#             search_url, base_url, schema = info['search_url'], info['base_url'], info['schema']
#             css_scraper_tool = Crawl4AIScraperTool(crawler=crawler, css_schema=schema)
#             logger.info(f"Fetching listings from {platform_name}: {search_url}")
            
#             try:
#                 raw_listing_data_str = await css_scraper_tool._arun(url=search_url, strategy_type="css")
#                 listings_data_parsed = safe_json_parse(raw_listing_data_str)
                
#                 if isinstance(listings_data_parsed, dict) and "error" in listings_data_parsed:
#                     logger.error(f"Failed to get listings from {platform_name}: {listings_data_parsed['error']}")
#                     continue
                    
#                 if not isinstance(listings_data_parsed, list):
#                     logger.error(f"Expected list from {platform_name} listings, got {type(listings_data_parsed)}")
#                     continue
                    
#                 logger.info(f"Found {len(listings_data_parsed)} raw items from {platform_name}.")
                
#                 count = 0
#                 for item_raw in listings_data_parsed:
#                     if count >= max_products_per_platform:
#                         break
#                     if not isinstance(item_raw, dict):
#                         continue
                        
#                     product_title = item_raw.get('title', "").strip()
#                     full_url = None
                    
#                     if platform_name == "amazon":
#                         scraped_url_path, direct_asin = item_raw.get('url'), item_raw.get('asin_direct')
#                         final_asin = None
                        
#                         if scraped_url_path:
#                             relative_url = str(scraped_url_path).strip()
#                             full_url = (base_url + relative_url) if not relative_url.startswith(('http', '/')) else (base_url + relative_url if relative_url.startswith('/') else relative_url)
#                             asin_match = re.search(r'/dp/([A-Z0-9]{10})', full_url)
#                             if asin_match:
#                                 final_asin = asin_match.group(1)
                                
#                         if direct_asin and (not final_asin or final_asin != direct_asin):
#                             final_asin = str(direct_asin).strip() if not final_asin else final_asin
                            
#                         if final_asin:
#                             full_url = f"{base_url}/dp/{final_asin.strip()}"
                            
#                         if not product_title:
#                             product_title = f"Amazon Product ASIN: {final_asin}"
#                     else:
#                         scraped_url = item_raw.get('url')
#                         if not product_title and not scraped_url:
#                             continue
                            
#                         if not product_title:
#                             product_title = f"{platform_name.capitalize()} Product (Title unknown)"
                            
#                         if scraped_url:
#                             relative_url = str(scraped_url).strip()
#                             full_url = (base_url + relative_url) if not relative_url.startswith(('http', '/')) else (base_url + relative_url if relative_url.startswith('/') else relative_url)
                    
#                     if full_url and product_title:
#                         initial_product_listings.append({
#                             'title': product_title,
#                             'price_str': item_raw.get('price', ''),
#                             'rating_str': item_raw.get('rating'),
#                             'url': full_url,
#                             'platform': platform_name.capitalize()
#                         })
#                         count += 1
#                         logger.info(f"Added: {product_title[:60]}... from {platform_name}")
                        
#             except Exception as e:
#                 logger.error(f"Error scraping {platform_name}: {e}")
#                 continue

#     if not initial_product_listings:
#         logger.warning("No initial product listings found")
#         return []

#     all_products_for_analysis = []
    
#     # Process detail pages with better error handling
#     for listing_item in initial_product_listings[:min(len(initial_product_listings), max_detail_pages)]:
#         logger.info(f"Processing: {listing_item['title'][:60]}...")
        
#         validated_basic_details = BasicDetails()
        
#         # Try LLM extraction if available
#         if llm_strategy_detail_page:
#             try:
#                 async with AsyncWebCrawler(config=browser_config) as detail_crawler:
#                     detail_scraper_tool = Crawl4AIScraperTool(crawler=detail_crawler, llm_strategy=llm_strategy_detail_page)
#                     detail_result_str = await detail_scraper_tool._arun(url=listing_item['url'], strategy_type="llm")
#                     logger.info(f"LLM extraction result: {detail_result_str}")
#                     parsed_llm_output = safe_json_parse(detail_result_str)
                    
#                     actual_details_dict = {}
#                     if isinstance(parsed_llm_output, list) and parsed_llm_output and isinstance(parsed_llm_output[0], dict):
#                         actual_details_dict = parsed_llm_output[0]
#                     elif isinstance(parsed_llm_output, dict):
#                         actual_details_dict = parsed_llm_output
                    
#                     if not (isinstance(actual_details_dict, dict) and actual_details_dict.get("error")):
#                         try:
#                             validated_basic_details = BasicDetails(**actual_details_dict)
#                             logger.info(f"Successfully extracted details for: {listing_item['title'][:60]}")
#                         except Exception as e_val:
#                             logger.warning(f"Pydantic validation failed for BasicDetails: {e_val}")
#                     else:
#                         logger.warning(f"LLM extraction error for {listing_item['url']}: {actual_details_dict.get('error')}")
                        
#             except Exception as e:
#                 logger.warning(f"Failed to extract details for {listing_item['url']}: {e}")
        
#         all_products_for_analysis.append(Product(
#             title=listing_item['title'],
#             price=listing_item.get('price_str', 'N/A'),
#             rating=listing_item.get('rating_str'),
#             seller=validated_basic_details.seller_name,
#             url=listing_item['url'],
#             platform=listing_item['platform'],
#             basic_details=validated_basic_details.model_dump_json(),
#             original_price=parse_price(listing_item.get('price_str'))
#         ))
        
#         # Add delay to avoid rate limits
#         await asyncio.sleep(10)

#     if not all_products_for_analysis:
#         logger.warning("No products processed for analysis")
#         return []

#     # Try CrewAI analysis, fallback to manual calculation
#     final_results = []
    
#     try:
#         llm_crew = CrewAILLM(model="gemini/gemini-2.0-flash-lite", api_key=gemini_api_key, temperature=0.1)
#         # llm_crew = CrewAILLM(model="anthropic/claude-3-sonnet", api_key=anthropic_api_key, temperature=0.1)
#         processor_agent = Agent(
#             role="E-commerce Discount Analyzer",
#             goal="Analyze product data with user's credit card offers to find the best effective prices.",
#             backstory="Expert in parsing e-commerce product information and calculating discount prices.",
#             llm=llm_crew,
#             verbose=True,
#             allow_delegation=False
#         )
        
#         all_products_input_str = json.dumps([p.model_dump(exclude_none=True) for p in all_products_for_analysis])
        
#         discount_task = Task(
#             description=f"""
#             Analyze this product list: {all_products_input_str}
#             User's credit cards: {json.dumps(user_credit_cards)}
            
#             Calculate effective prices considering credit card offers and return top 10 products sorted by effective price.
#             Return as JSON array with fields: title, platform, price, original_price, effective_price, discount_applied, url, rating, seller.
#             """,
#             agent=processor_agent,
#             expected_output="JSON array of products with discount analysis"
#         )
        
#         crew = Crew(agents=[processor_agent], tasks=[discount_task], verbose=True, process=Process.sequential)
#         logger.info(f"Starting CrewAI analysis with {len(all_products_for_analysis)} products.")
        
#         result = crew.kickoff()
        
#         # Try to parse CrewAI output
#         if hasattr(result, 'raw') and result.raw:
#             try:
#                 final_results = json.loads(result.raw)
#                 if not isinstance(final_results, list):
#                     raise ValueError("Expected list from CrewAI")
#                 logger.info(f"CrewAI successfully processed {len(final_results)} products")
#             except Exception as e:
#                 logger.warning(f"Failed to parse CrewAI output: {e}")
#                 final_results = []
        
#     except Exception as e:
#         logger.warning(f"CrewAI execution failed: {e}")
#         final_results = []

#     # Fallback to manual calculation if CrewAI fails
#     if not final_results:
#         logger.info("Using fallback discount calculation method")
#         final_results = calculate_discount_fallback(all_products_for_analysis, user_credit_cards)

#     # Display results
#     logger.info("=" * 50 + f"\nFINAL RESULTS for '{product_query}' (Top {min(len(final_results), 10)})\n" + "=" * 50)
    
#     if final_results and isinstance(final_results, list):
#         for i, p in enumerate(final_results[:10], 1):
#             if isinstance(p, dict):
#                 price_str = f"₹{p.get('effective_price'):,.2f}" if isinstance(p.get('effective_price'), (int, float)) else str(p.get('effective_price'))
#                 logger.info(f"Product {i}: {p.get('title', 'N/A')[:60]} ({p.get('platform', 'N/A')})")
#                 logger.info(f" Original: {p.get('price', 'N/A')} → Effective: {price_str}")
#                 logger.info(f" Discount: {p.get('discount_applied', 'None')}")
#                 logger.info(f" URL: {p.get('url', 'N/A')}")
#                 logger.info("-" * 50)
#     else:
#         logger.warning("No final results available")

#     logger.info(f"Total results: {len(final_results) if isinstance(final_results, list) else 0}\n" + "=" * 50)
#     return final_results if isinstance(final_results, list) else []

# async def test_system():
#     load_dotenv()
#     product_query = "iPhone 15 128GB"
#     my_cards = ["HDFC Bank", "Axis Bank Credit Card", "SBI Card", "ICICI Credit Card", "Flipkart Axis Bank Credit Card"]
    
#     logger.info(f"Testing system with query: '{product_query}', Cards: {my_cards}")
    
#     try:
#         results = await scrape_products(
#             product_query, 
#             my_cards, 
#             max_products_per_platform=2, 
#             max_detail_pages=4
#         )
#         logger.info(f"Test completed. Processed {len(results)} products.")
#         return results
#     except Exception as e:
#         logger.error(f"Test system failed: {e}")
#         logger.error(traceback.format_exc())
#         return []

# if __name__ == "__main__":
#     final_test_results = asyncio.run(test_system())
    
#     print("\n" + "="*60)
#     print("FINAL TEST RESULTS")
#     print("="*60)
    
#     if final_test_results:
#         for i, product in enumerate(final_test_results[:5], 1):
#             eff_price = product.get('effective_price', 'N/A')
#             price_display = f"₹{eff_price:,.2f}" if isinstance(eff_price, (float, int)) else str(eff_price)
            
#             print(f"\n{i}. {product.get('title', 'N/A')[:60]}")
#             print(f"   Platform: {product.get('platform', 'N/A')}")
#             print(f"   Original Price: {product.get('price', 'N/A')}")
#             print(f"   Effective Price: {price_display}")
#             print(f"   Discount: {product.get('discount_applied', 'None')}")
#             print(f"   Rating: {product.get('rating', 'N/A')}")
#             print(f"   URL: {product.get('url', 'N/A')[:80]}...")
#     else:
#         print("No products found or processed successfully.")
    
#     print(f"\nTotal products processed: {len(final_test_results)}")
#     print("="*60)

# main.py

import asyncio
import traceback
from urllib.parse import quote

from crawl4ai import AsyncWebCrawler, LLMConfig, LLMExtractionStrategy

import config
import utils
from models import Product, BasicDetails
from scraping import fetch_product_listings, fetch_product_details
from analysis import analyze_discounts_with_crewai, calculate_discount_fallback

logger = utils.setup_logging()

async def run_product_search_pipeline(
    product_query: str, 
    user_credit_cards: list = None, 
    max_listings: int = config.MAX_PRODUCTS_PER_PLATFORM,
    max_details: int = config.MAX_DETAIL_PAGES_TO_SCRAPE
):
    """Orchestrates the end-to-end product search and analysis pipeline."""
    user_credit_cards = user_credit_cards or config.DEFAULT_USER_CARDS
    
    try:
        api_keys = utils.load_api_keys()
    except ValueError as e:
        logger.error(e)
        return []

    # --- 1. Initialize LLM Strategy for Detail Pages ---
    llm_strategy_detail_page = None
    try:
        llm_config = LLMConfig(provider="gemini/gemini-2.0-flash-lite", api_token=api_keys["gemini"])
        llm_strategy_detail_page = LLMExtractionStrategy(
            llm_config=llm_config,
            schema=BasicDetails.model_json_schema(),
            extraction_type="schema",
            instruction=config.LLM_EXTRACTION_INSTRUCTION,
            apply_chunking=True,
            chunk_token_threshold=50000,
        )
    except Exception as e:
        logger.warning(f"Failed to initialize LLM strategy: {e}. Detail extraction will be limited.")

    # --- 2. Scrape Initial Product Listings ---
    initial_listings = []
    async with AsyncWebCrawler(config=config.BROWSER_CONFIG) as crawler:
        listing_tasks = [
            fetch_product_listings(crawler, name, info, quote(product_query), max_listings)
            for name, info in config.PLATFORMS.items()
        ]
        results = await asyncio.gather(*listing_tasks)
        for res in results:
            initial_listings.extend(res)

    if not initial_listings:
        logger.warning("No product listings found across any platform.")
        return []

    # --- 3. Scrape Product Detail Pages ---
    products_for_analysis = []
    detail_pages_to_scrape = initial_listings[:min(len(initial_listings), max_details)]
    
    async with AsyncWebCrawler(config=config.BROWSER_CONFIG) as detail_crawler:
        for listing in detail_pages_to_scrape:
            details = await fetch_product_details(detail_crawler, listing.url, llm_strategy_detail_page)
            
            products_for_analysis.append(Product(
                title=listing.title,
                price=listing.price_str,
                rating=listing.rating_str,
                seller=details.seller_name,
                url=listing.url,
                platform=listing.platform,
                basic_details=details.model_dump_json(),
                original_price=utils.parse_price(listing.price_str)
            ))
            await asyncio.sleep(2) # Be a good citizen

    # --- 4. Analyze Data and Calculate Discounts ---
    final_results = analyze_discounts_with_crewai(products_for_analysis, user_credit_cards, api_keys["gemini"])
    
    if not final_results:
        logger.info("CrewAI analysis failed or returned no results. Using fallback calculation.")
        final_results = calculate_discount_fallback(products_for_analysis, user_credit_cards)

    # --- 5. Display Results ---
    utils.display_final_results(final_results, product_query)
    
    return final_results


if __name__ == "__main__":
    product_to_find = "iPhone 16"
    my_cards = ["HDFC Bank", "Axis Bank", "Flipkart Axis Bank Credit Card"]
    
    logger.info(f"Starting product search for: '{product_to_find}'")
    
    try:
        final_data = asyncio.run(run_product_search_pipeline(product_to_find, my_cards))
        logger.info(f"Pipeline finished. Found and processed {len(final_data)} products.")
    except Exception as e:
        logger.error(f"An unhandled error occurred in the main pipeline: {e}")
        logger.error(traceback.format_exc())