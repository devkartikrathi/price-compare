from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict, Any
import asyncio
import json
import os
from datetime import datetime
import uuid
from ai import analyze_product_prices

app = FastAPI(
    title="Smart E-commerce Price Analyzer API",
    description="API for analyzing e-commerce prices across multiple platforms with credit card offer optimization",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "https://smartprice.kartik-rathi.site"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request/Response Models
class PriceAnalysisRequest(BaseModel):
    product_query: str = Field(..., min_length=2, max_length=200, description="Product to search for")
    user_credit_cards: List[str] = Field(..., min_items=1, max_items=20, description="User's credit cards")
    max_products_per_platform: Optional[int] = Field(5, ge=1, le=20, description="Maximum products per platform")

class PriceAnalysisResponse(BaseModel):
    products: List[Dict[str, Any]] = Field(..., description="List of products with their details")

class HealthCheck(BaseModel):
    status: str
    timestamp: str
    version: str

@app.get("/", response_model=HealthCheck)
async def root():
    return HealthCheck(
        status="healthy",
        timestamp=datetime.now().isoformat(),
        version="2.0.0"
    )

@app.post("/analyze-prices", response_model=PriceAnalysisResponse)
async def analyze_prices(request: PriceAnalysisRequest):
    return await analyze_product_prices(
        product_query=request.product_query,
        user_credit_cards=request.user_credit_cards,
        # max_products_per_platform=request.max_products_per_platform
        max_products_per_platform=2
    )

@app.get("/supported-cards")
async def get_supported_cards():
    return {
        "supported_cards": [
            "HDFC Bank Regalia Credit Card",
            "HDFC Bank Millennia Credit Card",
            "HDFC Bank Diners Club Credit Card",
            "ICICI Bank Amazon Pay Credit Card",
            "ICICI Bank Coral Credit Card",
            "ICICI Bank Rubyx Credit Card",
            "Axis Bank Flipkart Credit Card",
            "Axis Bank Magnus Credit Card",
            "Axis Bank Neo Credit Card",
            "SBI Card Elite",
            "SBI SimplyCLICK Credit Card",
            "Citi Rewards Credit Card",
            "Citi Cashback Credit Card",
            "American Express Platinum Card",
            "Yes Bank Marquee Credit Card",
            "Kotak Mahindra 811 Credit Card"
        ],
        "note": "You can also enter custom card names. The system will try to match offers based on bank names and card types."
    }

@app.get("/platforms")
async def get_supported_platforms():
    return {
        "platforms": [
            "Amazon",
            "Flipkart", 
            "Myntra",
            "BigBasket",
            "Blinkit",
            "Zepto",
            "Swiggy",
            "Nykaa",
            "FirstCry"
        ],
        "note": "The scraper will automatically search across available platforms based on product category."
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)