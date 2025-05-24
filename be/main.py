import os
import asyncio
import json
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from dotenv import load_dotenv
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode, LLMConfig
from crawl4ai.extraction_strategy import JsonCssExtractionStrategy, LLMExtractionStrategy
from crewai import Agent, Task, Crew, Process
from langchain_ollama.llms import OllamaLLM
from crewai.tools import BaseTool
from crewai import LLM
import dotenv

dotenv.load_dotenv()

llm = LLM(
    model="gemini/gemini-2.0-flash",
    temperature=0.7,
)

class BasicDetails(BaseModel):
    description_summary: Optional[str] = None
    key_features: List[str] = []
    variant_info: Optional[str] = None
    seller_name: Optional[str] = None
    credit_card_offers: List[str] = []

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

amazon_css_listing_schema = {
    "name": "AmazonProductListing",
    "baseSelector": 'div[data-component-type="s-search-result"]',
    "fields": [
        {"name": "title", "selector": "h2 a span", "type": "text"},
        {"name": "price", "selector": "span.a-price span.a-offscreen", "type": "text"},
        {"name": "rating", "selector": "span[aria-label*='out of']", "type": "attribute", "attribute": "aria-label", "optional": True},
        {"name": "url", "selector": "h2 a.a-link-normal", "type": "attribute", "attribute": "href"},
        {"name": "seller_raw", "selector": "div.a-row.a-size-small span.a-color-secondary", "type": "text", "optional": True}
    ]
}

llm_extraction_instruction = """
Extract the following details from the provided product page content:
1. A concise summary of the product description (max 100 words).
2. A list of key features of the product (e.g., specifications, highlights).
3. Information about product variants (e.g., colors, sizes, storage options).
4. The primary seller's name if visible.
5. Any credit card-specific discounts or offers (e.g., "5% cashback with HDFC Bank card").
Return the output as a JSON object conforming to the BasicDetails schema.
If a field is not found, set it to null or an empty list as per the schema.
"""

class Crawl4AIScraperTool(BaseTool):
    name: str = "Crawl4AIScraper"
    description: str = "Scrapes web pages using Crawl4AI with CSS or LLM extraction. Returns JSON string."
    _crawler: AsyncWebCrawler = None
    _css_listing_schema: Dict = None
    _llm_strategy_detail_page: LLMExtractionStrategy = None

    def __init__(self, crawler: AsyncWebCrawler, css_listing_schema: Dict, llm_strategy_detail_page: LLMExtractionStrategy):
        super().__init__()
        self._crawler = crawler
        self._css_listing_schema = css_listing_schema
        self._llm_strategy_detail_page = llm_strategy_detail_page

    async def _run(self, url: str, strategy_type: str = "css_listing") -> str:
        try:
            if strategy_type == "css_listing":
                crawl_config = CrawlerRunConfig(
                    extraction_strategy=JsonCssExtractionStrategy(self._css_listing_schema, verbose=False),
                    session_id="amazon_product_session",
                    cache_mode=CacheMode.BYPASS,
                    exclude_external_links=True,
                    exclude_social_media_links=True
                )
                actual_url = url
            elif strategy_type == "llm_detail":
                crawl_config = CrawlerRunConfig(
                    cache_mode=CacheMode.BYPASS,
                    extraction_strategy=self._llm_strategy_detail_page,
                    session_id="amazon_product_session",
                )
                actual_url = url
            else:
                raise ValueError(f"Invalid strategy_type: {strategy_type}")
            result = await self._crawler.arun(url=actual_url, config=crawl_config)
            print(result)
            if result.success:
                return result.extracted_content
            else:
                return json.dumps({"error": result.error_message, "url": url})
        except Exception as e:
            return json.dumps({"error": str(e), "url": url})

