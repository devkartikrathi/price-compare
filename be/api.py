from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict, Any
from datetime import datetime
import asyncio
import uuid
from ai import analyze_product_prices

app = FastAPI(
    title="Smart E-commerce Price Analyzer API",
    description="API for analyzing e-commerce prices across multiple platforms with credit card offer optimization",
    version="2.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173", 
        "https://smartprice.kartik-rathi.site", 
        "https://*.vercel.app",
        "http://localhost:3000",
        "http://localhost:3001"
    ], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Enhanced Models for the new response format
class CreditCardBenefits(BaseModel):
    reward_points_earned: float
    reward_points_value: float
    cashback_earned: float
    effective_cashback_rate: float
    annual_fee: str
    welcome_offer: str
    lounge_access: str
    other_benefits: str
    total_value_benefit: float

class UserCardBenefits(BaseModel):
    reward_points_earned: float
    reward_points_value: float
    cashback_earned: float
    total_value_benefit: float

class UserCardsAnalysis(BaseModel):
    best_user_card: str
    user_card_effective_price: float
    user_card_total_discount: float
    user_card_benefits: UserCardBenefits
    user_card_calculation_breakdown: str
    savings_vs_recommended: float
    recommendation_message: str

class ProductAnalysis(BaseModel):
    product_title: str
    product_url: str
    platform: str
    original_price: float
    total_discount: float
    effective_price: float
    savings_percentage: float
    recommended_card: str
    card_benefit_description: str
    credit_card_benefits: CreditCardBenefits
    user_cards_analysis: Optional[UserCardsAnalysis] = None
    points_calculation_breakdown: str
    confidence_score: float

# Request/Response Models
class PriceAnalysisRequest(BaseModel):
    product_query: str = Field(..., min_length=2, max_length=200, description="Product to search for")
    user_credit_cards: List[str] = Field(..., min_items=1, max_items=20, description="User's credit cards")
    max_products_per_platform: Optional[int] = Field(5, ge=1, le=20, description="Maximum products per platform")

    @field_validator('product_query')
    @classmethod
    def validate_product_query(cls, v):
        if not v.strip():
            raise ValueError('Product query cannot be empty')
        return v.strip()

    @field_validator('user_credit_cards')
    @classmethod
    def validate_credit_cards(cls, v):
        if not v or len(v) == 0:
            raise ValueError('At least one credit card must be provided')
        return [card.strip() for card in v if card.strip()]

class PriceAnalysisResponse(BaseModel):
    products: List[Dict[str, Any]] = Field(..., description="List of products with their analysis")
    total_products: Optional[int] = Field(None, description="Total number of products analyzed")
    query: Optional[str] = Field(None, description="Original search query")
    timestamp: Optional[str] = Field(None, description="Analysis timestamp")

class HealthCheck(BaseModel):
    status: str
    timestamp: str
    version: str
    features: List[str]

class ErrorResponse(BaseModel):
    error: str
    message: str
    timestamp: str
    request_id: str

@app.get("/", response_model=HealthCheck)
async def root():
    return HealthCheck(
        status="healthy",
        timestamp=datetime.now().isoformat(),
        version="2.1.0",
        features=[
            "Multi-platform price analysis",
            "Credit card optimization",
            "User card analysis",
            "Reward points calculation",
            "Cashback optimization",
            "Real-time price comparison"
        ]
    )

@app.post("/analyze-prices", response_model=PriceAnalysisResponse)
async def analyze_prices(request: PriceAnalysisRequest):
    request_id = str(uuid.uuid4())
    
    try:
        result = await analyze_product_prices(
            product_query=request.product_query,
            user_credit_cards=request.user_credit_cards,
            max_products_per_platform=min(request.max_products_per_platform, 10)
        )
        
        if not isinstance(result, dict) or 'products' not in result:
            raise HTTPException(
                status_code=500,
                detail=f"Invalid response format from analysis engine. Request ID: {request_id}"
            )
        
        enhanced_result = {
            "products": result.get('products', []),
            "total_products": len(result.get('products', [])),
            "query": request.product_query,
            "timestamp": datetime.now().isoformat()
        }
        
        print(f"[{datetime.now().isoformat()}] Successfully analyzed {len(enhanced_result['products'])} products for query: '{request.product_query}' | Request ID: {request_id}")
        
        return PriceAnalysisResponse(**enhanced_result)
        
    except Exception as e:
        error_msg = f"Error analyzing prices: {str(e)}"
        print(f"[{datetime.now().isoformat()}] {error_msg} | Request ID: {request_id}")
        
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Analysis Failed",
                "message": error_msg,
                "timestamp": datetime.now().isoformat(),
                "request_id": request_id
            }
        )

@app.get("/supported-cards")
async def get_supported_cards():
    return {
        "supported_cards": [
            # HDFC Bank Cards
            "HDFC Bank Millennia",
            "HDFC Bank Regalia Gold",
            "HDFC Bank Diners Club Black",
            "HDFC Bank IndianOil",
            
            # SBI Cards
            "SBI Card SimplyCLICK",
            "SBI Card SimplySAVE",
            "SBI Card ELITE",
            "BPCL SBI Card OCTANE",
            
            # ICICI Bank Cards
            "ICICI Bank Amazon Pay",
            "ICICI Bank Coral",
            "ICICI Bank Sapphiro",
            
            # Axis Bank Cards
            "Axis Bank ACE",
            "Flipkart Axis Bank",
            "Axis Bank Magnus",
            
            # American Express Cards
            "American Express Membership Rewards",
            "American Express Platinum Travel",
            
            # UAE Cards (for international users)
            "Emirates NBD Skywards Signature",
            "Emirates NBD dnata World",
            "FAB Cashback Card",
            "FAB Etihad Guest Platinum",
            "ADCB Talabat",
            "ADCB Lulu Platinum",
            "Dubai Islamic Bank Prime Infinite",
            "Dubai Islamic Bank Al Islami Platinum Charge"
        ],
        "supported_countries": ["India", "UAE"],
        "note": "You can also enter custom card names. The system will try to match offers based on bank names and card types.",
        "tip": "For best results, use the exact card name as it appears on your credit card."
    }

@app.get("/api/stats")
async def get_api_stats():
    """
    Get API usage statistics (placeholder for future implementation)
    """
    return {
        "message": "Statistics endpoint - Coming soon!",
        "features_planned": [
            "Request count tracking",
            "Popular product queries",
            "Most used credit cards",
            "Platform performance metrics"
        ]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api:app", 
        host="0.0.0.0", 
        port=8000,
        reload=True,
        log_level="info"
    )