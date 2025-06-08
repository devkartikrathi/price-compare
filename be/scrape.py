import os
import json
from firecrawl import FirecrawlApp
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()

class AmazonProduct(BaseModel):
    product_title: str = Field(description="The title of the product")
    price: str = Field(description="The current price of the product, including currency")
    offers: list[str] = Field(description="List of current offers on the product, including bank credit card offers")
    brand: str = Field(description="The brand of the product")
    asin: str = Field(description="The Amazon Standard Identification Number")

class FlipkartProduct(BaseModel):
    product_title: str = Field(description="The title of the product")
    price: str = Field(description="The current price of the product, including currency")
    original_price: str = Field(description="The original price before discount, if available", default="")
    discount: str = Field(description="The discount percentage or amount, if available", default="")
    offers: list[str] = Field(description="List of current offers on the product, including bank offers and exchange offers")
    brand: str = Field(description="The brand of the product")
    rating: str = Field(description="The product rating out of 5", default="")
    reviews_count: str = Field(description="Number of reviews/ratings", default="")

def scrape_flipkart_product(url: str) -> FlipkartProduct:
    api_key = os.getenv("FIRECRAWL_API_KEY")
    if not api_key:
        raise ValueError("FIRECRAWL_API_KEY not set in .env file")
    
    app = FirecrawlApp(api_key=api_key)

    # Corrected API call structure for Flipkart
    result = app.scrape_url(
        url,
        formats=['json'],
        jsonOptions={
            'schema': FlipkartProduct.model_json_schema()
        }
    )
    
    print(result)
    
    # Handle the response structure correctly
    if hasattr(result, 'json') and result.json:
        return FlipkartProduct(**result.json)
    elif isinstance(result, dict) and 'json' in result and result['json']:
        return FlipkartProduct(**result['json'])
    else:
        raise ValueError(f"Failed to extract product data. Response: {result}")

def detect_platform(url: str) -> str:
    """Detect whether the URL is from Amazon or Flipkart"""
    if "amazon." in url.lower():
        return "amazon"
    elif "flipkart." in url.lower():
        return "flipkart"
    else:
        raise ValueError("Unsupported platform. Only Amazon and Flipkart are supported.")

def scrape_product(url: str):
    """Universal product scraper that handles both Amazon and Flipkart"""
    platform = detect_platform(url)
    
    if platform == "amazon":
        return scrape_amazon_product(url)
    elif platform == "flipkart":
        return scrape_flipkart_product(url)
    else:
        raise ValueError(f"Unsupported platform: {platform}")
    api_key = os.getenv("FIRECRAWL_API_KEY")
    if not api_key:
        raise ValueError("FIRECRAWL_API_KEY not set in .env file")
    
    app = FirecrawlApp(api_key=api_key)

    # Corrected API call structure
    result = app.scrape_url(
        url,
        formats=['json'],
        jsonOptions={
            'schema': AmazonProduct.model_json_schema()
        }
    )
    
    print(result)
    
    # Handle the response structure correctly
    if hasattr(result, 'json') and result.json:
        return AmazonProduct(**result.json)
    elif isinstance(result, dict) and 'json' in result and result['json']:
        return AmazonProduct(**result['json'])
    else:
        raise ValueError(f"Failed to extract product data. Response: {result}")

def scrape_amazon_product(url: str) -> AmazonProduct:
    api_key = os.getenv("FIRECRAWL_API_KEY")
    if not api_key:
        raise ValueError("FIRECRAWL_API_KEY not set in .env file")
    
    app = FirecrawlApp(api_key=api_key)

    # Corrected API call structure
    result = app.scrape_url(
        url,
        formats=['json'],
        jsonOptions={
            'schema': AmazonProduct.model_json_schema()
        }
    )
    
    print(result)
    
    # Handle the response structure correctly
    if hasattr(result, 'json') and result.json:
        return AmazonProduct(**result.json)
    elif isinstance(result, dict) and 'json' in result and result['json']:
        return AmazonProduct(**result['json'])
    else:
        raise ValueError(f"Failed to extract product data. Response: {result}")

