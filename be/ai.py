import asyncio
import os
import json
import re
import pandas as pd
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, ConfigDict
from google import genai
from dotenv import load_dotenv
from main import run_product_pipeline as scrape
load_dotenv()
class SmartPriceCalculator:
    def __init__(self, cc_csv_path: str = "CC.csv"):
        self.client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        self.credit_card_data = self.load_credit_card_data(cc_csv_path)

    def load_credit_card_data(self, csv_path: str) -> Dict[str, Any]:
        """Load and process credit card data from CSV file"""
        try:
            df = pd.read_csv(csv_path)
            df = df.dropna(subset=['Bank', 'Card Name'], how='all')
            df['Bank'] = df['Bank'].fillna(method='ffill')
            df = df.dropna(subset=['Card Name'])
            
            cards_data = []
            for _, row in df.iterrows():
                if pd.notna(row['Card Name']) and row['Card Name'].strip():
                    card_info = {
                        'country': row.get('Country', '').strip() if pd.notna(row.get('Country')) else '',
                        'bank': row.get('Bank', '').strip() if pd.notna(row.get('Bank')) else '',
                        'card_name': row.get('Card Name', '').strip() if pd.notna(row.get('Card Name')) else '',
                        'key_features': row.get('Key Features/Benefits', '').strip() if pd.notna(row.get('Key Features/Benefits')) else '',
                        'joining_fee': row.get('Joining Fee (INR/AED)', '').strip() if pd.notna(row.get('Joining Fee (INR/AED)')) else '',
                        'annual_fee': row.get('Annual Fee (INR/AED)', '').strip() if pd.notna(row.get('Annual Fee (INR/AED)')) else '',
                        'welcome_offer': row.get('Welcome Offer', '').strip() if pd.notna(row.get('Welcome Offer')) else '',
                        'rewards_program': row.get('Rewards Program', '').strip() if pd.notna(row.get('Rewards Program')) else '',
                        'lounge_access': row.get('Lounge Access', '').strip() if pd.notna(row.get('Lounge Access')) else '',
                        'other_benefits': row.get('Other Benefits', '').strip() if pd.notna(row.get('Other Benefits')) else ''
                    }
                    cards_data.append(card_info)
            
            return {
                'cards': cards_data,
                'total_cards': len(cards_data)
            }
        except Exception as e:
            print(f"Error loading credit card data: {e}")
            return {'cards': [], 'total_cards': 0}

    def safe_json_parse(self, raw_text):
        try:
            return json.loads(raw_text.strip())
        except json.JSONDecodeError:
            return {"error": "Invalid JSON format from model"}
    
    def calculate_effective_prices(self, prepared_data: Dict, user_credit_cards: List[str]):
        prompt = f"""
            You are an expert e-commerce pricing and credit card offer analyst. Your job is to analyze the following product data and return the most cost-effective purchasing options using the user's credit cards, including detailed credit card benefits and points calculations.

            ### USER CONTEXT
            Search Query: "{prepared_data.get('query', '')}"
            User Credit Cards: {user_credit_cards}
            Total Products: {prepared_data.get('total_products', 0)}

            ### PRODUCT DATA
            {json.dumps(prepared_data, indent=2)}

            ### CREDIT CARD DATABASE
            Available Credit Cards and Their Benefits:
            {json.dumps(self.credit_card_data, indent=2)}

            ---

            ### OUTPUT FORMAT (MUST FOLLOW STRICTLY)

            Return an array of product objects in the following JSON format and make sure to arrange the products in the increasing order of effective price only and give higher priority to the products with same name as the search query also convert the \u20b9 to ₹:

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
                "credit_card_benefits": {{
                    "reward_points_earned": float,
                    "reward_points_value": float,
                    "cashback_earned": float,
                    "effective_cashback_rate": float,
                    "annual_fee": string,
                    "welcome_offer": string,
                    "lounge_access": string,
                    "other_benefits": string,
                    "total_value_benefit": float
                }},
                "points_calculation_breakdown": string,
                "confidence_score": float
            }},
            ...
            ]

            ---

            ### RULES FOR ANALYSIS

            1. **Credit Card Matching Logic**
            - Match user credit cards to the credit card database using:
                - Case-insensitive exact card name match
                - Partial bank name matches (e.g., "HDFC" → "HDFC Bank")
                - Handle card aliases (e.g., "Flipkart Axis Bank" = "Axis Bank")
            - Use the most beneficial applicable card for each product.

            2. **Price Calculation**
            - original_price = price_str and in case of flipkart special offer is already applied so don't apply it again rather use another offer as only flipkart allows one more offer to be applied on price_str excluding the special offer and in case of any other platform use price_str and just apply one best possible offer.
            - total_discount = Total of valid applicable discounts (use max single if not combinable)
            - effective_price = original_price - total_discount
            - savings_percentage = (total_discount / original_price) * 100

            3. **Credit Card Benefits Calculation**
            - **reward_points_earned**: Calculate based on the card's reward structure (e.g., "4 Reward Points per ₹150 spent" means effective_price/150*4)
            - **reward_points_value**: Monetary value of earned points (e.g., if 1 point = ₹0.25, then multiply points by 0.25)
            - **cashback_earned**: Direct cashback amount based on card's cashback rate
            - **effective_cashback_rate**: Total percentage benefit including points value and cashback
            - **annual_fee**: From the card database
            - **welcome_offer**: From the card database
            - **lounge_access**: From the card database
            - **other_benefits**: From the card database
            - **total_value_benefit**: Sum of reward_points_value + cashback_earned

            4. **Points Calculation Breakdown**
            - Provide a clear explanation of how points/cashback were calculated
            - Example: "₹25,000 spent ÷ ₹150 × 4 points = 667 points worth ₹166.75 (₹0.25 per point)"

            5. **User Cards Analysis**
            - **best_user_card**: The best card from user's available cards for this specific product
            - **user_card_effective_price**: Final price using the best user card (original_price - user_card_total_discount)
            - **user_card_total_discount**: Total discount achievable with user's best card
            - **user_card_benefits**: Detailed benefits calculation for the user's best card
            - **user_card_calculation_breakdown**: Clear explanation of user card calculations
            - **savings_vs_recommended**: Difference between recommended card effective price and user card effective price (positive means user saves more with recommended card)
            - **recommendation_message**: Advice on whether to use user's card or consider getting the recommended card

            6. **Recommendation Logic**
            - Always analyze user's available cards first
            - Calculate effective price with user's best card
            - Compare with overall best card recommendation
            - Provide clear guidance on the best option for the user

            7. **Recommendation Ranking**
            - Give higher priority to products with same name as the search query
            - Rank by lowest effective_price (Secondary)
            - Consider total_value_benefit in recommendations

            8. **Credit Card Recommendation**
            - Choose the best credit card for each product (considering both discounts and long-term benefits)
            - Explain the benefit and how to apply it at checkout

            9. **Confidence Score**
            - Float between 0.0 - 1.0 indicating analysis confidence

            ---

            ### CALCULATION EXAMPLES

            **User Card vs Recommended Card Analysis:**
            
            **Scenario: User has HDFC Millennia, Recommended is Axis Magnus**
            - Original Price: ₹50,000
            - User Card (HDFC Millennia): 1% cashback = ₹500, Effective Price: ₹49,500
            - Recommended Card (Axis Magnus): 12 EDGE Rewards per ₹200 = 3000 points worth ₹750, Effective Price: ₹49,250
            - Savings vs Recommended: ₹250 (User could save ₹250 more with Magnus)
            - Recommendation: "Consider applying for Axis Magnus for ₹250 additional savings"

            **HDFC Millennia Example:**
            - If spending ₹10,000 on Amazon (5% cashback category)
            - Cashback: ₹10,000 × 0.05 = ₹500
            - Plus 1000 Cash Points worth ₹250 (₹0.25 per point)
            - Total benefit: ₹750

            **SBI Card ELITE Example:**
            - If spending ₹15,000 on dining (5X points category)
            - Points: ₹15,000 ÷ ₹100 × 5 = 750 points
            - If 1 point = ₹0.25, value = ₹187.50

            ---

            ### IMPORTANT NOTES
            - All numbers must be realistic and valid (e.g., no negative prices)
            - Always return a valid JSON structure (no markdown, no explanation, no extra text)
            - Output only the JSON array in the exact schema above
            - Calculate benefits accurately based on the credit card database provided
            - Consider category-specific benefits (e.g., dining, online shopping, fuel)
            - Factor in annual fees when recommending cards for long-term value
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

async def analyze_product_prices(product_query: str, user_credit_cards: List[str], max_products_per_platform: int = 3, cc_csv_path: str = "CC.csv"):
    scraper_results = await scrape(product_query, 3)
    calculator = SmartPriceCalculator(cc_csv_path)
    result = calculator.calculate_effective_prices(scraper_results, user_credit_cards)

    if isinstance(result, list):
        return {"products": result}
    elif isinstance(result, dict) and "products" in result:
        return result
    else:
        return {"products": []}
    
if __name__ == "__main__":
    result = asyncio.run(analyze_product_prices(
        "iPhone 15 128GB", 
        ["HDFC Bank Millennia"],
        cc_csv_path="CC.csv"
    ))
    print(json.dumps(result, indent=2))