import asyncio
import json
import traceback
from typing import List, Optional, Dict, Any

from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, CacheMode, LLMExtractionStrategy, JsonCssExtractionStrategy
from crewai.tools import BaseTool

from models import ProductListing, BasicDetails
from utils import logger, safe_json_parse, normalize_url

class Crawl4AIScraperTool(BaseTool):
    """A CrewAI tool to scrape web pages using Crawl4AI with CSS or LLM strategies."""
    name: str = "Crawl4AIScraper"
    description: str = "Scrapes web pages using Crawl4AI for content extraction."
    _crawler: AsyncWebCrawler
    _css_schema: Optional[Dict] = None
    _llm_strategy: Optional[LLMExtractionStrategy] = None

    def __init__(self, crawler: AsyncWebCrawler, **kwargs):
        super().__init__(**kwargs)
        self._crawler = crawler
        # Strategies are now passed to _arun instead of being stored
    
    def _run(self, *args, **kwargs):
        """Sync wrapper for the async _arun method."""
        return asyncio.run(self._arun(*args, **kwargs))

    async def _arun(self, url: str, strategy: Any) -> str:
        """Asynchronously scrapes a URL using the provided extraction strategy."""
        if not isinstance(url, str) or not url.startswith(('http://', 'https://')):
            logger.error(f"Invalid URL provided: {url}")
            return json.dumps({"error": "Invalid URL format", "url": url})

        try:
            crawl_config = CrawlerRunConfig(
                extraction_strategy=strategy,
                cache_mode=CacheMode.BYPASS,
                wait_for="body",
                page_timeout=45000
            )
            result = await self._crawler.arun(url=url, config=crawl_config)
            
            if result.success:
                logger.debug(f"Successfully scraped {url}. Type: {type(result.extracted_content)}")
                return json.dumps(result.extracted_content) if isinstance(result.extracted_content, (dict, list)) else str(result.extracted_content)
            else:
                logger.error(f"Scraping failed for {url}: {result.error_message} (Status: {result.status_code})")
                return json.dumps({"error": result.error_message, "url": url, "status_code": result.status_code})
        except Exception as e:
            logger.error(f"Exception in Crawl4AIScraperTool for {url}: {e}\n{traceback.format_exc()}")
            return json.dumps({"error": str(e), "url": url})

async def fetch_product_listings(crawler: AsyncWebCrawler, platform_name: str, platform_info: Dict, query: str, max_products: int) -> List[ProductListing]:
    """Fetches and parses product listings from a single platform's search results page."""
    search_url = platform_info['search_url_template'].format(query=query.replace(' ', '+'))
    base_url = platform_info['base_url']
    schema = platform_info['schema']
    
    logger.info(f"Fetching listings from {platform_name.capitalize()}: {search_url}")
    
    strategy = JsonCssExtractionStrategy(schema, verbose=False)
    tool = Crawl4AIScraperTool(crawler=crawler)
    raw_data_str = await tool._arun(url=search_url, strategy=strategy)
    
    parsed_data = safe_json_parse(raw_data_str)
    
    if not isinstance(parsed_data, list) or "error" in parsed_data:
        logger.error(f"Failed to get listings from {platform_name}: {parsed_data.get('error', 'Unexpected format')}")
        return []
        
    listings = []
    for item in parsed_data:
        if len(listings) >= max_products:
            break
        if not isinstance(item, dict) or not item.get('title'):
            continue
        
        full_url = normalize_url(platform_name, base_url, item)
        if full_url:
            listings.append(ProductListing(
                title=item.get('title', 'N/A').strip(),
                price_str=item.get('price', 'N/A'),
                rating_str=item.get('rating'),
                url=full_url,
                platform=platform_name.capitalize()
            ))
            logger.info(f"Found listing: {item.get('title', 'N/A').strip()[:60]}...")
            
    return listings

async def fetch_product_details(crawler: AsyncWebCrawler, url: str, llm_strategy: LLMExtractionStrategy) -> Optional[BasicDetails]:
    """Fetches detailed information (e.g., offers) from a single product page using an LLM strategy."""
    logger.info(f"Fetching details from {url[:80]}...")
    if not llm_strategy:
        logger.warning("LLM strategy not available. Skipping detail extraction.")
        return BasicDetails()
        
    tool = Crawl4AIScraperTool(crawler=crawler)
    detail_result_str = await tool._arun(url=url, strategy=llm_strategy)
    parsed_output = safe_json_parse(detail_result_str)

    # The output might be a list containing a dict
    actual_details_dict = {}
    if isinstance(parsed_output, list) and parsed_output:
        actual_details_dict = parsed_output[0]
    elif isinstance(parsed_output, dict):
        actual_details_dict = parsed_output

    if "error" in actual_details_dict:
        logger.warning(f"LLM extraction error for {url}: {actual_details_dict.get('error')}")
        return BasicDetails() # Return default empty object

    try:
        return BasicDetails(**actual_details_dict)
    except Exception as e:
        logger.warning(f"Pydantic validation failed for BasicDetails from LLM output: {e}")
        return BasicDetails()