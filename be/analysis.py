import json
import re
from typing import List, Dict, Any

from crewai import Agent, Task, Crew, Process
from crewai import LLM as CrewAILLM

from models import Product, ProductOutput
from utils import logger, parse_price
from config import AGENT_ROLE, AGENT_GOAL, AGENT_BACKSTORY

def analyze_discounts_with_crewai(products: List[Product], user_credit_cards: List[str], llm_api_key: str) -> List[Dict]:
    """Analyzes product data using a CrewAI agent to find the best deals."""
    if not products:
        return []

    try:
        # It's better to instantiate the LLM here to ensure it's fresh for the task.
        llm_crew = CrewAILLM(model="gemini/gemini-2.0-flash-lite", api_key=llm_api_key, temperature=0.1)

        processor_agent = Agent(
            role=AGENT_ROLE,
            goal=AGENT_GOAL,
            backstory=AGENT_BACKSTORY,
            llm=llm_crew,
            verbose=True,
            allow_delegation=False
        )

        products_input_str = json.dumps([p.model_dump(exclude_none=True) for p in products])
        
        analysis_task = Task(
            description=f"""
            Analyze the following JSON list of products: {products_input_str}
            The user has these credit cards: {json.dumps(user_credit_cards)}

            Your goal is to calculate the final effective price for each product by applying the best possible credit card discount.
            The 'basic_details' field contains a JSON string with 'credit_card_offers'. Parse this to find applicable offers.
            
            Return a JSON array of objects. Each object must conform to this Pydantic schema:
            {json.dumps(ProductOutput.model_json_schema())}
            
            Sort the final list by 'effective_price' in ascending order.
            """,
            agent=processor_agent,
            expected_output="A sorted JSON array of products with calculated effective prices."
        )

        crew = Crew(agents=[processor_agent], tasks=[analysis_task], verbose=True)
        logger.info(f"Starting CrewAI analysis for {len(products)} products.")
        
        result = crew.kickoff()

        # The result from CrewAI is often a string that needs parsing
        if result:
            parsed_result = json.loads(result)
            if isinstance(parsed_result, list):
                logger.info(f"CrewAI successfully processed {len(parsed_result)} products.")
                return parsed_result
        
        logger.warning("CrewAI returned an empty or invalid result.")
        return []

    except Exception as e:
        logger.error(f"CrewAI analysis failed: {e}. Will attempt fallback calculation.")
        return []

def calculate_discount_fallback(products: List[Product], user_credit_cards: List[str]) -> List[Dict]:
    """Fallback method to calculate discounts if the LLM agent fails."""
    logger.info("Using fallback discount calculation method.")
    results = []
    
    for product in products:
        original_price = product.original_price or parse_price(product.price)
        if not original_price:
            continue
            
        best_discount = 0.0
        best_offer_text = "None"
        
        if product.basic_details:
            try:
                details = json.loads(product.basic_details)
                offers = details.get('credit_card_offers', [])
                
                for offer in offers:
                    # Simple check if any user card is mentioned in the offer text
                    if any(card.lower() in offer.lower() for card in user_credit_cards):
                        # Extract discount amount (this is a simplified regex)
                        percent_match = re.search(r'(\d{1,2}(?:\.\d{1,2})?)%', offer)
                        amount_match = re.search(r'[₹Rs\.]\s*([\d,]+)', offer)
                        
                        current_discount = 0.0
                        if percent_match:
                            current_discount = original_price * (float(percent_match.group(1)) / 100)
                        elif amount_match:
                            current_discount = float(amount_match.group(1).replace(',', ''))
                        
                        if current_discount > best_discount:
                            best_discount = current_discount
                            best_offer_text = offer

            except (json.JSONDecodeError, AttributeError):
                pass # Ignore errors in parsing basic details
        
        results.append(ProductOutput(
            title=product.title,
            platform=product.platform,
            price=product.price,
            original_price=original_price,
            effective_price=original_price - best_discount,
            discount_applied=best_offer_text,
            url=product.url,
            rating=product.rating,
            seller=product.seller
        ).model_dump())

    results.sort(key=lambda x: x['effective_price'])
    return results