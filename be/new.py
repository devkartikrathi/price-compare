#!/usr/bin/env python3
"""
CrewAI E-commerce Product Scraper
A robust multi-agent system for scraping product information from various e-commerce platforms
"""

import os
import json
import logging
import asyncio
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
import re
from dotenv import load_dotenv
load_dotenv()

from typing import Dict, List, Any, Optional

# Core CrewAI imports
from crewai import Agent, Task, Crew, Process, LLM
from crewai.tools import BaseTool

# Additional imports for web scraping
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Try to import optional dependencies
try:
    import firecrawl
    FIRECRAWL_AVAILABLE = True
except ImportError:
    logger.warning("Firecrawl not available. Install with: pip install firecrawl-py")
    FIRECRAWL_AVAILABLE = False

try:
    from fake_useragent import UserAgent
    UA_AVAILABLE = True
except ImportError:
    logger.warning("fake-useragent not available. Install with: pip install fake-useragent")
    UA_AVAILABLE = False

try:
    from crewai_tools import SerperDevTool
    SERPER_AVAILABLE = True
except ImportError:
    logger.warning("SerperDevTool not available. Web search functionality limited.")
    SERPER_AVAILABLE = False

@dataclass
class ProductInfo:
    """Data class for product information"""
    name: str
    price: str
    original_price: str = ""
    discount: str = ""
    offers: List[str] = field(default_factory=list)
    rating: str = ""
    reviews_count: str = ""
    availability: str = ""
    image_url: str = ""
    product_url: str = ""
    platform: str = ""
    description: str = ""

class FirecrawlScrapingTool(BaseTool):
    """Custom tool for scraping using Firecrawl API"""
    name: str = "firecrawl_scrapper"
    description: str = "Scrape web pages using Firecrawl API for clean, structured data extraction"
    client: Optional[Any] = None 
    
    def __init__(self, api_key: str = None):
        super().__init__()
        self._api_key = api_key or os.getenv('FIRECRAWL_API_KEY')
        if self._api_key and FIRECRAWL_AVAILABLE:
            self.client = firecrawl.FirecrawlApp(api_key=self._api_key)
        else:
            self.client = None
            if not FIRECRAWL_AVAILABLE:
                logger.warning("Firecrawl library not available. Using fallback scraping methods.")
            else:
                logger.warning("Firecrawl API key not provided. Using fallback scraping methods.")
    
    def _run(self, url: str, extract_schema: Dict = None) -> str:
        """Execute the scraping operation"""
        try:
            if self.client:
                # Use Firecrawl for better scraping
                params = {
                    'formats': ['markdown', 'html'],
                    'waitFor': 3000,
                    'timeout': 30000
                }
                
                if extract_schema:
                    params['extract'] = {'schema': extract_schema}
                
                result = self.client.scrape_url(url, params=params)
                
                if result.get('success'):
                    return json.dumps({
                        'url': url,
                        'content': result.get('markdown', ''),
                        'html': result.get('html', ''),
                        'extracted_data': result.get('extract', {}),
                        'metadata': result.get('metadata', {})
                    })
                else:
                    logger.error(f"Firecrawl scraping failed: {result.get('error')}")
                    return self._fallback_scrape(url)
            else:
                return self._fallback_scrape(url)
                
        except Exception as e:
            logger.error(f"Error scraping {url}: {str(e)}")
            return self._fallback_scrape(url)
    
    def _fallback_scrape(self, url: str) -> str:
        """Fallback scraping method using requests and BeautifulSoup"""
        try:
            if UA_AVAILABLE:
                ua = UserAgent()
                user_agent = ua.random
            else:
                user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            
            headers = {
                'User-Agent': user_agent,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
            }
            
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()
            
            text = soup.get_text()
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = ' '.join(chunk for chunk in chunks if chunk)
            
            return json.dumps({
                'url': url,
                'content': text[:5000],  # Limit content size
                'html': str(soup)[:10000],
                'title': soup.title.string if soup.title else '',
                'metadata': {'scraped_at': datetime.now().isoformat()}
            })
            
        except Exception as e:
            logger.error(f"Fallback scraping failed for {url}: {str(e)}")
            return json.dumps({'url': url, 'error': str(e), 'content': ''})

