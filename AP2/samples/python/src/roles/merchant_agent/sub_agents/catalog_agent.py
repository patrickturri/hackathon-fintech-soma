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

"""A sub-agent that offers items from its 'catalog'.

This agent can use Best Buy API for real products or generate mock products.
"""

from datetime import datetime
from datetime import timedelta
from datetime import timezone
from typing import Any

from a2a.server.tasks.task_updater import TaskUpdater
from a2a.types import DataPart
from a2a.types import Part
from a2a.types import Task
from a2a.types import TextPart
from google import genai
from pydantic import ValidationError

from .. import storage
from ..bestbuy_client import BestBuyClient
from ..bestbuy_client import BestBuyProduct
from ap2.types.mandate import CART_MANDATE_DATA_KEY
from ap2.types.mandate import CartContents
from ap2.types.mandate import CartMandate
from ap2.types.mandate import INTENT_MANDATE_DATA_KEY
from ap2.types.mandate import IntentMandate
from ap2.types.payment_request import PaymentDetailsInit
from ap2.types.payment_request import PaymentItem
from ap2.types.payment_request import PaymentMethodData
from ap2.types.payment_request import PaymentOptions
from ap2.types.payment_request import PaymentRequest
from common import message_utils
from common.system_utils import DEBUG_MODE_INSTRUCTIONS


async def find_items_workflow(
    data_parts: list[dict[str, Any]],
    updater: TaskUpdater,
    current_task: Task | None,
) -> None:
  """Finds products that match the user's IntentMandate using Best Buy API."""
  intent_mandate = message_utils.parse_canonical_object(
      INTENT_MANDATE_DATA_KEY, data_parts, IntentMandate
  )
  intent = intent_mandate.natural_language_description

  # Initialize Best Buy client (will use demo mode if no API key)
  bestbuy_client = BestBuyClient()

  try:
    # Search Best Buy for matching products (fetch extra for filtering)
    products = await bestbuy_client.search_products(
        query=intent,
        max_results=3,
        fetch_extra=15,
    )

    current_time = datetime.now(timezone.utc)

    if products:
      # Use LLM to filter for most relevant products
      try:
        relevant_products = await _filter_relevant_products(
            products, intent, max_results=3
        )
      except Exception as e:
        print(f"[Catalog Agent] LLM filtering failed: {e}, using first 3 products")
        relevant_products = products[:3]

      # If no products after filtering, use first 3
      if not relevant_products:
        print(f"[Catalog Agent] No products after filtering, using first 3")
        relevant_products = products[:3]

      # Use real Best Buy products
      item_count = 0
      for product in relevant_products:
        item_count += 1
        # Convert Best Buy product to PaymentItem
        payment_item = PaymentItem(
            label=product.name,
            amount={
                "currency": "USD",
                "value": str(product.salePrice),
            },
        )
        await _create_and_add_cart_mandate_artifact(
            payment_item,
            item_count,
            current_time,
            updater,
            merchant_name="Best Buy",
            product_description=product.shortDescription,
            product_image=product.image,
            product_url=product.url,
        )
    else:
      # Fallback to LLM-generated products if Best Buy returns nothing
      await _generate_fallback_products(intent, current_time, updater)

    risk_data = _collect_risk_data(updater)
    updater.add_artifact([
        Part(root=DataPart(data={"risk_data": risk_data})),
    ])
    await updater.complete()

  except Exception as e:
    error_message = updater.new_agent_message(
        parts=[Part(root=TextPart(text=f"Error finding products: {e}"))]
    )
    await updater.failed(message=error_message)
    return
  finally:
    await bestbuy_client.close()


def _extract_keywords(intent: str) -> list[str]:
  """Extract key search terms from query.

  Args:
    intent: User's search query

  Returns:
    List of important keywords
  """
  # Remove common stopwords
  stopwords = {"the", "a", "an", "for", "with", "my", "best", "good", "cheap", "find", "show", "me"}
  words = intent.lower().split()
  keywords = [w for w in words if w not in stopwords and len(w) > 2]
  return keywords