async def scrape_amazon_products(product_query: str, max_products_to_collect: int = 10, user_credit_cards: List[str] = None):
    amazon_search_url = f"https://www.amazon.in/s?k={product_query.replace(' ', '+')}"
    load_dotenv()
    llm_config_crawl4ai = LLMConfig(provider="gemini/gemini-2.0-flash", api_token=os.getenv("GEMINI_API_KEY"))
    llm_crewai = llm
    llm_strategy_detail_page = LLMExtractionStrategy(
        llm_config=llm_config_crawl4ai,
        schema=BasicDetails.model_json_schema(),
        extraction_type="schema",
        instruction=llm_extraction_instruction,
        chunk_token_threshold=1500,
        apply_chunking=True,
        input_format="html",
        extra_args={"temperature": 0.1}
    )
    browser_config = BrowserConfig(headless=True, viewport_width=1280, viewport_height=720, verbose=False)
    async with AsyncWebCrawler(config=browser_config) as crawler:
        scraper_tool = Crawl4AIScraperTool(
            crawler=crawler,
            css_listing_schema=amazon_css_listing_schema,
            llm_strategy_detail_page=llm_strategy_detail_page
        )
        scraper_agent = Agent(
            role="Amazon Product Scraper",
            goal="Extract product listings and details from Amazon.in.",
            backstory="Expert in navigating Amazon's website and extracting data using Crawl4AI.",
            llm=llm_crewai,
            tools=[scraper_tool],
            async_execution=False,
            verbose=True,
            allow_delegation=False
        )
        discount_analyzer = Agent(
            role="Credit Card Discount Analyzer",
            goal="Apply credit card discounts and sort products by effective price.",
            backstory="Specialist in parsing e-commerce offers and calculating final prices.",
            llm=llm_crewai,
            async_execution=False,
            verbose=True,
            allow_delegation=False
        )
        scrape_search_results_task = Task(
            description=f"""
            Scrape Amazon search results for '{product_query}' using 'Crawl4AIScraperTool' with 'css_listing' strategy.
            Collect up to {max_products_to_collect} unique products from the first page.
            Ensure URLs are absolute (e.g., 'https://www.amazon.in/...').
            Return a JSON string of product dictionaries with 'title', 'price', 'rating', 'url', 'seller_raw'.
            """,
            agent=scraper_agent,
            async_execution=False,
            expected_output=f"JSON string of up to {max_products_to_collect} product dictionaries."
        )
        scrape_product_details_task = Task(
            description="""
            Given a JSON string of product listings, iterate through each product.
            Scrape details using 'Crawl4AIScraperTool' with 'llm_detail' strategy.
            Aggregate results into a JSON string of Product dictionaries, including 'basic_details' and 'seller'.
            Handle errors gracefully, skipping failed products.
            """,
            agent=scraper_agent,
            async_execution=False,
            expected_output="JSON string of Product dictionaries with full details."
        )
        discount_analysis_task = Task(
            description=f"""
            Parse the JSON string of product data. For each product:
            - Convert 'price' to 'original_price' (float), handling '₹' and commas.
            - Extract credit card offers from 'basic_details.credit_card_offers'.
            - Apply discounts if any offer matches {user_credit_cards}.
            - Set 'effective_price' and 'discount_applied' fields.
            - Sort by 'effective_price' (lowest to highest).
            Return a JSON string of sorted product dictionaries.
            """,
            agent=discount_analyzer,
            async_execution=False,
            expected_output="JSON string of sorted product dictionaries with discount details."
        )
        amazon_crew = Crew(
            agents=[scraper_agent, discount_analyzer],
            tasks=[scrape_search_results_task, scrape_product_details_task, discount_analysis_task],
            verbose=True,
            process=Process.sequential
        )
        crew_inputs = {
            'product_query': product_query,
            'url': amazon_search_url,
            'max_products_to_collect': max_products_to_collect,
            'user_credit_cards': json.dumps(user_credit_cards)
        }
        try:
            final_processed_results_json = await amazon_crew.kickoff(inputs=crew_inputs)
            final_processed_results = json.loads(final_processed_results_json)
        except Exception as e:
            final_processed_results = []
    return final_processed_results

async def main():
    product_to_search = "iphone 16"
    user_credit_cards = ["HDFC Bank", "Axis Bank Flipkart"]
    final_results = await scrape_amazon_products(
        product_to_search,
        max_products_to_collect=10,
        user_credit_cards=user_credit_cards
    )
    print("="*50)
    print(f"FINAL PROCESSED RESULTS for '{product_to_search}'")
    print("="*50)
    if final_results:
        for i, p in enumerate(final_results, 1):
            print(f"Product {i}:\n{json.dumps(p, indent=2)}")
    else:
        print("No processed products. Check scraping and CrewAI execution.")
    print(f"Total final processed products: {len(final_results)}")
    print("="*50)

if __name__ == "__main__":
    asyncio.run(main())