class EcommerceSearchTool(BaseTool):
    """Tool for searching products on e-commerce platforms"""
    name: str = "ecommerce_search"
    description: str = "Search for products on various e-commerce platforms and return search result URLs"
    
    def _run(self, product_name: str, platforms: List[str] = None) -> str:
        """Search for products across platforms"""
        if platforms is None:
            platforms = ['amazon', 'flipkart', 'blinkit', 'zepto']
        
        search_urls = []
        
        platform_configs = {
            'amazon': {
                'base_url': 'https://www.amazon.in/s?k=',
                'search_pattern': lambda query: f"https://www.amazon.in/s?k={query.replace(' ', '+')}"
            },
            'flipkart': {
                'base_url': 'https://www.flipkart.com/search?q=',
                'search_pattern': lambda query: f"https://www.flipkart.com/search?q={query.replace(' ', '%20')}"
            },
            'blinkit': {
                'base_url': 'https://blinkit.com/s/?q=',
                'search_pattern': lambda query: f"https://blinkit.com/s/?q={query.replace(' ', '%20')}"
            },
            'zepto': {
                'base_url': 'https://www.zepto.com/search?query=',
                'search_pattern': lambda query: f"https://www.zepto.com/search?query={query.replace(' ', '%20')}"
            }
        }
        
        for platform in platforms:
            if platform.lower() in platform_configs:
                config = platform_configs[platform.lower()]
                search_url = config['search_pattern'](product_name)
                search_urls.append({
                    'platform': platform,
                    'search_url': search_url
                })
        
        return json.dumps({
            'product_name': product_name,
            'search_urls': search_urls,
            'total_platforms': len(search_urls)
        })