def save_product_json(product, filename: str):
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(product.model_dump_json(indent=2))

if __name__ == "__main__":
    # Example URLs - you can test with either platform
    amazon_url = "https://www.amazon.in/dp/B0DGJH8RYG"
    flipkart_url = "https://www.flipkart.com/apple-iphone-16-black-128-gb/p/itmb07d67f995271?pid=MOBH4DQFG8NKFRDY&lid=LSTMOBH4DQFG8NKFRDYNBDOZI&marketplace=FLIPKART&q=iPhone+16&store=tyy%2F4io&spotlightTagId=default_BestsellerId_tyy%2F4io&srno=s_1_1&otracker=search&fm=organic&iid=74a3ea84-8bc2-48dd-a5ce-7acf4a6b9fbb.MOBH4DQFG8NKFRDY.SEARCH&ppt=sp&ppn=sp&ssid=v4q0hv2yz40000001749311023735&qH=8e0ee2dac8c1afb1" 
    
    print("=== Testing Amazon Product ===")
    try:
        product_data = scrape_product(amazon_url)
        save_product_json(product_data, "amazon_product.json")
        print("Amazon product data saved to amazon_product.json")
        print(f"Product: {product_data.product_title}")
        print(f"Price: {product_data.price}")
        print(f"Brand: {product_data.brand}")
        if hasattr(product_data, 'asin'):
            print(f"ASIN: {product_data.asin}")
        print()
    except Exception as e:
        print(f"Amazon Error: {str(e)}")
        print()

    print("=== Testing Flipkart Product ===")
    print("To test Flipkart, replace the flipkart_url variable with a valid Flipkart product URL")
    print("Example: flipkart_url = 'https://www.flipkart.com/apple-iphone-16-black-128-gb/p/itmb07d67f995271?pid=MOBH4DQFG8NKFRDY&lid=LSTMOBH4DQFG8NKFRDYNBDOZI&marketplace=FLIPKART&q=iPhone+16&store=tyy%2F4io&spotlightTagId=default_BestsellerId_tyy%2F4io&srno=s_1_1&otracker=search&fm=organic&iid=74a3ea84-8bc2-48dd-a5ce-7acf4a6b9fbb.MOBH4DQFG8NKFRDY.SEARCH&ppt=sp&ppn=sp&ssid=v4q0hv2yz40000001749311023735&qH=8e0ee2dac8c1afb1'")

    try:
        flipkart_product = scrape_product(flipkart_url)
        save_product_json(flipkart_product, "flipkart_product.json")
        print("Flipkart product data saved to flipkart_product.json")
        print(f"Product: {flipkart_product.product_title}")
        print(f"Price: {flipkart_product.price}")
        print(f"Brand: {flipkart_product.brand}")
        if flipkart_product.rating:
            print(f"Rating: {flipkart_product.rating}")
        if flipkart_product.discount:
            print(f"Discount: {flipkart_product.discount}")
    except Exception as e:
        print(f"Flipkart Error: {str(e)}")

