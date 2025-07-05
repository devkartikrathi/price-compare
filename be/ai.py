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
            df = df.dropna(subset=['Card Name'])
            
            cards_data = []
            for _, row in df.iterrows():
                if pd.notna(row['Card Name']) and row['Card Name'].strip():
                    card_info = {
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
        - **ONLY analyze credit cards that the user actually owns**: {user_credit_cards}
        - Match user credit cards to the credit card database using:
            - Case-insensitive exact card name match
            - Partial bank name matches (e.g., "HDFC" → "HDFC Bank")
            - Handle card aliases (e.g., "Flipkart Axis Bank" = "Axis Bank")
        - **IMPORTANT**: Apply ALL applicable credit card benefits for each product, but ONLY for user's cards:
            - Platform-specific benefits (e.g., Amazon Pay ICICI for Amazon purchases)
            - Universal benefits (e.g., card's cashback on all purchases)
            - Category-specific benefits (e.g., dining, fuel, online shopping)
        - Use the most beneficial card from user's available cards for each product.

        2. **Price Calculation**
        - original_price = price_str and in case of flipkart special offer is already applied so don't apply it again rather use another offer as only flipkart allows one more offer to be applied on price_str excluding the special offer and in case of any other platform use price_str and just apply one best possible offer.
        - total_discount = Total of valid applicable discounts (use max single if not combinable) + credit card benefits
        - effective_price = original_price - total_discount
        - savings_percentage = (total_discount / original_price) * 100

        3. **Credit Card Benefits Calculation - USER CARDS ONLY**
        - **For each product, analyze ONLY the user's available credit cards**: {user_credit_cards}
        - **DO NOT recommend or calculate benefits for cards the user doesn't own**
        - **reward_points_earned**: Calculate based on the user's card reward structure considering:
            - Platform-specific rates (e.g., 5% on Amazon for Amazon Pay ICICI)
            - Universal rates (e.g., 1% on all purchases for HDFC Millennia)
            - Category-specific rates (e.g., 5X points on dining, 2X on online shopping)
        - **reward_points_value**: Monetary value of earned points (e.g., if 1 point = ₹0.25, then multiply points by 0.25)
        - **cashback_earned**: Direct cashback amount based on user's card cashback rate (consider both platform-specific and universal rates)
        - **effective_cashback_rate**: Total percentage benefit including points value and cashback
        - **annual_fee**: From the card database for user's card
        - **welcome_offer**: From the card database for user's card
        - **lounge_access**: From the card database for user's card
        - **other_benefits**: From the card database for user's card
        - **total_value_benefit**: Sum of reward_points_value + cashback_earned

        4. **User's Credit Card Benefits Application**
        - **CRITICAL**: Only evaluate credit cards that the user actually owns: {user_credit_cards}
        - **For each product, consider user's cards only**:
            - If user has HDFC Millennia, apply its 1% cashback on all purchases to all platforms
            - If user has Amazon Pay ICICI, apply its 5% cashback specifically to Amazon purchases
            - If user has Axis Bank Flipkart, apply its benefits only if user actually owns this card
        - **DO NOT apply benefits from cards the user doesn't own**
        - **Choose the best card from user's available cards that provides maximum total benefit for each specific product**

        5. **Points Calculation Breakdown**
        - Provide a clear explanation of how points/cashback were calculated using user's cards only
        - Include both platform-specific and universal benefits in the breakdown for user's cards
        - Example: "Using HDFC Millennia: 1% cashback on ₹60,000 = ₹600" or "Using Amazon Pay ICICI: 5% cashback on Amazon purchase ₹60,000 = ₹3,000 (capped at ₹1,800)"

        6. **User Cards Analysis**
        - **best_user_card**: The best card from user's available cards for this specific product
        - **user_card_effective_price**: Final price using the best user card (original_price - user_card_total_discount)
        - **user_card_total_discount**: Total discount achievable with user's best card
        - **user_card_benefits**: Detailed benefits calculation for the user's best card
        - **user_card_calculation_breakdown**: Clear explanation of user card calculations
        - **savings_vs_recommended**: Difference between recommended card effective price and user card effective price (positive means user saves more with recommended card)
        - **recommendation_message**: Advice on whether to use user's card or consider getting the recommended card

        7. **Recommendation Logic**
        - Always analyze user's available cards first
        - Calculate effective price with user's best card
        - Compare with overall best card recommendation
        - Provide clear guidance on the best option for the user

        8. **Recommendation Ranking**
        - Give higher priority to products with same name as the search query
        - Rank by lowest effective_price (Secondary)
        - Consider total_value_benefit in recommendations

        9. **Credit Card Recommendation**
        - Choose the best credit card from user's available cards for each product considering applicable benefits (platform-specific + universal + category-specific)
        - **recommended_card** should always be one of the user's cards: {user_credit_cards}
        - Explain the benefit and how to apply it at checkout

        10. **Confidence Score**
        - Float between 0.0 - 1.0 indicating analysis confidence

        ---

        ### CALCULATION EXAMPLES

        **User's Available Cards Analysis:**
        - Product: iPhone 15 on Amazon for ₹60,000
        - User Cards: ["HDFC Bank Millennia", "ICICI Bank Amazon Pay"]
        - HDFC Millennia Analysis:
            - Universal benefit: 1% cashback on all purchases = ₹600
            - Total benefit: ₹600, Effective price: ₹59,400
        - Amazon Pay ICICI Analysis:
            - Platform-specific: 5% cashback on Amazon = ₹3,000 (capped at ₹1,800)
            - Total benefit: ₹1,800, Effective price: ₹58,200
        - **Result**: Amazon Pay ICICI is better for this Amazon purchase (from user's available cards)

        **Flipkart Purchase Example:**
        - Product: iPhone 15 on Flipkart for ₹64,900
        - User Cards: ["HDFC Bank Millennia", "ICICI Bank Amazon Pay"]
        - HDFC Millennia Analysis:
            - Universal benefit: 1% cashback on all purchases = ₹649
            - Total benefit: ₹649, Effective price: ₹64,251
        - Amazon Pay ICICI Analysis:
            - Universal benefit: 1% cashback on all purchases = ₹649
            - Total benefit: ₹649, Effective price: ₹64,251
        - **Result**: Both cards provide same benefit, choose any (from user's available cards)

        **HDFC Millennia Example:**
        - If spending ₹10,000 on any platform
        - Universal cashback: ₹10,000 × 0.01 = ₹100
        - Total benefit: ₹100

        **Amazon Pay ICICI Example:**
        - If spending ₹15,000 on Amazon (platform-specific benefit)
        - Cashback: ₹15,000 × 0.05 = ₹750 (subject to monthly caps)
        - If spending ₹15,000 on other platforms: 1% cashback = ₹150

        ---

        ### IMPORTANT NOTES
        - **CRITICAL**: Only analyze and recommend credit cards that the user actually owns: {user_credit_cards}
        - **DO NOT recommend cards the user doesn't have**
        - **Universal benefits from user's cards apply to all platforms** - don't restrict cards to specific platforms only
        - **Platform-specific benefits are bonuses on top of universal benefits where applicable**
        - All numbers must be realistic and valid (e.g., no negative prices)
        - Always return a valid JSON structure (no markdown, no explanation, no extra text)
        - Output only the JSON array in the exact schema above
        - Calculate benefits accurately based on the credit card database provided, but only for user's cards
        - Consider category-specific benefits (e.g., dining, online shopping, fuel) for all platforms, but only for user's cards
        - Factor in annual fees when recommending cards for long-term value
        - **Ensure analysis is performed only for user's available credit cards**
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
    # scraper_results = await scrape(product_query, 3)
    scraper_results = {'query': 'iPhone 15 128GB', 'total_listings_found': 9, 'detailed_products_processed': 9, 'products': [{'listing_info': {'title': 'Apple iPhone 15 (128 GB) - Blue', 'price_str': '₹60,300', 'original_price_str': '', 'rating_str': '4.5 out of 5 stars', 'url': 'https://www.amazon.in/dp/B0CHX2F5QT', 'platform': 'Amazon'}, 'detailed_info': {'offer_details': "₹60,300.00 with 14 percent savings -14%₹60,300\nM.R.P.: ₹69,900.00 M.R.P.: ₹69,900₹69,900\nIncludes selected options.  Includes initial monthly payment and selected options. [Details](https://www.amazon.in/dp/B0CHX2F5QT?th=1#)\n\n* * *\n\n**EMI** starts at ₹2,923 per month. **EMI** starts at ₹2,923. No Cost EMI available  EMI options\n\n- [Amazon Pay Later](https://www.amazon.in/dp/B0CHX2F5QT?th=1#)\n- [Debit Card EMI](https://www.amazon.in/dp/B0CHX2F5QT?th=1#)\n- [Other EMIs](https://www.amazon.in/dp/B0CHX2F5QT?th=1#)\n\nView only 'No Cost EMI' options\n\nAmazon Pay ICICI Credit Card\n\nProcessing Fee of ₹199 by Bank\n\n#### No Cost EMI Plans\n\n| EMI Plan | Interest(pa) | Discount | Total cost |\n| ₹20,100x 3m | ₹1,572(15.99%) | ₹1,572 | ₹60,300 |\n| ₹10,050x 6m | ₹2,715(15.99%) | ₹2,715 | ₹60,300 |"}}, {'listing_info': {'title': 'Apple iPhone 15 (128 GB) - Pink', 'price_str': '₹60,000', 'original_price_str': '', 'rating_str': '4.5 out of 5 stars', 'url': 'https://www.amazon.in/dp/B0CHX3TW6X', 'platform': 'Amazon'}, 'detailed_info': {'offer_details': '₹60,000.00 with 14 percent savings -14%₹60,000\nM.R.P.: ₹69,900.00 M.R.P.: ₹69,900₹69,900\nIncludes all taxes\nEMI starts at ₹2,909 per month. No Cost EMI available\nUpto ₹1,800.00 cashback as Amazon Pay Balance when you pay with Amazon Pay ICICI Bank Credit Cards\nUpto ₹2,701.72 EMI interest savings on Amazon Pay ICICI Bank Credit Cards\nGet GST invoice and save up to 28% on business purchases.'}}, {'listing_info': {'title': 'Apple iPhone 15 (128 GB) - Green', 'price_str': '₹60,500', 'original_price_str': '', 'rating_str': '4.5 out of 5 stars', 'url': 'https://www.amazon.in/dp/B0CHX6NQMD', 'platform': 'Amazon'}, 'detailed_info': {'offer_details': '₹60,500.00 with 13 percent savings -13%₹60,500 M.R.P.: ₹69,900.00 Inclusive of all taxes\n\nEMI starts at ₹2,933 per month. No Cost EMI available\n\nUpto ₹1,815.00 cashback as Amazon Pay Balance when you pay with Amazon Pay ICICI Bank Credit Cards\n\nUpto ₹2,724.26 EMI interest savings on Amazon Pay ICICI Bank Credit Cards\n\nGet GST invoice and save up to 28% on business purchases.'}}, {'listing_info': {'title': 'Apple iPhone 15 (Blue, 128 GB)', 'price_str': '₹64,900', 'original_price_str': '', 'rating_str': None, 'url': 'https://www.flipkart.com/apple-iphone-15-blue-128-gb/p/itmbf14ef54f645d?pid=MOBGTAGPAQNVFZZY&lid=LSTMOBGTAGPAQNVFZZYQRLPCQ&marketplace=FLIPKART&q=iPhone+15+128GB&store=tyy%2F4io&srno=s_1_1&otracker=search&fm=organic&iid=85f43595-b9ab-494f-ba26-d5a97eba4941.MOBGTAGPAQNVFZZY.SEARCH&ppt=None&ppn=None&ssid=gnvrtq0n4w0000001751641511978&qH=2953a49b03f1f51b', 'platform': 'Flipkart'}, 'detailed_info': {'offer_details': 'Extra ₹5000 off\n\nAvailable offers:\n1. Bank Offer: 5% cashback on Flipkart Axis Bank Credit Card up to ₹4,000 per statement quarter\n2. Bank Offer: 5% cashback on Axis Bank Flipkart Debit Card up to ₹750\n3. Bank Offer: Flat ₹10 Instant Cashback on Paytm UPI Transactions. Min Order Value ₹500. Valid once per Paytm account\n4. Special Price: Get extra ₹5000 off (price inclusive of cashback/coupon)\n5. Buy without Exchange: ₹64,900\n6. Buy with Exchange: up to ₹48,150 off\n7. Get extra ₹3,000 off on exchange of select models.'}}, {'listing_info': {'title': 'Apple iPhone 15 (Pink, 128 GB)', 'price_str': '₹64,900', 'original_price_str': '', 'rating_str': None, 'url': 'https://www.flipkart.com/apple-iphone-15-pink-128-gb/p/itm7579ed94ca647?pid=MOBGTAGPNMZA5PU5&lid=LSTMOBGTAGPNMZA5PU5E1UCRJ&marketplace=FLIPKART&q=iPhone+15+128GB&store=tyy%2F4io&srno=s_1_2&otracker=search&fm=organic&iid=85f43595-b9ab-494f-ba26-d5a97eba4941.MOBGTAGPNMZA5PU5.SEARCH&ppt=None&ppn=None&ssid=gnvrtq0n4w0000001751641511978&qH=2953a49b03f1f51b', 'platform': 'Flipkart'}, 'detailed_info': {'offer_details': 'Available offers:\n1. Bank Offer: 5% cashback on Flipkart Axis Bank Credit Card up to ₹4,000 per statement quarter\n2. Bank Offer: 5% cashback on Axis Bank Flipkart Debit Card up to ₹750\n3. Bank Offer: Flat ₹10 Instant Cashback on Paytm UPI Transactions. Min Order Value ₹500. Valid once per Paytm account\n4. No Cost EMI on Bajaj Finserv\n5. Buy without Exchange: ₹64,900\n6. Buy with Exchange: up to ₹48,150 off\n7. Get extra ₹3,000 off on exchange of select models.'}}, {'listing_info': {'title': 'Apple iPhone 15 (Black, 128 GB)', 'price_str': '₹64,900', 'original_price_str': '', 'rating_str': None, 'url': 'https://www.flipkart.com/apple-iphone-15-black-128-gb/p/itm6ac6485515ae4?pid=MOBGTAGPTB3VS24W&lid=LSTMOBGTAGPTB3VS24WKFODHL&marketplace=FLIPKART&q=iPhone+15+128GB&store=tyy%2F4io&spotlightTagId=default_FkPickId_tyy%2F4io&srno=s_1_3&otracker=search&fm=organic&iid=85f43595-b9ab-494f-ba26-d5a97eba4941.MOBGTAGPTB3VS24W.SEARCH&ppt=sp&ppn=sp&ssid=gnvrtq0n4w0000001751641511978&qH=2953a49b03f1f51b', 'platform': 'Flipkart'}, 'detailed_info': {'offer_details': 'Available offers:\n1. Bank Offer: 5% cashback on Flipkart Axis Bank Credit Card up to ₹4,000 per statement quarter\n2. Bank Offer: 5% cashback on Axis Bank Flipkart Debit Card up to ₹750\n3. Bank Offer: Flat ₹10 Instant Cashback on Paytm UPI Transactions. Min Order Value ₹500. Valid once per Paytm account\n4. No Cost EMI on Bajaj Finserv\n5. Buy without Exchange: ₹64,900\n6. Buy with Exchange: up to ₹48,150 off. Get extra ₹3,000 off on exchange of select models.'}}, {'listing_info': {'title': 'AppleiPhone 15 (128GB, Black)1 Unit - Black', 'price_str': '₹61490₹69900', 'original_price_str': '', 'rating_str': None, 'url': 'https://www.bigbasket.com/pd/40331223/apple-iphone-15-128gb-black/?nc=cl-prod-list&t_pos_sec=1&t_pos_item=1&t_s=iPhone+15+%2528128GB%252C+Black%2529', 'platform': 'Bigbasket'}, 'detailed_info': {'offer_details': 'MRP: ₹69900\nPrice: ₹61490 (₹61490 / pc)\nYou Save: 12% OFF (inclusive of all taxes)'}}]}
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
        ["HDFC Bank Millennia", "ICICI Bank Amazon Pay"],
        cc_csv_path="CC.csv"
    ))
    print(json.dumps(result, indent=2))