class ProductParser:
    """Parse product information from scraped content"""
    
    @staticmethod
    def parse_amazon_product(content: str, url: str) -> ProductInfo:
        """Parse Amazon product information"""
        try:
            # Extract product name
            name_patterns = [
                r'<span[^>]*id="productTitle"[^>]*>([^<]+)</span>',
                r'"title":"([^"]+)"',
                r'<title>([^<]+)</title>'
            ]
            name = ProductParser._extract_with_patterns(content, name_patterns)
            
            # Extract price
            price_patterns = [
                r'<span[^>]*class="[^"]*a-price-whole[^"]*"[^>]*>([^<]+)</span>',
                r'"price":"([^"]+)"',
                r'₹([0-9,]+)'
            ]
            price = ProductParser._extract_with_patterns(content, price_patterns)
            
            # Extract original price
            original_price_patterns = [
                r'<span[^>]*class="[^"]*a-text-price[^"]*"[^>]*>.*?₹([0-9,]+)',
                r'"listPrice":"([^"]+)"'
            ]
            original_price = ProductParser._extract_with_patterns(content, original_price_patterns)
            
            # Extract offers
            offers = ProductParser._extract_offers_amazon(content)
            
            # Extract rating
            rating_patterns = [
                r'<span[^>]*class="[^"]*a-size-base[^"]*"[^>]*>([0-9.]+) out of 5',
                r'"rating":"([^"]+)"'
            ]
            rating = ProductParser._extract_with_patterns(content, rating_patterns)
            
            return ProductInfo(
                name=name or "Product name not found",
                price=f"₹{price}" if price else "Price not found",
                original_price=f"₹{original_price}" if original_price else "",
                offers=offers,
                rating=rating,
                product_url=url,
                platform="Amazon"
            )
            
        except Exception as e:
            logger.error(f"Error parsing Amazon product: {str(e)}")
            return ProductInfo(name="Parse Error", price="N/A", product_url=url, platform="Amazon")
    
    @staticmethod
    def parse_flipkart_product(content: str, url: str) -> ProductInfo:
        """Parse Flipkart product information"""
        try:
            # Extract product name
            name_patterns = [
                r'<span[^>]*class="[^"]*B_NuCI[^"]*"[^>]*>([^<]+)</span>',
                r'"name":"([^"]+)"',
                r'<h1[^>]*>([^<]+)</h1>'
            ]
            name = ProductParser._extract_with_patterns(content, name_patterns)
            
            # Extract price
            price_patterns = [
                r'<div[^>]*class="[^"]*_30jeq3[^"]*"[^>]*>₹([0-9,]+)',
                r'"price":"([^"]+)"'
            ]
            price = ProductParser._extract_with_patterns(content, price_patterns)
            
            # Extract offers
            offers = ProductParser._extract_offers_flipkart(content)
            
            return ProductInfo(
                name=name or "Product name not found",
                price=f"₹{price}" if price else "Price not found",
                offers=offers,
                product_url=url,
                platform="Flipkart"
            )
            
        except Exception as e:
            logger.error(f"Error parsing Flipkart product: {str(e)}")
            return ProductInfo(name="Parse Error", price="N/A", product_url=url, platform="Flipkart")
    
    @staticmethod
    def parse_blinkit_product(content: str, url: str) -> ProductInfo:
        """Parse Blinkit product information"""
        try:
            name_patterns = [
                r'"name":"([^"]+)"',
                r'<h1[^>]*>([^<]+)</h1>',
                r'<title>([^<]+)</title>'
            ]
            name = ProductParser._extract_with_patterns(content, name_patterns)
            
            price_patterns = [
                r'₹([0-9,]+)',
                r'"price":"([^"]+)"'
            ]
            price = ProductParser._extract_with_patterns(content, price_patterns)
            
            offers = ProductParser._extract_offers_generic(content)
            
            return ProductInfo(
                name=name or "Product name not found",
                price=f"₹{price}" if price else "Price not found",
                offers=offers,
                product_url=url,
                platform="Blinkit"
            )
            
        except Exception as e:
            logger.error(f"Error parsing Blinkit product: {str(e)}")
            return ProductInfo(name="Parse Error", price="N/A", product_url=url, platform="Blinkit")
    
    @staticmethod
    def parse_zepto_product(content: str, url: str) -> ProductInfo:
        """Parse Zepto product information"""
        try:
            name_patterns = [
                r'"name":"([^"]+)"',
                r'<h1[^>]*>([^<]+)</h1>',
                r'<title>([^<]+)</title>'
            ]
            name = ProductParser._extract_with_patterns(content, name_patterns)
            
            price_patterns = [
                r'₹([0-9,]+)',
                r'"price":"([^"]+)"'
            ]
            price = ProductParser._extract_with_patterns(content, price_patterns)
            
            offers = ProductParser._extract_offers_generic(content)
            
            return ProductInfo(
                name=name or "Product name not found",
                price=f"₹{price}" if price else "Price not found",
                offers=offers,
                product_url=url,
                platform="Zepto"
            )
            
        except Exception as e:
            logger.error(f"Error parsing Zepto product: {str(e)}")
            return ProductInfo(name="Parse Error", price="N/A", product_url=url, platform="Zepto")
    
    @staticmethod
    def _extract_with_patterns(content: str, patterns: List[str]) -> str:
        """Extract text using regex patterns"""
        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
            if match:
                return match.group(1).strip()
        return ""
    
    @staticmethod
    def _extract_offers_amazon(content: str) -> List[str]:
        """Extract offers from Amazon content"""
        offers = []
        offer_patterns = [
            r'<span[^>]*class="[^"]*a-color-success[^"]*"[^>]*>([^<]+)</span>',
            r'Save ₹[0-9,]+',
            r'[0-9]+% off',
            r'Extra ₹[0-9,]+ off',
            r'Bank Offer[^<]*</span>([^<]+)',
            r'No Cost EMI',
            r'Free Delivery'
        ]
        
        for pattern in offer_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            offers.extend(matches)
        
        return list(set(offers))[:5]  # Return unique offers, max 5
    
    @staticmethod
    def _extract_offers_flipkart(content: str) -> List[str]:
        """Extract offers from Flipkart content"""
        offers = []
        offer_patterns = [
            r'Bank Offer[^<]*</span>([^<]+)',
            r'[0-9]+% off',
            r'₹[0-9,]+ off',
            r'No Cost EMI',
            r'Free Delivery',
            r'Exchange Offer'
        ]
        
        for pattern in offer_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            offers.extend(matches)
        
        return list(set(offers))[:5]
    
    @staticmethod
    def _extract_offers_generic(content: str) -> List[str]:
        """Extract offers from generic content"""
        offers = []
        offer_patterns = [
            r'[0-9]+% off',
            r'₹[0-9,]+ off',
            r'Free Delivery',
            r'No Cost EMI',
            r'Bank Offer',
            r'Cashback',
            r'Discount'
        ]
        
        for pattern in offer_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            offers.extend(matches)
        
        return list(set(offers))[:5]

