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

"""Tools used by the shopper subagent.

Each agent uses individual tools to handle distinct tasks throughout the
shopping and purchasing process.
"""

from datetime import datetime
from datetime import timedelta
from datetime import timezone

from a2a.types import Artifact
from google.adk.tools.tool_context import ToolContext

from ap2.types.mandate import CART_MANDATE_DATA_KEY
from ap2.types.mandate import CartMandate
from ap2.types.mandate import INTENT_MANDATE_DATA_KEY
from ap2.types.mandate import IntentMandate
from common.a2a_message_builder import A2aMessageBuilder
from common.artifact_utils import find_canonical_objects
from roles.shopping_agent.remote_agents import merchant_agent_client


def create_intent_mandate(
    natural_language_description: str,
    user_cart_confirmation_required: bool,
    merchants: list[str],
    skus: list[str],
    requires_refundability: bool,
    tool_context: ToolContext,
) -> IntentMandate:
  """Creates an IntentMandate object.

  Args:
    natural_language_description: The description of the user's intent.
    user_cart_confirmation_required: If the user must confirm the cart.
    merchants: A list of allowed merchants.
    skus: A list of allowed SKUs.
    requires_refundability: If the items must be refundable.
    tool_context: The ADK supplied tool context.

  Returns:
    An IntentMandate object valid for 1 day.
  """
  intent_mandate = IntentMandate(
      natural_language_description=natural_language_description,
      user_cart_confirmation_required=user_cart_confirmation_required,
      merchants=merchants,
      skus=skus,
      requires_refundability=requires_refundability,
      intent_expiry=(
          datetime.now(timezone.utc) + timedelta(days=1)
      ).isoformat(),
  )
  tool_context.state["intent_mandate"] = intent_mandate
  return intent_mandate


async def find_products(
    tool_context: ToolContext, debug_mode: bool = False
) -> str:
  """Calls the merchant agent to find products matching the user's intent.

  Args:
    tool_context: The ADK supplied tool context.
    debug_mode: Whether the agent is in debug mode.

  Returns:
    A formatted string with product details including images in Markdown.

  Raises:
    RuntimeError: If the merchant agent fails to provide products.
  """
  intent_mandate = tool_context.state["intent_mandate"]
  if not intent_mandate:
    raise RuntimeError("No IntentMandate found in tool context state.")
  risk_data = _collect_risk_data(tool_context)
  if not risk_data:
    raise RuntimeError("No risk data found in tool context state.")
  message = (
      A2aMessageBuilder()
      .add_text("Find products that match the user's IntentMandate.")
      .add_data(INTENT_MANDATE_DATA_KEY, intent_mandate.model_dump())
      .add_data("risk_data", risk_data)
      .add_data("debug_mode", debug_mode)
      .add_data("shopping_agent_id", "trusted_shopping_agent")
      .build()
  )
  task = await merchant_agent_client.send_a2a_message(message)

  if task.status.state != "completed":
    raise RuntimeError(f"Failed to find products: {task.status}")

  tool_context.state["shopping_context_id"] = task.context_id
  cart_mandates = _parse_cart_mandates(task.artifacts)
  tool_context.state["cart_mandates"] = cart_mandates

  # Extract metadata from artifacts
  metadata_dict = _extract_metadata_from_artifacts(task.artifacts)
  tool_context.state["product_metadata"] = metadata_dict

  # Format products with images for display
  return _format_products_with_images(cart_mandates, metadata_dict)


def update_chosen_cart_mandate(cart_id: str, tool_context: ToolContext) -> str:
  """Updates the chosen CartMandate in the tool context state.

  Args:
    cart_id: The ID of the chosen cart.
    tool_context: The ADK supplied tool context.
  """
  cart_mandates: list[CartMandate] = tool_context.state.get("cart_mandates", [])
  for cart in cart_mandates:
    print(
        f"Checking cart with ID: {cart.contents.id} with chosen ID: {cart_id}"
    )
    if cart.contents.id == cart_id:
      tool_context.state["chosen_cart_id"] = cart_id
      return f"CartMandate with ID {cart_id} selected."
  return f"CartMandate with ID {cart_id} not found."


def _parse_cart_mandates(artifacts: list[Artifact]) -> list[CartMandate]:
  """Parses a list of artifacts into a list of CartMandate objects."""
  return find_canonical_objects(artifacts, CART_MANDATE_DATA_KEY, CartMandate)


def _collect_risk_data(tool_context: ToolContext) -> dict:
  """Creates a risk_data in the tool_context."""
  # This is a fake risk data for demonstration purposes.
  risk_data = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...fake_risk_data"
  tool_context.state["risk_data"] = risk_data
  return risk_data


def _extract_metadata_from_artifacts(artifacts: list[Artifact]) -> dict[str, dict]:
  """Extracts product metadata from artifacts.

  Args:
    artifacts: List of Artifact objects from merchant response.

  Returns:
    Dictionary mapping cart_id to metadata dict.
  """
  metadata_dict = {}

  for artifact in artifacts:
    for part in artifact.parts:
      if hasattr(part.root, 'data') and isinstance(part.root.data, dict):
        # Look for metadata key
        metadata_key = f"{CART_MANDATE_DATA_KEY}.metadata"
        if metadata_key in part.root.data:
          # Get the corresponding cart mandate to extract cart_id
          if CART_MANDATE_DATA_KEY in part.root.data:
            cart_data = part.root.data[CART_MANDATE_DATA_KEY]
            cart_id = cart_data.get('contents', {}).get('id')
            if cart_id:
              metadata_dict[cart_id] = part.root.data[metadata_key]

  return metadata_dict


def _format_products_with_images(
    cart_mandates: list[CartMandate],
    metadata_dict: dict[str, dict] = None
) -> str:
  """Formats CartMandates with product images for display.

  Args:
    cart_mandates: List of CartMandate objects to format.
    metadata_dict: Dictionary mapping cart_id to metadata (image, description, url).

  Returns:
    A Markdown-formatted string with product details and images.
  """
  if not cart_mandates:
    return "No products found."

  if metadata_dict is None:
    metadata_dict = {}

  output = "Here are the available products:\n\n"

  for idx, cart in enumerate(cart_mandates, 1):
    item_name = cart.contents.payment_request.details.display_items[0].label
    total_price = cart.contents.payment_request.details.total.amount.value
    currency = cart.contents.payment_request.details.total.amount.currency
    merchant_name = cart.contents.merchant_name
    cart_id = cart.contents.id

    # Get metadata for this cart
    metadata = metadata_dict.get(cart_id, {})
    image_url = metadata.get('image')
    description = metadata.get('description')
    product_url = metadata.get('url')

    # Build product entry
    output += f"### {idx}. {item_name}\n\n"

    # Add product image if available
    if image_url:
      output += f"![{item_name}]({image_url})\n\n"

    # Add description if available
    if description:
      output += f"*{description}*\n\n"

    output += f"**Price:** {currency} ${total_price}\n\n"
    output += f"**Sold by:** {merchant_name}\n\n"

    # Add product link if available
    if product_url:
      output += f"[View on {merchant_name} website]({product_url})\n\n"

    output += f"**Cart ID:** `{cart_id}`\n\n"
    output += "---\n\n"

  output += "\nPlease choose which item you'd like to purchase by saying the number (e.g., 'I'll take option 1')."

  return output
