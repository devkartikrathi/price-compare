import asyncio
import os
import json
import re
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, ConfigDict
from google import genai
from dotenv import load_dotenv
from main import run_product_pipeline as scrape

load_dotenv()

class SmartPriceCalculator:
    def __init__(self):
        self.client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

    def safe_json_parse(self, raw_text):
        try:
            return json.loads(raw_text.strip())
        except json.JSONDecodeError:
            return {"error": "Invalid JSON format from model"}
    
    def calculate_effective_prices(self, prepared_data: Dict, user_credit_cards: List[str]):
        prompt = f"""
            You are an expert e-commerce pricing and credit card offer analyst. Your job is to analyze the following product data and return the most cost-effective purchasing options using the user's credit cards.

            ### USER CONTEXT
            Search Query: "{prepared_data.get('query', '')}"
            User Credit Cards: {user_credit_cards}
            Total Products: {prepared_data.get('total_products', 0)}

            ### PRODUCT DATA
            {json.dumps(prepared_data, indent=2)}

            ---

            ### OUTPUT FORMAT (MUST FOLLOW STRICTLY)

            Return an array of product objects in the following JSON format and make sure to arrange the products in the increasing order of effective price onlys and give higher priority to the products with same name as the search query also convert the \u20b9 to ₹:

            [
            {{
                "product_title": string,
                "product_url": string,
                "platform": string,
                "original_price": float,
                "total_discount": float,
                "effective_price": float,
                "savings_percentage": float,
                "recommended_card": string,
                "card_benefit_description": string,
                "confidence_score": float
            }},
            ...
            ]

            ---

            ### RULES FOR ANALYSIS

            1. **Offer Matching Logic**
            - Match user credit cards to offers using:
                - Case-insensitive exact card name match
                - Partial bank name matches (e.g., "HDFC" → "HDFC Bank Credit Card")
                - Handle card aliases (e.g., "Flipkart Axis Bank" = "Axis Bank")
            - Use the most beneficial applicable offer (or multiple if combinable).
            - Exclude offers labeled as “already applied” or “special price” if they’re reflected in current price.

            2. **Price Calculation**
            - original_price = price_str and in case of flipkart special offer is already applied so don't apply it again rather use another offer as only flipkart allows one more offer to be applied on price_str excluding the special offer and in case of any other platform use price_str and just apply one best possible offer.
            - total_discount = Total of valid applicable discounts (use max single if not combinable)
            - effective_price = original_price - total_discount
            - savings_percentage = (total_discount / original_price) * 100

            3. **Recommendation Ranking**
            - Give higher priority to the products with same name as the search query
            - Rank by lowest effective_price (Secondary)

            4. **Credit Card Recommendation**
            - Choose the best credit card for each product (most savings)
            - Explain the benefit and how to apply it at checkout

            5. **Confidence Score**
            - Float between 0.0 - 1.0 indicating analysis confidence

            ---

            ### IMPORTANT NOTES
            - All numbers must be realistic and valid (e.g., no negative prices)
            - Always return a valid JSON structure (no markdown, no explanation, no extra text)
            - Output only the JSON array in the exact schema above
            """



        response = self.client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
            config={
                "response_mime_type": "application/json",
                "temperature": 0.1,  
            },
            )
        return self.safe_json_parse(response.text)

async def analyze_product_prices(product_query: str, user_credit_cards: List[str], max_products_per_platform: int = 3):
    scraper_results = await scrape(product_query, max_products_per_platform)
    print("scraper_results: ", scraper_results)
    calculator = SmartPriceCalculator()
    result = calculator.calculate_effective_prices(scraper_results, user_credit_cards)
    if isinstance(result, list):
        return {"products": result}
    elif isinstance(result, dict) and "products" in result:
        return result
    else:
        return {"products": []}
    
if __name__ == "__main__":
    result = asyncio.run(analyze_product_prices("iPhone 16", ["HDFC Bank Credit Card", "Flipkart Axis Bank Credit Card"]))
    print(result)