class EcommerceScrapingCrew:
    """Main class orchestrating the CrewAI agents for e-commerce scraping"""
    
    def __init__(self, firecrawl_api_key: str = None, serper_api_key: str = None):
        self.firecrawl_api_key = firecrawl_api_key
        self.serper_api_key = serper_api_key
        self.setup_tools()
        self.setup_agents()
    
    def setup_tools(self):
        """Initialize scraping tools"""
        self.firecrawl_tool = FirecrawlScrapingTool(self.firecrawl_api_key)
        self.search_tool = EcommerceSearchTool()
        
        # Optional: Add Serper for web search if API key is provided
        if self.serper_api_key and SERPER_AVAILABLE:
            self.serper_tool = SerperDevTool(api_key=self.serper_api_key)
        else:
            self.serper_tool = None
    
    def setup_agents(self):
        """Setup CrewAI agents"""
        
        # Search Agent - Finds product URLs across platforms
        self.search_agent = Agent(
            role='E-commerce Search Specialist',
            goal='Find and identify the most relevant product listings across multiple e-commerce platforms',
            backstory="""You are an expert at navigating e-commerce websites and finding the best 
            product matches. You understand how different platforms structure their search results 
            and can identify the most relevant products based on user queries.""",
            tools=[self.search_tool] + ([self.serper_tool] if self.serper_tool else []),
            llm=LLM(
                model="gemini/gemini-2.0-flash",
                api_key=os.getenv("GEMINI_API_KEY")
            ),
            verbose=True,
            allow_delegation=False
        )
        
        # Scraping Agent - Extracts product data
        self.scraping_agent = Agent(
            role='Web Scraping Expert',
            goal='Extract comprehensive product information from e-commerce websites',
            backstory="""You are a skilled web scraper who can extract detailed product information 
            from various e-commerce platforms. You know how to handle different website structures, 
            dynamic content, and can parse offers, prices, and product details accurately.""",
            tools=[self.firecrawl_tool],
            llm=LLM(
                model="gemini/gemini-2.0-flash",
                api_key=os.getenv("GEMINI_API_KEY")
            ),
            verbose=True,
            allow_delegation=False
        )
        
        # Analysis Agent - Processes and ranks results
        self.analysis_agent = Agent(
            role='Product Data Analyst',
            goal='Analyze and rank scraped product data to provide the best recommendations',
            backstory="""You are a data analyst specializing in e-commerce product comparison. 
            You can evaluate product listings, compare prices, analyze offers, and rank products 
            based on various criteria to provide the best recommendations to users.""",
            llm=LLM(
                model="gemini/gemini-2.0-flash",
                api_key=os.getenv("GEMINI_API_KEY")
            ),
            tools=[],
            verbose=True,
            allow_delegation=False
        )
    
    def create_tasks(self, product_name: str, max_results: int = 5):
        """Create tasks for the crew"""
        
        # Task 1: Search for products
        search_task = Task(
            description=f"""
            Search for the product "{product_name}" across major e-commerce platforms:
            - Amazon India
            - Flipkart
            - Blinkit
            - Zepto
            
            For each platform, find the search URL and identify the top {max_results} most relevant 
            product listings. Return the URLs of individual products, not just search results.
            
            Focus on:
            1. Exact matches for the product name
            2. Popular and well-rated products
            3. Products with good availability
            4. Products from reliable sellers
            """,
            agent=self.search_agent,
            expected_output=f"List of {max_results} product URLs per platform with platform names and basic product identifiers"
        )
        
        # Task 2: Scrape product details
        scraping_task = Task(
            description=f"""
            Scrape detailed information from the product URLs found in the previous task.
            
            For each product, extract:
            1. Product name and title
            2. Current price and original price
            3. Discount percentage or amount
            4. All available offers (bank offers, cashback, EMI, etc.)
            5. Product rating and number of reviews
            6. Availability status
            7. Product images
            8. Brief product description
            9. Seller information (if available)
            
            Handle different website structures and ensure robust data extraction.
            If scraping fails for any URL, log the error and continue with others.
            """,
            agent=self.scraping_agent,
            expected_output="Comprehensive product data in structured format for all scraped products",
            context=[search_task]
        )
        
        # Task 3: Analyze and rank results
        analysis_task = Task(
            description=f"""
            Analyze the scraped product data and create a comprehensive comparison report.
            
            Your analysis should include:
            1. Top {max_results} products ranked by best value (considering price, offers, rating)
            2. Price comparison across platforms
            3. Summary of best offers available
            4. Platform-wise availability
            5. Recommendations based on different criteria:
               - Best price
               - Best offers
               - Highest rated
               - Best value for money
            
            Present the results in a clear, structured format that helps users make informed decisions.
            """,
            agent=self.analysis_agent,
            expected_output="Ranked list of top products with detailed comparison and recommendations",
            context=[search_task, scraping_task]
        )
        
        return [search_task, scraping_task, analysis_task]
    
    def scrape_product(self, product_name: str, max_results: int = 5) -> Dict[str, Any]:
        """Main method to scrape product information"""
        try:
            logger.info(f"Starting product search for: {product_name}")
            
            # Create tasks
            tasks = self.create_tasks(product_name, max_results)
            
            # Create and run crew
            crew = Crew(
                agents=[self.search_agent, self.scraping_agent, self.analysis_agent],
                llm=LLM(
                    model="gemini/gemini-2.0-flash",
                    api_key=os.getenv("GEMINI_API_KEY")
                ),
                tasks=tasks,
                process=Process.sequential,
                verbose=True
            )
            
            # Execute the crew
            result = crew.kickoff()
            
            # Process and structure the results
            structured_result = self._structure_results(result, product_name)
            
            logger.info(f"Successfully completed scraping for: {product_name}")
            return structured_result
            
        except Exception as e:
            logger.error(f"Error during scraping process: {str(e)}")
            return {
                'error': str(e),
                'product_name': product_name,
                'status': 'failed',
                'timestamp': datetime.now().isoformat()
            }
    
    def _structure_results(self, crew_result, product_name: str) -> Dict[str, Any]:
        """Structure the crew results into a standardized format"""
        try:
            return {
                'product_name': product_name,
                'status': 'success',
                'timestamp': datetime.now().isoformat(),
                'results': str(crew_result),
                'summary': f"Product search and analysis completed for '{product_name}'"
            }
        except Exception as e:
            logger.error(f"Error structuring results: {str(e)}")
            return {
                'product_name': product_name,
                'status': 'partial_success',
                'timestamp': datetime.now().isoformat(),
                'results': str(crew_result) if crew_result else 'No results',
                'error': str(e)
            }