async def _filter_relevant_products(
    products: list[BestBuyProduct],
    intent: str,
    max_results: int = 3,
) -> list[BestBuyProduct]:
  """Filter products for relevance using LLM.

  Args:
    products: List of products from Best Buy API
    intent: User's search intent
    max_results: Number of products to return

  Returns:
    Filtered list of most relevant products
  """
  if len(products) <= max_results:
    return products

  llm_client = genai.Client()

  # Extract keywords from the search intent
  keywords = _extract_keywords(intent)
  keywords_str = ", ".join(keywords)

  # Create a numbered list of products for the LLM
  product_list = []
  for idx, product in enumerate(products):
    product_list.append({
        "index": idx,
        "name": product.name,
        "price": product.salePrice,
        "description": product.shortDescription or "",
    })

  prompt = f"""Filter product search results for: "{intent}"

Key search terms: {keywords_str}

Available products:
{'\n'.join([f"{i}. {p['name']} (${p['price']})" for i, p in enumerate(product_list)])}

STRICT MATCHING RULES:
1. Product name MUST contain the main search terms from: {keywords_str}
2. Example: "USB cables" requires BOTH "USB" AND "cable" in product name
3. Example: "USB hard drive" has "USB" but NOT "cable" → REJECT for "USB cables" search
4. Prioritize products where ALL keywords match

EXCLUSION RULES (unless user explicitly searches for these):
- If user wants a DEVICE (laptop, TV, phone): EXCLUDE accessories, cables, cases, chargers, filters
- If user wants ACCESSORIES (cables, chargers): ONLY select those, EXCLUDE devices
- ALWAYS exclude: warranties, service plans, replacement parts, refills

EXAMPLES:
User searches "USB cables":
  ✓ "Anker USB-C to USB-C Cable 6ft" (has USB + cable)
  ✗ "WD External USB 3.0 Hard Drive" (has USB but NOT cable)
  ✗ "HDMI Cable 10ft" (has cable but NOT USB)

User searches "MacBook":
  ✓ "Apple MacBook Air 13-inch M2"
  ✗ "MacBook Pro USB-C Charging Cable"
  ✗ "MacBook Case Hard Shell"

User searches "refrigerator":
  ✓ "Samsung 25 Cu. Ft. French Door Refrigerator"
  ✗ "Refrigerator Water Filter"
  ✗ "Refrigerator Air Filter Replacement"

Return ONLY the indices (0-based) of the {max_results} BEST MATCHING products as a JSON array.
If fewer than {max_results} match well, return fewer indices.
Example response: [0, 5, 12]
"""

  try:
    llm_response = llm_client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config={
            "response_mime_type": "application/json",
            "response_schema": list[int],
        }
    )

    selected_indices: list[int] = llm_response.parsed
    print(f"[Relevance Filter] Selected indices: {selected_indices}")

    # Return selected products
    relevant_products = []
    for idx in selected_indices:
      if 0 <= idx < len(products):
        relevant_products.append(products[idx])
        print(f"[Relevance Filter] Selected: {products[idx].name} - ${products[idx].salePrice}")

    return relevant_products if relevant_products else products[:max_results]

  except Exception as e:
    print(f"[Relevance Filter] Error: {e}, returning first {max_results} products")
    return products[:max_results]


async def _generate_fallback_products(
    intent: str,
    current_time: datetime,
    updater: TaskUpdater,
) -> None:
  """Generate products using LLM as fallback."""
  llm_client = genai.Client()

  prompt = f"""
        Based on the user's request for '{intent}', your task is to generate 3
        complete, unique and realistic PaymentItem JSON objects.

        You MUST exclude all branding from the PaymentItem `label` field.

    %s
        """ % DEBUG_MODE_INSTRUCTIONS

  llm_response = llm_client.models.generate_content(
      model="gemini-2.5-flash",
      contents=prompt,
      config={
          "response_mime_type": "application/json",
          "response_schema": list[PaymentItem],
      }
  )

  items: list[PaymentItem] = llm_response.parsed
  item_count = 0
  for item in items:
    item_count += 1
    await _create_and_add_cart_mandate_artifact(
        item, item_count, current_time, updater
    )


async def _create_and_add_cart_mandate_artifact(
    item: PaymentItem,
    item_count: int,
    current_time: datetime,
    updater: TaskUpdater,
    merchant_name: str = "Generic Merchant",
    product_description: str | None = None,
    product_image: str | None = None,
    product_url: str | None = None,
) -> None:
  """Creates a CartMandate and adds it as an artifact."""
  payment_request = PaymentRequest(
      method_data=[
          PaymentMethodData(
              supported_methods="CARD",
              data={
                  "network": ["mastercard", "paypal", "amex"],
              },
          )
      ],
      details=PaymentDetailsInit(
          id=f"order_{item_count}",
          display_items=[item],
          total=PaymentItem(
              label="Total",
              amount=item.amount,
          ),
      ),
      options=PaymentOptions(request_shipping=True),
  )

  cart_contents = CartContents(
      id=f"cart_{item_count}",
      user_cart_confirmation_required=True,
      payment_request=payment_request,
      cart_expiry=(current_time + timedelta(minutes=30)).isoformat(),
      merchant_name=merchant_name,
  )

  cart_mandate = CartMandate(contents=cart_contents)

  # Store additional metadata for the product
  metadata = {
      "description": product_description,
      "image": product_image,
      "url": product_url,
  }
  storage.set_cart_metadata(cart_mandate.contents.id, metadata)

  storage.set_cart_mandate(cart_mandate.contents.id, cart_mandate)

  # Add both cart mandate and metadata as separate data parts
  artifact_data = {
      CART_MANDATE_DATA_KEY: cart_mandate.model_dump(),
      f"{CART_MANDATE_DATA_KEY}.metadata": metadata,
  }

  await updater.add_artifact([
      Part(root=DataPart(data=artifact_data))
  ])


def _collect_risk_data(updater: TaskUpdater) -> dict:
  """Creates a risk_data in the tool_context."""
  # This is a fake risk data for demonstration purposes.
  risk_data = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...fake_risk_data"
  storage.set_risk_data(updater.context_id, risk_data)
  return risk_data
