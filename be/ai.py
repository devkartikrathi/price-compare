import os
import json
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from google import genai
from dotenv import load_dotenv
from main import main as scrape
import asyncio

load_dotenv()

class OfferMatch(BaseModel):
    offer_description: str = Field(description="Description of the matched offer")
    discount_amount: float = Field(description="Discount amount in rupees")
    discount_percentage: float = Field(description="Discount percentage if applicable")
    applicable_card: str = Field(description="Which credit card this offer applies to")
    max_discount: Optional[float] = Field(description="Maximum discount limit if any", default=None)

class EffectivePriceCalculation(BaseModel):
    platform: str = Field(description="E-commerce platform name")
    product_title: str = Field(description="Product title")
    original_price: float = Field(description="Original price in rupees")
    applicable_offers: List[OfferMatch] = Field(description="List of applicable offers based on user's credit cards")
    total_discount: float = Field(description="Total discount amount")
    effective_price: float = Field(description="Final price after all discounts")
    best_card_to_use: str = Field(description="Which credit card gives maximum benefit")
    seller: Optional[str] = Field(description="Seller information", default="")
    rating: Optional[str] = Field(description="Product rating", default="")
    reviews_count: Optional[str] = Field(description="Number of reviews", default="")
    product_url: str = Field(description="URL to the product page")

class PriceComparisonResult(BaseModel):
    query: str = Field(description="Search query used")
    user_credit_cards: List[str] = Field(description="User's credit cards")
    calculations: List[EffectivePriceCalculation] = Field(description="Price calculations for each product")
    best_deal: EffectivePriceCalculation = Field(description="The best deal overall")
    summary: str = Field(description="Summary of the analysis and recommendation")

class SmartPriceCalculator:
    def __init__(self, google_api_key: str = None):
        self.api_key = google_api_key or os.getenv("GEMINI_API_KEY")
        self.client = genai.Client(api_key=self.api_key)
    
    def calculate_effective_prices(self, products_data: Dict, user_credit_cards: List[str]) -> PriceComparisonResult:
        prompt = f"""
        You are an expert e-commerce price analyzer. Analyze the following product data and user credit cards to calculate the most effective prices.
        
        USER'S CREDIT CARDS:
        {user_credit_cards}
        
        PRODUCT DATA:
        {json.dumps(products_data, indent=2)}
        
        ANALYSIS REQUIREMENTS:
        1. For each product, carefully match the offers with user's credit cards
        2. Calculate exact discount amounts (both percentage and fixed amount discounts)
        3. Consider maximum discount limits where applicable
        4. Calculate the final effective price after all applicable discounts
        5. Identify which credit card gives the maximum benefit for each product
        6. Determine the overall best deal considering price, rating, and seller reputation
        
        OFFER MATCHING RULES:
        - Match bank names exactly (e.g., "HDFC" card works for "HDFC Bank offers")
        - Match platform-specific cards (e.g., "Flipkart Axis Bank Card" for Flipkart offers)
        - Consider cashback offers as effective price reduction
        - For percentage discounts, calculate exact amount and apply maximum limits
        - Combine multiple applicable offers where possible
        
        PRICE CALCULATION EXAMPLES:
        - If price is ₹74,900 and offer is "5% off with max ₹2,500", discount = min(74,900 * 0.05, 2,500) = ₹2,500
        - If multiple offers are stackable, add them up
        - If offers are exclusive, pick the best one
        
        Return detailed calculations for each product and identify the best overall deal.
        Include a comprehensive summary with clear recommendations.
        """
        
        try:
            response = self.client.models.generate_content(
                model="gemini-2.0-flash-exp",
                contents=prompt,
                config={
                    "response_mime_type": "application/json",
                    "response_schema": PriceComparisonResult,
                },
            )
            
            return response.parsed
        except Exception as e:
            print(f"Error calculating prices: {e}")
            return None
    
    def analyze_and_recommend(self, products_json_file: str, user_cards_input: str) -> Dict:
        try:
            with open(products_json_file, 'r', encoding='utf-8') as f:
                products_data = json.load(f)
        except FileNotFoundError:
            return {"error": f"Product file {products_json_file} not found"}
        except json.JSONDecodeError:
            return {"error": "Invalid JSON format in product file"}

        result = self.calculate_effective_prices(products_data, user_cards_input)
        
        if not result:
            return {"error": "Failed to calculate effective prices"}
        
        return {
            "success": True,
            "analysis": result,
            "recommendations": {
                "best_deal": {
                    "product": result.best_deal.product_title,
                    "platform": result.best_deal.platform,
                    "original_price": result.best_deal.original_price,
                    "effective_price": result.best_deal.effective_price,
                    "savings": result.best_deal.total_discount,
                    "best_card": result.best_deal.best_card_to_use,
                    "url": result.best_deal.product_url
                },
                "summary": result.summary
            }
        }

def main():
    products_file = asyncio.run(scrape(product_query="samsung s24", max_products_per_platform=2, max_detail_pages=4))
    # products_file = "product_results.json"
    user_cards_input = [
        "HDFC Bank Regalia Credit Card",
        "ICICI Bank Amazon Pay Credit Card",
        "Axis Bank Flipkart Credit Card",
        "SBI Card Elite",
        "Citi Rewards Credit Card"
    ]
    
    try:
        calculator = SmartPriceCalculator()
        result = calculator.analyze_and_recommend(products_file, user_cards_input)
        
        if result.get("success"):
            best_deal = result["recommendations"]["best_deal"]
            print(f"Product: {best_deal['product']}")
            print(f"Platform: {best_deal['platform']}")
            print(f"Original Price: ₹{best_deal['original_price']:,.2f}")
            print(f"Effective Price: ₹{best_deal['effective_price']:,.2f}")
            print(f"You Save: ₹{best_deal['savings']:,.2f}")
            print(f"Best Card to Use: {best_deal['best_card']}")
            print(f"Product URL: {best_deal['url']}")
            
            print(result["recommendations"]["summary"])

            with open('price_analysis_result.json', 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False, default=str)
            print(f"\nDetailed analysis saved to price_analysis_result.json")
            
        else:
            print(f"Error: {result.get('error')}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()