def main():
    """Main function to demonstrate the scraper"""
    print("🛒 E-commerce Product Scraper using CrewAI")
    print("="*50)
    
    # Configuration
    FIRECRAWL_API_KEY = os.getenv('FIRECRAWL_API_KEY') 
    SERPER_API_KEY = os.getenv('SERPER_API_KEY') 
    
    # Show available features
    print("Available features:")
    print(f"✅ Basic scraping: Always available")
    print(f"{'✅' if FIRECRAWL_AVAILABLE else '❌'} Firecrawl integration: {'Available' if FIRECRAWL_AVAILABLE else 'Not installed'}")
    print(f"{'✅' if SERPER_AVAILABLE else '❌'} Serper search: {'Available' if SERPER_AVAILABLE else 'Not installed'}")
    print(f"{'✅' if UA_AVAILABLE else '❌'} User-Agent rotation: {'Available' if UA_AVAILABLE else 'Not installed'}")
    print()
    
    # Initialize the scraper
    try:
        scraper = EcommerceScrapingCrew(
            firecrawl_api_key=FIRECRAWL_API_KEY,
            serper_api_key=SERPER_API_KEY
        )
    except Exception as e:
        print(f"❌ Error initializing scraper: {str(e)}")
        print("Please ensure all required packages are installed:")
        print("pip install crewai requests beautifulsoup4")
        print("Optional: pip install firecrawl-py fake-useragent")
        return
    
    # Get product name from user
    product_name = input("Enter the product name to search: ").strip()
    
    if not product_name:
        print("Please enter a valid product name.")
        return
    
    print(f"\n🔍 Starting search for: {product_name}")
    print("This may take a few minutes as we search across multiple platforms...\n")
    
    # Run the scraper
    try:
        results = scraper.scrape_product(product_name, max_results=2)
        
        # Display results
        print("\n" + "="*80)
        print("SCRAPING RESULTS")
        print("="*80)
        print(json.dumps(results, indent=2, ensure_ascii=False))
        
        # Save results to file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"product_search_{product_name.replace(' ', '_')}_{timestamp}.json"
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            print(f"\n💾 Results saved to: {filename}")
        except Exception as e:
            print(f"\n❌ Error saving results: {str(e)}")
            
    except Exception as e:
        print(f"\n❌ Error during scraping: {str(e)}")
        print("This might be due to network issues or missing dependencies.")
        print("Please check your internet connection and installed packages.")

if __name__ == "__main__":
    main()