# url=None markdown=None html=None rawHtml=None links=None extract=None json={'product_title': 'iPhone 16 128 GB: 5G Mobile Phone with Camera Control, A18 Chip and a Big Boost in Battery Life. Works with AirPods; Teal', 'price': '₹73,500.00', 'offers': ['Upto ₹4,000.00 discount on select Credit Cards', 'Upto ₹3,311.61 EMI interest savings on select Credit Cards', 'Upto ₹2,205.00 cashback as Amazon Pay Balance when you pay with Amazon Pay ICICI Bank Credit Cards', 'Get GST invoice and save up to 28% on business purchases.'], 'brand': 'Apple', 'asin': 'B0DGJH8RYG'} screenshot=None metadata={'description': 'iPhone 16 128 GB: 5G Mobile Phone with Camera Control, A18 Chip and a Big Boost in Battery Life. Works with AirPods; Teal : Amazon.in: Electronics', 'language': 'en-in', 'encrypted-slate-token': 'AnYxbzDtDPxAN0HMl/dA4TyuoLR8eFmvl4A4TA/42EqLZhpJWuA1sfctoNxKyrB5lhJJyFi0DoZOgsHtxdn49t0RAa3mCOF2hug+NGlqQJYuQ0plnNIqbepsiXaOJWlpP/GNsvqfMQ6/enYhrDsPDiWiGTBeZjGbX4jNO668IewJgZiDsKAdEgmDZEuUGiRTnr1P9DI/0F7nJ+vdInJMfil8mOob7F8PAzwlR5M/qp6hEkqfzyDAm8TNVyQfYXk9FqhwAHic+yMN/GSG8a3rXg==', 'title': 'iPhone 16 128 GB: 5G Mobile Phone with Camera Control, A18 Chip and a Big Boost in Battery Life. Works with AirPods; Teal : Amazon.in: Electronics', 'scrapeId': '325ea130-13ed-4f3c-9c49-2b632f4a2c89', 'sourceURL': 'https://www.amazon.in/dp/B0DGJH8RYG', 'url': 'https://www.amazon.in/dp/B0DGJH8RYG?th=1', 'statusCode': 200, 'contentType': 'text/html;charset=UTF-8', 'proxyUsed': 'basic'} actions=None title=None description=None changeTracking=None success=True warning=None error=None
# Amazon product data saved to amazon_product.json
# Product: iPhone 16 128 GB: 5G Mobile Phone with Camera Control, A18 Chip and a Big Boost in Battery Life. Works with AirPods; Teal
# Price: ₹73,500.00
# Brand: Apple
# ASIN: B0DGJH8RYG

