from pydantic import BaseModel, Field
from typing import List, Optional

class BasicDetails(BaseModel):
    description_summary: Optional[str] = None
    key_features: List[str] = Field(default_factory=list)
    variant_info: Optional[str] = None
    seller_name: Optional[str] = None
    credit_card_offers: List[str] = Field(default_factory=list)

class Product(BaseModel):
    title: str
    price: str
    url: str
    platform: str
    rating: Optional[str] = None
    seller: Optional[str] = None
    basic_details: Optional[str] = None
    original_price: Optional[float] = None
    effective_price: Optional[float] = None
    discount_applied: Optional[str] = None

class ProductListing(BaseModel):
    title: str
    price_str: str
    rating_str: Optional[str]
    url: str
    platform: str
    
class ProductOutput(BaseModel):
    """Pydantic model for the final, structured output data."""
    title: str
    platform: str
    price: str
    original_price: float
    effective_price: float
    discount_applied: str
    url: str
    rating: Optional[str] = None
    seller: Optional[str] = None