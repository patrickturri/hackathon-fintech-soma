# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Best Buy API client for fetching real product data."""

import os
from typing import Any
import httpx
from pydantic import BaseModel
from google import genai


class BestBuyProduct(BaseModel):
    """Represents a product from Best Buy API."""
    sku: int
    name: str
    salePrice: float
    regularPrice: float | None = None
    manufacturer: str | None = None
    modelNumber: str | None = None
    shortDescription: str | None = None
    image: str | None = None
    url: str | None = None
    customerReviewAverage: float | None = None
    inStoreAvailability: bool | None = None
    onlineAvailability: bool | None = None


class BestBuyClient:
    """Client for interacting with Best Buy Products API."""

    BASE_URL = "https://api.bestbuy.com/v1"

    # Best Buy category IDs for major product types
    CATEGORY_MAP = {
        "computers": "abcat0500000",  # All Computers & Tablets
        "laptops": "abcat0502000",  # Laptops
        "desktops": "abcat0501000",  # Desktops
        "tablets": "pcmcat209000050006",  # Tablets
        "tvs": "abcat0101000",  # TVs & Home Theater
        "appliances": "abcat0900000",  # Appliances
        "refrigerators": "abcat0901000",  # Refrigerators
        "headphones": "abcat0204000",  # Headphones
        "cameras": "abcat0401000",  # Cameras & Camcorders
        "phones": "abcat0800000",  # Cell Phones
        "gaming": "abcat0700000",  # Video Games
        "audio": "abcat0200000",  # Audio
        "smart_home": "pcmcat1496256099917",  # Smart Home
        "wearables": "pcmcat332000050000",  # Wearable Technology
        "coffee_makers": "pcmcat367400050001",  # Coffee Makers
    }

    def __init__(self, api_key: str | None = None):
        """Initialize the Best Buy API client.

        Args:
            api_key: Best Buy API key. If None, uses BESTBUY_API_KEY env var.
                    If no key available, uses demo mode with mock data.
        """
        self.api_key = api_key or os.getenv("BESTBUY_API_KEY")
        self.demo_mode = self.api_key is None
        self.client = httpx.AsyncClient(timeout=10.0)
        self.llm_client = None  # Lazy initialize for category detection

    async def _detect_category(self, query: str) -> str | None:
        """Use LLM to detect the best product category for a search query.

        Args:
            query: Natural language search query

        Returns:
            Best Buy category ID or None if no good match
        """
        if self.llm_client is None:
            self.llm_client = genai.Client()

        # Create list of available categories
        category_list = "\n".join([f"- {key}: {desc}" for key, desc in [
            ("computers", "All computers and tablets"),
            ("laptops", "Laptop computers"),
            ("desktops", "Desktop computers"),
            ("tablets", "Tablets and iPads"),
            ("tvs", "Televisions and home theater"),
            ("appliances", "Home appliances"),
            ("refrigerators", "Refrigerators and freezers"),
            ("headphones", "Headphones and earbuds"),
            ("cameras", "Cameras and camcorders"),
            ("phones", "Cell phones and smartphones"),
            ("gaming", "Video games and gaming consoles"),
            ("audio", "Audio equipment and speakers"),
            ("smart_home", "Smart home devices"),
            ("wearables", "Wearable technology like smartwatches"),
            ("coffee_makers", "Coffee makers and espresso machines"),
        ]])

        prompt = f"""Given this product search query: "{query}"

Select the MOST SPECIFIC category that matches the user's intent from these options:

{category_list}

Rules:
1. Choose the MOST SPECIFIC category (e.g., "desktops" instead of "computers" if they want a desktop)
2. If the query mentions "laptop", choose "laptops"
3. If the query mentions "desktop" or "tower", choose "desktops"
4. If the query is generic like "computer for work", choose "computers" (broader category)
5. Return ONLY the category key (e.g., "desktops"), not the description
6. If none match well, return "none"

Return only the category key as a single word.
"""

        try:
            response = self.llm_client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
            )

            category_key = response.text.strip().lower()
            print(f"[Category Detection] Query: '{query}' → Category: '{category_key}'")

            if category_key in self.CATEGORY_MAP:
                return self.CATEGORY_MAP[category_key]
            else:
                print(f"[Category Detection] No valid category found")
                return None

        except Exception as e:
            print(f"[Category Detection] Error: {e}")
            return None

    async def search_products(
        self,
        query: str,
        max_results: int = 3,
        min_price: float | None = None,
        max_price: float | None = None,
        fetch_extra: int = 15,
    ) -> list[BestBuyProduct]:
        """Search for products matching a query.

        Args:
            query: Natural language search query (e.g., "coffee maker")
            max_results: Maximum number of results to return (default 3)
            min_price: Minimum price filter (optional)
            max_price: Maximum price filter (optional)
            fetch_extra: Number of products to fetch for filtering (default 15)

        Returns:
            List of BestBuyProduct objects (filtered for relevance)
        """
        if self.demo_mode:
            return self._get_demo_products(query, max_results)

        # Detect category for better search results
        category_id = await self._detect_category(query)

        # Build search criteria
        search_criteria = [f'search={query}']

        # Add category filter if detected
        if category_id:
            search_criteria.append(f'categoryPath.id={category_id}')
            print(f"[BestBuy API] Using category filter: {category_id}")

        # Filter out service/warranty products (type=hardgood excludes warranties)
        search_criteria.append('type=hardgood')

        # Set minimum price based on query type or user preference
        effective_min_price = min_price if min_price is not None else 50
        search_criteria.append(f'salePrice>={effective_min_price}')

        if max_price is not None:
            search_criteria.append(f'salePrice<={max_price}')

        # Join criteria with &
        criteria = '&'.join(search_criteria)

        # Fields to return
        show_fields = (
            "sku,name,salePrice,regularPrice,manufacturer,modelNumber,"
            "shortDescription,image,url,customerReviewAverage,"
            "inStoreAvailability,onlineAvailability"
        )

        # Fetch more products than needed for filtering
        fetch_count = max(fetch_extra, max_results * 3)

        # Sort by customer reviews (most popular products first)
        # This gets actual products, not accessories
        url = (
            f"{self.BASE_URL}/products({criteria})"
            f"?apiKey={self.api_key}"
            f"&format=json"
            f"&show={show_fields}"
            f"&pageSize={fetch_count}"
            f"&sort=customerReviewCount.desc"  # Most reviewed = most popular
        )

        try:
            print(f"[BestBuy API] Searching for: {query}")
            print(f"[BestBuy API] URL: {url}")

            response = await self.client.get(url)
            response.raise_for_status()
            data = response.json()

            print(f"[BestBuy API] Total results: {data.get('total', 0)}")

            products = []
            for product_data in data.get("products", []):
                try:
                    product = BestBuyProduct(**product_data)
                    print(f"[BestBuy API] Found: {product.name} - ${product.salePrice}")
                    products.append(product)
                except Exception as e:
                    print(f"[BestBuy API] Error parsing product: {e}")
                    continue

            if not products:
                print(f"[BestBuy API] No products found, falling back to demo mode")
                return self._get_demo_products(query, max_results)

            print(f"[BestBuy API] Fetched {len(products)} products, returning top {max_results}")
            # Return fetched products - filtering will happen in catalog_agent
            return products

        except Exception as e:
            print(f"[BestBuy API] Error: {e}")
            # Fallback to demo mode on error
            return self._get_demo_products(query, max_results)

    def _get_demo_products(self, query: str, count: int = 3) -> list[BestBuyProduct]:
        """Generate demo products when API key is not available.

        This provides realistic-looking data for testing without an API key.
        """
        query_lower = query.lower()

        # Demo product database organized by category
        demo_catalog = {
            "coffee": [
                BestBuyProduct(
                    sku=6446101,
                    name="Keurig K-Elite Single-Serve K-Cup Pod Coffee Maker",
                    salePrice=169.99,
                    regularPrice=189.99,
                    manufacturer="Keurig",
                    modelNumber="K90",
                    shortDescription="Brew your favorite coffee, tea, hot cocoa and more with this Keurig K-Elite coffee maker.",
                    image="https://pisces.bbystatic.com/image2/BestBuy_US/images/products/6446/6446101_sd.jpg",
                    url="https://www.bestbuy.com/site/6446101.p",
                    customerReviewAverage=4.5,
                    inStoreAvailability=True,
                    onlineAvailability=True,
                ),
                BestBuyProduct(
                    sku=6120833,
                    name="Ninja 12-Cup Programmable Coffee Maker",
                    salePrice=89.99,
                    regularPrice=99.99,
                    manufacturer="Ninja",
                    modelNumber="CE251",
                    shortDescription="Classic coffee maker with advanced features for a perfect cup every time.",
                    image="https://pisces.bbystatic.com/image2/BestBuy_US/images/products/6120/6120833_sd.jpg",
                    url="https://www.bestbuy.com/site/6120833.p",
                    customerReviewAverage=4.7,
                    inStoreAvailability=True,
                    onlineAvailability=True,
                ),
                BestBuyProduct(
                    sku=6372886,
                    name="Mr. Coffee 5-Cup Mini Brew Coffee Maker",
                    salePrice=24.99,
                    regularPrice=29.99,
                    manufacturer="Mr. Coffee",
                    modelNumber="BVMC-PSTX",
                    shortDescription="Compact coffee maker perfect for small spaces.",
                    image="https://pisces.bbystatic.com/image2/BestBuy_US/images/products/6372/6372886_sd.jpg",
                    url="https://www.bestbuy.com/site/6372886.p",
                    customerReviewAverage=4.2,
                    inStoreAvailability=True,
                    onlineAvailability=True,
                ),
            ],
            "laptop": [
                BestBuyProduct(
                    sku=6534616,
                    name="MacBook Air 13.6\" Laptop - Apple M2 chip - 8GB Memory - 256GB SSD",
                    salePrice=999.99,
                    regularPrice=1199.99,
                    manufacturer="Apple",
                    modelNumber="MLY33LL/A",
                    shortDescription="Supercharged by M2 chip for incredible performance.",
                    image="https://pisces.bbystatic.com/image2/BestBuy_US/images/products/6534/6534616_sd.jpg",
                    url="https://www.bestbuy.com/site/6534616.p",
                    customerReviewAverage=4.8,
                    inStoreAvailability=True,
                    onlineAvailability=True,
                ),
                BestBuyProduct(
                    sku=6515649,
                    name="HP 15.6\" Touch-Screen Laptop - Intel Core i5 - 8GB Memory - 256GB SSD",
                    salePrice=499.99,
                    regularPrice=599.99,
                    manufacturer="HP",
                    modelNumber="15-dy2795wm",
                    shortDescription="Reliable performance for everyday computing.",
                    image="https://pisces.bbystatic.com/image2/BestBuy_US/images/products/6515/6515649_sd.jpg",
                    url="https://www.bestbuy.com/site/6515649.p",
                    customerReviewAverage=4.3,
                    inStoreAvailability=True,
                    onlineAvailability=True,
                ),
                BestBuyProduct(
                    sku=6542175,
                    name="Dell Inspiron 2-in-1 14\" Touch-Screen Laptop - Intel Core i7 - 16GB Memory",
                    salePrice=799.99,
                    regularPrice=999.99,
                    manufacturer="Dell",
                    modelNumber="I7420-7683BLU-PUS",
                    shortDescription="Versatile 2-in-1 design for work and entertainment.",
                    image="https://pisces.bbystatic.com/image2/BestBuy_US/images/products/6542/6542175_sd.jpg",
                    url="https://www.bestbuy.com/site/6542175.p",
                    customerReviewAverage=4.6,
                    inStoreAvailability=False,
                    onlineAvailability=True,
                ),
            ],
            "headphones": [
                BestBuyProduct(
                    sku=6505727,
                    name="Sony WH-1000XM5 Wireless Noise-Cancelling Over-the-Ear Headphones",
                    salePrice=349.99,
                    regularPrice=399.99,
                    manufacturer="Sony",
                    modelNumber="WH1000XM5/B",
                    shortDescription="Industry-leading noise cancellation with premium sound quality.",
                    image="https://pisces.bbystatic.com/image2/BestBuy_US/images/products/6505/6505727_sd.jpg",
                    url="https://www.bestbuy.com/site/6505727.p",
                    customerReviewAverage=4.9,
                    inStoreAvailability=True,
                    onlineAvailability=True,
                ),
                BestBuyProduct(
                    sku=6447909,
                    name="Apple AirPods Pro (2nd generation) with MagSafe Case",
                    salePrice=199.99,
                    regularPrice=249.99,
                    manufacturer="Apple",
                    modelNumber="MTJV3AM/A",
                    shortDescription="Active Noise Cancellation and Transparency mode.",
                    image="https://pisces.bbystatic.com/image2/BestBuy_US/images/products/6447/6447909_sd.jpg",
                    url="https://www.bestbuy.com/site/6447909.p",
                    customerReviewAverage=4.8,
                    inStoreAvailability=True,
                    onlineAvailability=True,
                ),
                BestBuyProduct(
                    sku=6428457,
                    name="Beats Studio3 Wireless Noise Cancelling Over-Ear Headphones",
                    salePrice=199.99,
                    regularPrice=349.99,
                    manufacturer="Beats by Dr. Dre",
                    modelNumber="MX3X2LL/A",
                    shortDescription="Pure adaptive noise canceling with premium sound.",
                    image="https://pisces.bbystatic.com/image2/BestBuy_US/images/products/6428/6428457_sd.jpg",
                    url="https://www.bestbuy.com/site/6428457.p",
                    customerReviewAverage=4.5,
                    inStoreAvailability=True,
                    onlineAvailability=True,
                ),
            ],
            "tv": [
                BestBuyProduct(
                    sku=6536735,
                    name='Samsung 65" Class QLED 4K UHD Smart Tizen TV',
                    salePrice=897.99,
                    regularPrice=1299.99,
                    manufacturer="Samsung",
                    modelNumber="QN65Q60CAFXZA",
                    shortDescription="Quantum Dot technology for brilliant colors.",
                    image="https://pisces.bbystatic.com/image2/BestBuy_US/images/products/6536/6536735_sd.jpg",
                    url="https://www.bestbuy.com/site/6536735.p",
                    customerReviewAverage=4.6,
                    inStoreAvailability=True,
                    onlineAvailability=True,
                ),
                BestBuyProduct(
                    sku=6522019,
                    name='LG 55" Class OLED evo C3 Series Smart TV',
                    salePrice=1299.99,
                    regularPrice=1799.99,
                    manufacturer="LG",
                    modelNumber="OLED55C3PUA",
                    shortDescription="Self-lit OLED pixels for perfect black and infinite contrast.",
                    image="https://pisces.bbystatic.com/image2/BestBuy_US/images/products/6522/6522019_sd.jpg",
                    url="https://www.bestbuy.com/site/6522019.p",
                    customerReviewAverage=4.8,
                    inStoreAvailability=False,
                    onlineAvailability=True,
                ),
                BestBuyProduct(
                    sku=6501901,
                    name='TCL 50" Class S4 4K UHD HDR LED Smart TV with Google TV',
                    salePrice=249.99,
                    regularPrice=329.99,
                    manufacturer="TCL",
                    modelNumber="50S450G",
                    shortDescription="Stunning 4K picture quality at an incredible value.",
                    image="https://pisces.bbystatic.com/image2/BestBuy_US/images/products/6501/6501901_sd.jpg",
                    url="https://www.bestbuy.com/site/6501901.p",
                    customerReviewAverage=4.4,
                    inStoreAvailability=True,
                    onlineAvailability=True,
                ),
            ],
        }

        # Find matching category
        for category, products in demo_catalog.items():
            if category in query_lower:
                return products[:count]

        # Default: return first available products
        all_products = []
        for products in demo_catalog.values():
            all_products.extend(products)
        return all_products[:count]

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