# === Testing Flipkart Product ===
# To test Flipkart, replace the flipkart_url variable with a valid Flipkart product URL
# Example: flipkart_url = 'https://www.flipkart.com/apple-iphone-16-black-128-gb/p/itmb07d67f995271?pid=MOBH4DQFG8NKFRDY&lid=LSTMOBH4DQFG8NKFRDYNBDOZI&marketplace=FLIPKART&q=iPhone+16&store=tyy%2F4io&spotlightTagId=default_BestsellerId_tyy%2F4io&srno=s_1_1&otracker=search&fm=organic&iid=74a3ea84-8bc2-48dd-a5ce-7acf4a6b9fbb.MOBH4DQFG8NKFRDY.SEARCH&ppt=sp&ppn=sp&ssid=v4q0hv2yz40000001749311023735&qH=8e0ee2dac8c1afb1'
# url=None markdown=None html=None rawHtml=None links=None extract=None json={'product_title': 'Apple iPhone 16 (Black, 128 GB)', 'price': '₹74,900', 'original_price': '₹79,900', 'discount': '6% off', 'offers': ['5% Unlimited Cashback on Flipkart Axis Bank Credit Card', '₹2500 Off On Flipkart Axis Bank Credit Card Non EMI Transactions.', '₹4000 Off On All Banks Credit Card Transactions.', 'Get extra ₹5000 off (price inclusive of cashback/coupon)'], 'brand': 'Apple', 'rating': '4.6', 'reviews_count': '17,203 Ratings & 725 Reviews'} screenshot=None metadata={'twitter:app:country': 'in', 'og_url': 'https://www.flipkart.com/apple-iphone-16-black-128-gb/p/itmb07d67f995271', 'og_title': 'Apple iPhone 16 (Black, 128 GB)', 'twitter:app:url:googleplay': 'http://dl.flipkart.com/dl/home?', 'og_image': 'http://rukmini1.flixcart.com/image/300/300/xif0q/mobile/8/w/5/-original-imah4jyfwr3bfjbg.jpeg', 'twitter:app:url:iphone': 'http://dl.flipkart.com/dl/home?', 'twitter:image': 'http://rukmini1.flixcart.com/image/300/300/xif0q/mobile/8/w/5/-original-imah4jyfwr3bfjbg.jpeg', 'ogImage': 'http://rukmini1.flixcart.com/image/300/300/xif0q/mobile/8/w/5/-original-imah4jyfwr3bfjbg.jpeg', 'ogDescription': 'Buy Apple iPhone 16 online at best price with offers in India. Apple iPhone 16 (Black, 128 GB) features and specifications include 128 GB ROM, 48 MP back camera and 12 MP front camera. Compare iPhone 16 by price and performance to shop at Flipkart', 'twitter:card': 'app', 'twitter:app:name:ipad': 'Flipkart', 'twitter:site': '@flipkart', 'og_site_name': 'Flipkart.com', 'twitter:creator': '@flipkart', 'fb:page_id': '102988293558', 'twitter:app:url:ipad': 'http://dl.flipkart.com/dl/home?', 'twitter:app:name:googleplay': 'Flipkart', 'al:ios:app_name': 'Flipkart', 'title': 'Apple iPhone 16 (Black, 128 GB)', 'fb:admins': '658873552,624500995,100000233612389', 'favicon': 'https://static-assets-web.flixcart.com/www/promos/new/20150528-140547-favicon-retina.ico', 'ogUrl': 'https://www.flipkart.com/apple-iphone-16-black-128-gb/p/itmb07d67f995271', 'ogSiteName': 'Flipkart.com', 'og:type': 'website', 'twitter:description': 'Shop for electronics, apparels & more using our Flipkart app Free shipping & COD.', 'twitter:app:name:iphone': 'Flipkart', 'twitter:app:id:iphone': '742044692', 'twitter:app:id:googleplay': 'com.flipkart.android', 'og:description': 'Buy Apple iPhone 16 online at best price with offers in India. Apple iPhone 16 (Black, 128 GB) features and specifications include 128 GB ROM, 48 MP back camera and 12 MP front camera. Compare iPhone 16 by price and performance to shop at Flipkart', 'msvalidate.01': 'F4EEB3A0AFFDD385992A06E6920C0AC3', 'ogTitle': 'Apple iPhone 16 (Black, 128 GB)', 'twitter:app:id:ipad': '742044692', 'language': 'en', 'twitter:title': 'Apple iPhone 16 (Black, 128 GB)', 'Description': 'Buy Apple iPhone 16 online at best price with offers in India. Apple iPhone 16 (Black, 128 GB) features and specifications include 128 GB ROM, 48 MP back camera and 12 MP front camera. Compare iPhone 16 by price and performance to shop at Flipkart', 'al:ios:app_store_id': '742044692', 'scrapeId': '4f5b8782-5037-4142-bdf9-3eac110e4948', 'sourceURL': 'https://www.flipkart.com/apple-iphone-16-black-128-gb/p/itmb07d67f995271?pid=MOBH4DQFG8NKFRDY&lid=LSTMOBH4DQFG8NKFRDYNBDOZI&marketplace=FLIPKART&q=iPhone+16&store=tyy%2F4io&spotlightTagId=default_BestsellerId_tyy%2F4io&srno=s_1_1&otracker=search&fm=organic&iid=74a3ea84-8bc2-48dd-a5ce-7acf4a6b9fbb.MOBH4DQFG8NKFRDY.SEARCH&ppt=sp&ppn=sp&ssid=v4q0hv2yz40000001749311023735&qH=8e0ee2dac8c1afb1', 'url': 'https://www.flipkart.com/apple-iphone-16-black-128-gb/p/itmb07d67f995271?pid=MOBH4DQFG8NKFRDY&lid=LSTMOBH4DQFG8NKFRDYNBDOZI&marketplace=FLIPKART&q=iPhone+16&store=tyy%2F4io&spotlightTagId=default_BestsellerId_tyy%2F4io&srno=s_1_1&otracker=search&fm=organic&iid=74a3ea84-8bc2-48dd-a5ce-7acf4a6b9fbb.MOBH4DQFG8NKFRDY.SEARCH&ppt=sp&ppn=sp&ssid=v4q0hv2yz40000001749311023735&qH=8e0ee2dac8c1afb1', 'statusCode': 200, 'contentType': 'text/html; charset=utf-8', 'proxyUsed': 'basic'} actions=None title=None description=None changeTracking=None success=True warning=None error=None
# Flipkart product data saved to flipkart_product.json
# Product: Apple iPhone 16 (Black, 128 GB)
# Price: ₹74,900
# Brand: Apple
# Rating: 4.6
# Discount: 6% off