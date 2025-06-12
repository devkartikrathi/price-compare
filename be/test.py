from firecrawl import FirecrawlApp
from pydantic import BaseModel, Field
import os
from dotenv import load_dotenv
load_dotenv()

# app = FirecrawlApp(api_key=os.getenv("FIRECRAWL_API_KEY"))

# class ExtractSchema(BaseModel):
#     title: str
#     price: str
#     url: str

# data = app.extract(["https://www.amazon.in/s?k=iPhone+16"
# ], prompt='Give me the top 5 products from the search results with their titles, prices, and urls', schema=ExtractSchema.model_json_schema()).data
# print(data)

# from firecrawl import FirecrawlApp
# import os
# from dotenv import load_dotenv
# load_dotenv()

# # Initialize the client with your API key
# app = FirecrawlApp(api_key=os.getenv("FIRECRAWL_API_KEY"))

# search_result = app.search("https://www.amazon.in/s?k=iPhone+16", limit=5)
# print(search_result)